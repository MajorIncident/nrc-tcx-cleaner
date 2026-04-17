# NRC TCX Cleaner

Clean and enrich Nike Run Club TCX exports for Strava.

Nike Run Club exports often contain broken or inconsistent TCX data, which leads to incorrect distances and poor imports into platforms like Strava. This tool fixes those issues and transforms raw exports into a clean, structured, and visually polished running history.

---

## ✨ Features

- Fixes incorrect or non-cumulative distance data in TCX files  
- Handles both GPS and non-GPS runs safely  
- Preserves original run distances from Nike Run Club  
- Generates clean, human-readable activity names  
- Detects milestone runs (5K, 10K, Half Marathon, Marathon)  
- Tags standout efforts:
  - **Fast** (relative to your dataset)
  - **Long Run**
- Adds location data (city, state/country) for GPS runs  
- Suppresses repetitive “home city” labeling  
- Batch processes entire folders of runs  
- Outputs a CSV manifest for full preview and validation  

---

## 🧠 Example Output

Before:
```
Morning Run
Evening Run
Run
```

After:
```
2014-05-10 - 10K
2015-06-01 - Half Marathon - Long Run
2016-09-02 - 8.0 km - Cary, NC
2018-05-10 - 10K - Paris, France - Fast
```

---

## 🚀 Usage

### 1. Dry run (recommended first)
Preview everything before writing changes:

```bash
python fix_nrc_tcx_batch_v5.py . -r --dry-run
```

### 2. Dry run with location data (GPS runs only)

```bash
python fix_nrc_tcx_batch_v5.py . -r --dry-run --geocode --email your@email.com
```

### 3. Process and write cleaned files

```bash
python fix_nrc_tcx_batch_v5.py . -r -o fixed_v5 --rename-output
```

### 4. Full run with geocoding

```bash
python fix_nrc_tcx_batch_v5.py . -r -o fixed_v5 \
  --rename-output \
  --geocode --email your@email.com
```

---

## ⚙️ Key Options

| Option | Description |
|------|------------|
| `--dry-run` | Preview changes without writing files |
| `-o <folder>` | Output directory |
| `--rename-output` | Rename files using generated titles |
| `--geocode` | Add city/country using GPS coordinates |
| `--fast-quantile` | % of fastest runs to tag as Fast (default 0.12) |
| `--fast-min-km` | Minimum distance for Fast tag (default 4.0 km) |
| `--long-run-km` | Distance threshold for Long Run (default 15.0 km) |
| `--home-city` | City to suppress from output (default Toronto) |
| `--home-country` | Country for home city (default Canada) |

---

## 📊 How It Works

### Distance Fixing
- GPS runs: recalculates distance from coordinates and scales to match original totals  
- Non-GPS runs: interpolates cumulative distance while preserving original totals  

### Smart Naming
Titles are generated using:
- Date of run  
- Distance (with milestone detection)  
- Location (only when meaningful)  
- Selective labels (Fast, Long Run)  

### Example Title Format
```
YYYY-MM-DD - Distance - Place - Labels
```

---

## 🌍 Location Handling

- Uses OpenStreetMap (Nominatim) for reverse geocoding  
- Formats locations intelligently:
  - US: Cary, NC
  - Canada: Vancouver, BC
  - International: Paris, France
- Suppresses repetitive home city (e.g., Toronto)

---

## ⚠️ Notes

- Non-GPS runs cannot recover location data  
- Strava may not always use TCX metadata as the activity title  
- File renaming is recommended for best results  
- Geocoding is rate-limited (~1 request per second)  

---

## 📁 Output

- Cleaned `.tcx` files  
- `manifest_titles_v5.csv` containing:
  - suggested filenames  
  - pace  
  - labels  
  - location  
  - preview notes  

---

## 🛠 Requirements

- Python 3.x  
- No external dependencies required  

---

## 📌 Why This Exists

Nike Run Club exports are not designed for interoperability.  
This tool bridges that gap and allows you to preserve your full running history with clean, consistent, and meaningful data.

---

## 📄 License

MIT
