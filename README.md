# Drupal Media Image Search Engine

A visual search application built specifically for the Drupal Media module images scraped from `https://nginx-nadg-palm-bay-dental-main.nadg1.amazee.io/`.

Give it any screenshot, cropped region, or image file, and it instantly scans across the 792 Drupal media items to find matches with **&ge; 80% similarity** (customizable from 50% to 98%).

---

## Features

- **High Speed Visual Search**: Sub-millisecond to ~25ms query latency across 792 media assets.
- **Multi-Signal Similarity Matching**:
  - Difference Hash (dHash) & Perceptual Hash (pHash)
  - Normalized Cross-Correlation (NCC)
  - 3D HSV Color Histogram Correlation
  - Adaptive transparency/alpha compositing for white icons and SVGs
- **Interactive Drag-to-Crop**: When you upload or paste a screenshot containing multiple elements, you can drag a box directly on the screen to search only that specific cropped region.
- **Clipboard Paste (<kbd>Ctrl+V</kbd>)**: Simply capture a screenshot with your OS tool and press <kbd>Ctrl</kbd> + <kbd>V</kbd> anywhere on the web page.
- **Detailed Drupal Media Metadata**: Shows Media Name, Drupal Media ID (`mid`), bundle (`image` / `svg_image`), dimensions, file size, local file path, and remote origin CDN URL.
- **Web UI & CLI**: Beautiful web application on `http://localhost:5000` plus command-line search script.

---

## 1. Web Application

The web server is already running and accessible at:
👉 **[http://localhost:5000](http://localhost:5000)**

To run or restart the web application anytime:
```bash
cd /home/ygs0052/Music/scraped-image
./run_app.sh
```

---

## 2. Command-Line Search (CLI)

You can also run visual searches directly from the terminal using [`cli_search.py`](file:///home/ygs0052/Music/scraped-image/cli_search.py):

```bash
# Search with default 80% threshold
./venv/bin/python cli_search.py --image /path/to/screenshot.png --threshold 80

# Output results as JSON
./venv/bin/python cli_search.py --image /path/to/screenshot.png --threshold 80 --json
```

---

## Project Structure

```text
/home/ygs0052/Music/scraped-image/
├── app.py                   # Web application server (Flask)
├── run_app.sh               # Startup script for web UI
├── search_engine.py         # Visual search engine core & feature extraction
├── cli_search.py            # Command-line search tool
├── image_index.pkl          # Precomputed visual signatures cache
├── media_images/
│   ├── images/              # 616 standard image files
│   └── svgs/                # 176 SVG vector graphic files
├── media_manifest.json      # Complete Drupal media metadata (JSON)
├── media_manifest.csv       # Complete Drupal media metadata (CSV)
├── templates/
│   └── index.html           # Interactive web UI
├── static/
│   ├── css/style.css        # Responsive dark/light theme styles
│   └── js/app.js            # Drag-and-drop, canvas crop, and search logic
└── README.md
```
