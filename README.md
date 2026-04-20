# NRC TCX Cleaner (v7)

Clean, repair, normalize, and enrich Nike Run Club (NRC) TCX exports for reliable Strava import and long-term archival.

This tool was built to solve real-world issues with NRC exports:
- broken or non-cumulative distance data
- missing or insufficient trackpoints
- non-GPS legacy runs
- inconsistent naming
- unusable files rejected by Strava
- junk / accidental activities cluttering your history

The result is a clean, structured, consistent running history that imports properly and looks intentional.

---

# ✨ Feature Overview

## 1. Distance Repair

Fixes incorrect or flat DistanceMeters values.

- GPS runs:
  - recalculates distance using coordinates
  - scales to match original NRC totals

- Non-GPS runs:
  - interpolates distance over time
  - preserves total distance

---

## 2. Synthetic Trackpoint Generation (v6)

Automatically fixes files with:
- 0 or 1 trackpoint
- summary-only data

What it does:
- generates 60–300 evenly spaced trackpoints
- distributes time and distance across them
- produces valid TCX structure

Result:
- Strava no longer throws "too few data points"
- activity imports successfully
- no GPS map (expected)

---

## 3. Junk Activity Filtering (v7)

Optional but highly recommended.

Enable with:
--auto-filter-junk

Automatically skips:
- accidental starts
- empty activities
- broken long recordings with no distance

Rules:
- distance < 0.5 km AND time < 5 min → skip
- distance < 0.5 km AND time > 20 min → skip

Skipped files:
- are NOT deleted
- are logged in manifest_titles_v7.csv
- include reason field

---

## 4. Smart Activity Naming

Generates consistent, readable filenames:

YYYY-MM-DD - Distance - Location - Labels

Examples:

2014-05-10 - 10K
2015-06-01 - Half Marathon - Long Run
2016-09-02 - 8.0 km - Cary, NC
2018-05-10 - 10K - Paris, France - Fast
2019-07-12 - 5K - Fast

---

## 5. Intelligent Labeling

Automatically tags runs based on your dataset:

Fast:
- determined by percentile (default top 8%)

Long Run:
- distance-based threshold (default 16.5 km)

Configurable:
--fast-quantile
--fast-min-km
--long-run-km

---

## 6. Location Enrichment (Optional)

Uses OpenStreetMap (Nominatim):

--geocode --email your@email.com

Adds:
- city
- state/province (for US/Canada)
- country (for international)

Formatting:
- US: Cary, NC
- Canada: Toronto, ON
- International: Paris, France

Home suppression:
--home-city Toronto
--home-country Canada

---

## 7. Batch Processing

- processes entire folders
- supports recursion (-r)
- handles mixed-quality files safely

---

## 8. Manifest Output

Outputs:
manifest_titles_v7.csv

Includes:
- original filename
- output filename
- distance
- pace
- labels
- location
- processing mode
- synthetic points added
- skipped_reason (if filtered)

---

# 🚀 Usage

## Dry Run (always start here)

python fix_nrc_tcx_batch.py . -r --dry-run

---

## Dry Run with Filtering

python fix_nrc_tcx_batch.py . -r --dry-run --auto-filter-junk

---

## Process Files

python fix_nrc_tcx_batch.py . -r -o fixed_v7 --rename-output

---

## Full Recommended Run

python fix_nrc_tcx_batch.py . -r -o fixed_v7 \
  --rename-output \
  --auto-filter-junk \
  --geocode --email your@email.com

---

## In-Place Processing (advanced)

python fix_nrc_tcx_batch.py . -r --in-place --auto-filter-junk

---

# ⚙️ Full Options Reference

--dry-run  
Preview changes without writing files

-r / --recursive  
Process subfolders

-o <folder>  
Output directory

--in-place  
Modify original files

--rename-output  
Rename files using generated titles

--auto-filter-junk  
Skip junk activities

--geocode  
Enable reverse geocoding

--email  
Required for geocoding

--user-agent  
Optional override for API identification

--fast-quantile  
Fast run threshold (default 0.08)

--fast-min-km  
Minimum distance for Fast (default 4.0 km)

--long-run-km  
Long run threshold (default 16.5 km)

--home-city  
Suppress this city (default Toronto)

--home-country  
Suppress this country (default Canada)

---

# 📊 Processing Modes

Each file is processed using one of:

gps_scaled_to_final_total  
time_interpolated_no_gps  
synthetic_trackpoints_no_gps  
SKIPPED  

---

# 📁 Output Structure

Example:

fixed_v7/
  2018-05-10 - 10K - Paris, France - Fast.tcx
  2016-09-02 - 8.0 km - Cary, NC.tcx
  manifest_titles_v7.csv

---

# ⚠️ Important Notes

- Non-GPS runs will not have maps
- Synthetic runs may appear as straight lines
- Strava may ignore TCX titles → filename matters
- Geocoding is rate-limited (~1 req/sec)

---

# 🛠 Requirements

- Python 3.x
- No external libraries

---

# 📌 Why This Exists

NRC exports are not designed for interoperability.

This tool:
- fixes broken data
- restores missing structure
- normalizes naming
- enables clean Strava import
- preserves your running history properly

---

# 📄 License

MIT
