#!/usr/bin/env python3
"""
fix_nrc_tcx_batch_v5.py

Repairs Nike Run Club TCX exports for Strava and enriches metadata with
clean titles based on your preferences.

What it does
- Fixes Trackpoint DistanceMeters to be cumulative.
- GPS runs:
  - computes cumulative distance from route
  - scales cumulative trackpoint distances to the original lap total
- No-GPS runs:
  - preserves original lap total
  - interpolates cumulative distance over time or point order
- Analyzes all runs first to compute your personal pace distribution
- Generates cleaner titles using:
  - date of run
  - milestone-aware distance formatting
  - optional place for non-home GPS runs
  - standout labels only when warranted: Fast or Long Run
- Rewrites <Notes> with a compact summary line
- Writes a CSV manifest

Default filename style:
YYYY-MM-DD - Distance/Milestone - Place - Labels.tcx

Examples:
2021-04-03 - 10K - Fast.tcx
2014-08-19 - Half Marathon - Long Run.tcx
2016-09-02 - 8.0 km - Cary, NC.tcx
2018-05-10 - 10K - Paris, France - Fast.tcx
"""

import argparse
import csv
import math
import os
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

TCX_NS = "http://www.garmin.com/xmlschemas/TrainingCenterDatabase/v2"
NS = {"tcx": TCX_NS}
ET.register_namespace("", TCX_NS)

EARTH_RADIUS_M = 6371000.0

US_STATE_ABBREV = {
    "alabama":"AL","alaska":"AK","arizona":"AZ","arkansas":"AR","california":"CA","colorado":"CO",
    "connecticut":"CT","delaware":"DE","florida":"FL","georgia":"GA","hawaii":"HI","idaho":"ID",
    "illinois":"IL","indiana":"IN","iowa":"IA","kansas":"KS","kentucky":"KY","louisiana":"LA",
    "maine":"ME","maryland":"MD","massachusetts":"MA","michigan":"MI","minnesota":"MN","mississippi":"MS",
    "missouri":"MO","montana":"MT","nebraska":"NE","nevada":"NV","new hampshire":"NH","new jersey":"NJ",
    "new mexico":"NM","new york":"NY","north carolina":"NC","north dakota":"ND","ohio":"OH","oklahoma":"OK",
    "oregon":"OR","pennsylvania":"PA","rhode island":"RI","south carolina":"SC","south dakota":"SD",
    "tennessee":"TN","texas":"TX","utah":"UT","vermont":"VT","virginia":"VA","washington":"WA",
    "west virginia":"WV","wisconsin":"WI","wyoming":"WY","district of columbia":"DC"
}

CA_PROV_ABBREV = {
    "alberta":"AB","british columbia":"BC","manitoba":"MB","new brunswick":"NB","newfoundland and labrador":"NL",
    "nova scotia":"NS","ontario":"ON","prince edward island":"PE","quebec":"QC","saskatchewan":"SK",
    "northwest territories":"NT","nunavut":"NU","yukon":"YT"
}


def haversine_m(lat1, lon1, lat2, lon2):
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2.0) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlon / 2.0) ** 2
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(a))


def first_text(parent, path):
    el = parent.find(path, NS)
    if el is None or el.text is None:
        return None
    return el.text.strip()


def parse_float(s):
    try:
        return float(s)
    except Exception:
        return None


def parse_trackpoints(lap):
    tps = lap.findall(".//tcx:Trackpoint", NS)
    rows = []
    for idx, tp in enumerate(tps):
        lat = parse_float(first_text(tp, "./tcx:Position/tcx:LatitudeDegrees"))
        lon = parse_float(first_text(tp, "./tcx:Position/tcx:LongitudeDegrees"))
        tp_time = first_text(tp, "./tcx:Time")
        dist_el = tp.find("./tcx:DistanceMeters", NS)
        rows.append(
            {
                "idx": idx,
                "tp": tp,
                "lat": lat,
                "lon": lon,
                "time": tp_time,
                "dist_el": dist_el,
            }
        )
    return rows


def iso_to_epochish(s):
    import datetime as dt
    if not s:
        return None
    try:
        if s.endswith("Z"):
            d = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
        else:
            d = dt.datetime.fromisoformat(s)
        return d.timestamp()
    except Exception:
        return None


def extract_date_from_activity(activity, lap):
    txt = first_text(activity, "./tcx:Id")
    if txt and len(txt) >= 10:
        return txt[:10]
    tps = lap.findall(".//tcx:Trackpoint", NS)
    if tps:
        txt = first_text(tps[0], "./tcx:Time")
        if txt and len(txt) >= 10:
            return txt[:10]
    start = lap.get("StartTime")
    if start and len(start) >= 10:
        return start[:10]
    return "unknown-date"


def cumulative_from_gps(rows):
    points = [(r["lat"], r["lon"]) for r in rows if r["lat"] is not None and r["lon"] is not None]
    if len(points) < 2:
        return None, 0
    cumulative = [0.0] * len(rows)
    last_lat = None
    last_lon = None
    total = 0.0
    gps_pts = 0
    for i, r in enumerate(rows):
        if r["lat"] is None or r["lon"] is None:
            cumulative[i] = total
            continue
        gps_pts += 1
        if last_lat is not None and last_lon is not None:
            step = haversine_m(last_lat, last_lon, r["lat"], r["lon"])
            if step < 0:
                step = 0.0
            total += step
        cumulative[i] = total
        last_lat, last_lon = r["lat"], r["lon"]
    if total <= 0:
        return None, gps_pts
    return cumulative, gps_pts


def cumulative_interpolated(rows, final_total):
    n = len(rows)
    if n == 0:
        return []
    if n == 1:
        return [final_total]
    epochs = [iso_to_epochish(r["time"]) for r in rows]
    usable = [e for e in epochs if e is not None]
    if len(usable) >= 2:
        start = usable[0]
        end = usable[-1]
        span = end - start
        if span > 0:
            out = []
            for e in epochs:
                if e is None:
                    out.append(None)
                else:
                    frac = (e - start) / span
                    frac = max(0.0, min(1.0, frac))
                    out.append(final_total * frac)
            for i, v in enumerate(out):
                if v is None:
                    out[i] = final_total * (i / (n - 1))
            return out
    return [final_total * (i / (n - 1)) for i in range(n)]


def set_distance_element(parent, value):
    el = parent.find("./tcx:DistanceMeters", NS)
    if el is None:
        el = ET.SubElement(parent, f"{{{TCX_NS}}}DistanceMeters")
    el.text = f"{value:.6f}"


def get_or_create_notes(activity):
    notes = activity.find("./tcx:Notes", NS)
    if notes is None:
        id_el = activity.find("./tcx:Id", NS)
        notes = ET.Element(f"{{{TCX_NS}}}Notes")
        if id_el is not None:
            children = list(activity)
            insert_at = children.index(id_el) + 1
            activity.insert(insert_at, notes)
        else:
            activity.insert(0, notes)
    return notes


def pace_min_per_km(total_seconds, meters):
    if not total_seconds or not meters or meters <= 0:
        return None
    return (total_seconds / 60.0) / (meters / 1000.0)


def format_pace(min_per_km):
    if min_per_km is None:
        return None
    mins = int(min_per_km)
    secs = int(round((min_per_km - mins) * 60))
    if secs == 60:
        mins += 1
        secs = 0
    return f"{mins}:{secs:02d}/km"


def percentile(sorted_values, p):
    if not sorted_values:
        return None
    if p <= 0:
        return sorted_values[0]
    if p >= 1:
        return sorted_values[-1]
    idx = (len(sorted_values) - 1) * p
    lo = int(math.floor(idx))
    hi = int(math.ceil(idx))
    if lo == hi:
        return sorted_values[lo]
    frac = idx - lo
    return sorted_values[lo] * (1 - frac) + sorted_values[hi] * frac


def reverse_geocode(lat, lon, email=None, user_agent=None, timeout=20):
    params = {
        "format": "jsonv2",
        "lat": f"{lat:.7f}",
        "lon": f"{lon:.7f}",
        "zoom": "10",
        "addressdetails": "1",
    }
    if email:
        params["email"] = email
    url = "https://nominatim.openstreetmap.org/reverse?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url)
    req.add_header("User-Agent", user_agent or "nrc-tcx-fixer/1.0")
    req.add_header("Accept-Language", "en")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
    import json
    data = json.loads(raw)
    return data


def normalize_place(geo, home_city="Toronto", home_country="Canada"):
    if not geo:
        return ""
    address = geo.get("address", {}) or {}
    city = (
        address.get("city")
        or address.get("town")
        or address.get("village")
        or address.get("municipality")
        or address.get("county")
    )
    state = address.get("state")
    country = address.get("country")

    if not city and not country:
        return ""

    city_l = (city or "").strip().lower()
    country_l = (country or "").strip().lower()
    home_city_l = (home_city or "").strip().lower()
    home_country_l = (home_country or "").strip().lower()

    if city_l == home_city_l and country_l == home_country_l:
        return ""

    if country_l == "united states":
        st = US_STATE_ABBREV.get((state or "").strip().lower(), state)
        if city and st:
            return f"{city}, {st}"
        if city:
            return city
        return "United States"

    if country_l == "canada":
        prov = CA_PROV_ABBREV.get((state or "").strip().lower(), state)
        if city and prov:
            return f"{city}, {prov}"
        if city:
            return city
        return "Canada"

    if city and country:
        return f"{city}, {country}"
    if city:
        return city
    return country or ""


def format_distance_label(distance_m):
    km = (distance_m or 0.0) / 1000.0
    if abs(km - 5.0) <= 0.12:
        return "5K"
    if abs(km - 10.0) <= 0.18:
        return "10K"
    if abs(km - 21.0975) <= 0.25:
        return "Half Marathon"
    if abs(km - 42.195) <= 0.4:
        return "Marathon"
    if abs(km - round(km)) <= 0.05:
        return f"{int(round(km))}.0 km"
    return f"{km:.1f} km"


def choose_labels(info, fast_cutoff, long_run_km=15.0, fast_min_km=4.0):
    km = (info["written"] or 0.0) / 1000.0
    labels = []
    if km >= long_run_km:
        labels.append("Long Run")
    if info["pace"] is not None and fast_cutoff is not None and km >= fast_min_km and info["pace"] <= fast_cutoff:
        labels.append("Fast")
    return labels


def build_filename(date_str, distance_m, place=None, labels=None):
    parts = [date_str, format_distance_label(distance_m)]
    if place:
        parts.append(place)
    if labels:
        ordered = []
        if "Fast" in labels:
            ordered.append("Fast")
        if "Long Run" in labels:
            ordered.append("Long Run")
        for lbl in labels:
            if lbl not in ordered:
                ordered.append(lbl)
        parts.extend(ordered)
    return " - ".join(parts)


def build_notes_summary(filename_base, pace_str=None, place=None, gps_pts=0):
    parts = [filename_base]
    if pace_str:
        parts.append(pace_str)
    if place:
        parts.append(place)
    parts.append("GPS" if gps_pts >= 2 else "No GPS route")
    return " | ".join(parts)


def safe_filename(name):
    bad = '<>:"/\\|?*'
    out = []
    for ch in name:
        if ch in bad or ord(ch) < 32:
            out.append(" ")
        else:
            out.append(ch)
    cleaned = "".join(out)
    cleaned = " ".join(cleaned.split())
    return cleaned[:180].strip()


def analyze_file(path):
    tree = ET.parse(path)
    root = tree.getroot()
    activity = root.find(".//tcx:Activity", NS)
    if activity is None:
        raise ValueError("No Activity found")
    lap = activity.find("./tcx:Lap", NS)
    if lap is None:
        raise ValueError("No Lap found")

    rows = parse_trackpoints(lap)
    lap_dist = parse_float(first_text(lap, "./tcx:DistanceMeters")) or 0.0
    total_seconds = parse_float(first_text(lap, "./tcx:TotalTimeSeconds")) or None
    run_date = extract_date_from_activity(activity, lap)

    gps_cum, gps_pts = cumulative_from_gps(rows)
    if gps_cum is not None and gps_pts >= 2:
        gps_raw_total = gps_cum[-1]
        final_total = lap_dist if lap_dist > 0 else gps_raw_total
        mode = "gps_scaled_to_final_total"
    else:
        gps_raw_total = 0.0
        final_total = lap_dist
        mode = "time_interpolated_no_gps"

    first_gps = next((r for r in rows if r["lat"] is not None and r["lon"] is not None), None)
    pace = pace_min_per_km(total_seconds, final_total)

    return {
        "path": path,
        "tree": tree,
        "activity": activity,
        "lap": lap,
        "rows": rows,
        "tp": len(rows),
        "orig": lap_dist,
        "gps_raw": gps_raw_total,
        "written": final_total,
        "gps_pts": gps_pts,
        "mode": mode,
        "date": run_date,
        "total_seconds": total_seconds,
        "pace": pace,
        "first_gps": first_gps,
    }


def fix_and_write(info, output_path, dry_run=False, geocode=False, email=None, user_agent=None,
                  geocode_cache=None, fast_cutoff=None, long_run_km=15.0, fast_min_km=4.0,
                  home_city="Toronto", home_country="Canada"):
    activity = info["activity"]
    lap = info["lap"]
    rows = info["rows"]

    gps_cum, gps_pts = cumulative_from_gps(rows)
    if gps_cum is not None and gps_pts >= 2:
        gps_raw_total = gps_cum[-1]
        final_total = info["written"]
        scale = (final_total / gps_raw_total) if gps_raw_total > 0 else 1.0
        new_cum = [max(0.0, d * scale) for d in gps_cum]
        mode = "gps_scaled_to_final_total"
    else:
        gps_raw_total = 0.0
        final_total = info["written"]
        new_cum = cumulative_interpolated(rows, final_total)
        mode = "time_interpolated_no_gps"

    for r, d in zip(rows, new_cum):
        if r["dist_el"] is None:
            r["dist_el"] = ET.SubElement(r["tp"], f"{{{TCX_NS}}}DistanceMeters")
        r["dist_el"].text = f"{d:.6f}"

    set_distance_element(lap, final_total)

    place = ""
    if geocode and info["first_gps"] is not None and gps_pts >= 2:
        key = (round(info["first_gps"]["lat"], 4), round(info["first_gps"]["lon"], 4))
        if geocode_cache is not None and key in geocode_cache:
            place = geocode_cache[key]
        else:
            geo = reverse_geocode(info["first_gps"]["lat"], info["first_gps"]["lon"], email=email, user_agent=user_agent)
            place = normalize_place(geo, home_city=home_city, home_country=home_country)
            if geocode_cache is not None:
                geocode_cache[key] = place
            time.sleep(1.1)

    labels = choose_labels(info, fast_cutoff=fast_cutoff, long_run_km=long_run_km, fast_min_km=fast_min_km)
    filename_base = build_filename(info["date"], final_total, place=place, labels=labels)
    pace_str = format_pace(info["pace"])
    notes_summary = build_notes_summary(filename_base, pace_str=pace_str, place=place, gps_pts=gps_pts)

    notes = get_or_create_notes(activity)
    old_notes = (notes.text or "").strip()
    notes.text = notes_summary if not old_notes else notes_summary + "\n" + old_notes

    result = {
        "file": os.path.basename(info["path"]),
        "mode": mode,
        "orig": info["orig"],
        "gps_raw": gps_raw_total,
        "written": final_total,
        "tp": info["tp"],
        "gps_pts": gps_pts,
        "date": info["date"],
        "pace": pace_str or "",
        "place": place,
        "labels": ", ".join(labels),
        "filename_base": filename_base,
        "preview_notes": notes_summary,
        "output_file": "",
    }

    if not dry_run and output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        info["tree"].write(output_path, encoding="utf-8", xml_declaration=True)
        result["output_file"] = output_path

    return result


def collect_files(root_dir, recursive=False):
    root = Path(root_dir)
    if recursive:
        return sorted([str(p) for p in root.rglob("*.tcx") if p.is_file()])
    return sorted([str(p) for p in root.glob("*.tcx") if p.is_file()])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("input", help="input folder")
    parser.add_argument("-r", "--recursive", action="store_true", help="search recursively")
    parser.add_argument("-o", "--output", help="output folder")
    parser.add_argument("--in-place", action="store_true", help="overwrite original files")
    parser.add_argument("--dry-run", action="store_true", help="analyze only, write nothing")
    parser.add_argument("--geocode", action="store_true", help="reverse geocode GPS runs to city/country using Nominatim")
    parser.add_argument("--email", help="email for geocoding requests")
    parser.add_argument("--user-agent", help="custom user agent for geocoding requests")
    parser.add_argument("--rename-output", action="store_true", help="rename output files using the generated filename")
    parser.add_argument("--home-city", default="Toronto", help="suppress this city from output place labels")
    parser.add_argument("--home-country", default="Canada", help="suppress this country when paired with home city")
    parser.add_argument("--long-run-km", type=float, default=15.0, help="distance threshold for Long Run")
    parser.add_argument("--fast-quantile", type=float, default=0.12, help="fraction of fastest paced runs to tag as Fast")
    parser.add_argument("--fast-min-km", type=float, default=4.0, help="minimum distance for Fast tag")
    args = parser.parse_args()

    if args.in_place and args.output:
        print("Use either --in-place or -o/--output, not both.", file=sys.stderr)
        sys.exit(2)
    if not args.in_place and not args.output and not args.dry_run:
        print("Specify -o OUTPUT, --in-place, or --dry-run.", file=sys.stderr)
        sys.exit(2)
    if args.geocode and not (args.email or args.user_agent):
        print("For --geocode, provide at least --email or --user-agent.", file=sys.stderr)
        sys.exit(2)

    files = collect_files(args.input, recursive=args.recursive)
    if not files:
        print("No .tcx files found.")
        return

    analyzed = []
    for f in files:
        try:
            analyzed.append(analyze_file(f))
        except Exception as e:
            analyzed.append({"path": f, "error": str(e)})

    pace_values = sorted(
        a["pace"] for a in analyzed
        if "error" not in a and a.get("pace") is not None and (a.get("written") or 0.0) >= (args.fast_min_km * 1000.0)
    )
    fast_cutoff = percentile(pace_values, args.fast_quantile) if pace_values else None

    geocode_cache = {}
    manifest_rows = []
    processed = 0
    fast_count = 0
    long_count = 0

    out_dir = Path(args.output) if args.output else None
    if out_dir and not args.dry_run:
        out_dir.mkdir(parents=True, exist_ok=True)

    for info in analyzed:
        if "error" in info:
            print(f'{os.path.basename(info["path"])} | ERROR | {info["error"]}')
            manifest_rows.append({
                "file": os.path.basename(info["path"]),
                "output_file": "",
                "mode": "ERROR",
                "orig": "",
                "gps_raw": "",
                "written": "",
                "tp": "",
                "gps_pts": "",
                "date": "",
                "pace": "",
                "place": "",
                "labels": "",
                "filename_base": "",
                "preview_notes": "",
                "error": info["error"],
            })
            continue

        try:
            preview_place = ""
            if args.geocode and info["first_gps"] is not None and info["gps_pts"] >= 2:
                key = (round(info["first_gps"]["lat"], 4), round(info["first_gps"]["lon"], 4))
                if key in geocode_cache:
                    preview_place = geocode_cache[key]
                else:
                    geo = reverse_geocode(info["first_gps"]["lat"], info["first_gps"]["lon"], email=args.email, user_agent=args.user_agent)
                    preview_place = normalize_place(geo, home_city=args.home_city, home_country=args.home_country)
                    geocode_cache[key] = preview_place
                    time.sleep(1.1)

            labels = choose_labels(info, fast_cutoff=fast_cutoff, long_run_km=args.long_run_km, fast_min_km=args.fast_min_km)
            if "Fast" in labels:
                fast_count += 1
            if "Long Run" in labels:
                long_count += 1

            preview_base = build_filename(info["date"], info["written"], place=preview_place, labels=labels)
            preview_notes = build_notes_summary(preview_base, pace_str=format_pace(info["pace"]), place=preview_place, gps_pts=info["gps_pts"])

            result = {
                "file": os.path.basename(info["path"]),
                "mode": info["mode"],
                "orig": info["orig"],
                "gps_raw": info["gps_raw"],
                "written": info["written"],
                "tp": info["tp"],
                "gps_pts": info["gps_pts"],
                "date": info["date"],
                "pace": format_pace(info["pace"]) or "",
                "place": preview_place,
                "labels": ", ".join(labels),
                "filename_base": preview_base,
                "preview_notes": preview_notes,
                "output_file": "",
            }

            if not args.dry_run:
                if args.in_place:
                    output_path = info["path"]
                else:
                    out_name = os.path.basename(info["path"])
                    if args.rename_output:
                        out_name = safe_filename(preview_base) + ".tcx"
                    output_path = str(out_dir / out_name)
                result = fix_and_write(
                    info,
                    output_path=output_path,
                    dry_run=False,
                    geocode=args.geocode,
                    email=args.email,
                    user_agent=args.user_agent,
                    geocode_cache=geocode_cache,
                    fast_cutoff=fast_cutoff,
                    long_run_km=args.long_run_km,
                    fast_min_km=args.fast_min_km,
                    home_city=args.home_city,
                    home_country=args.home_country,
                )

            manifest_rows.append(result)
            processed += 1
            print(
                f'{result["file"]} | {result["mode"]} | date={result["date"]} | '
                f'written={result["written"]:.3f} | pace={result["pace"] or "-"} | '
                f'labels={result["labels"] or "-"} | place={result["place"] or "-"} | '
                f'filename="{result["filename_base"]}"'
            )
        except Exception as e:
            print(f'{os.path.basename(info["path"])} | ERROR | {e}')
            manifest_rows.append({
                "file": os.path.basename(info["path"]),
                "output_file": "",
                "mode": "ERROR",
                "orig": "",
                "gps_raw": "",
                "written": "",
                "tp": "",
                "gps_pts": "",
                "date": "",
                "pace": "",
                "place": "",
                "labels": "",
                "filename_base": "",
                "preview_notes": "",
                "error": str(e),
            })

    manifest_name = "manifest_titles_v5.csv"
    manifest_path = str((Path(args.output) if args.output else Path(args.input)) / manifest_name)
    fieldnames = [
        "file", "output_file", "mode", "orig", "gps_raw", "written", "tp", "gps_pts",
        "date", "pace", "place", "labels", "filename_base", "preview_notes", "error"
    ]
    with open(manifest_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in manifest_rows:
            writer.writerow({k: row.get(k, "") for k in fieldnames})

    print("")
    print(f"Processed {processed}/{len(files)} file(s).")
    print(f"Fast cutoff (min/km): {fast_cutoff:.3f}" if fast_cutoff is not None else "Fast cutoff unavailable.")
    print(f"Runs tagged Fast: {fast_count}")
    print(f"Runs tagged Long Run: {long_count}")
    if args.dry_run:
        print("Dry run only. No files were written.")
    print(f"Manifest written to: {manifest_path}")


if __name__ == "__main__":
    main()
