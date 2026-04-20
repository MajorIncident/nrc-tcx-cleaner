# NRC TCX Cleaner (v7)

Clean, fix, and enrich Nike Run Club TCX exports for Strava.

Nike Run Club exports often contain broken, incomplete, or inconsistent TCX data. This tool repairs those files and transforms them into a clean, structured, and visually polished running history ready for Strava import.

---

## ✨ Features

### Core Fixes
- Fixes incorrect or non-cumulative distance data
- Handles both GPS and non-GPS runs safely
- Preserves original run distance and duration
- Repairs malformed TCX structures

---

### Advanced Fixes (v6 + v7)

#### Synthetic Trackpoint Generation (v6)
- Automatically fixes files with too few data points
- Generates valid time-based trackpoints
- Allows broken files to import into Strava

#### Junk Activity Filtering (v7)
Optional automatic filtering:
- accidental starts
- empty runs
- broken recordings

Rules:
- Skip if distance < 0.5 km AND time < 5 min
- Skip if distance < 0.5 km AND time > 20 min

---

### Smart Naming
YYYY-MM-DD - Distance - Location - Labels

---

## 🚀 Usage

Dry run:
python fix_nrc_tcx_batch.py . -r --dry-run

With filtering:
python fix_nrc_tcx_batch.py . -r --dry-run --auto-filter-junk

Process:
python fix_nrc_tcx_batch.py . -r -o fixed_v7 --rename-output

Full:
python fix_nrc_tcx_batch.py . -r -o fixed_v7 --rename-output --auto-filter-junk --geocode --email your@email.com

---

## 📁 Output

- Cleaned .tcx files  
- manifest_titles_v7.csv  

---

## 🛠 Requirements

- Python 3.x

---

## 📄 License

MIT
