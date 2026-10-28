#!/usr/bin/env python3
"""
Drupal Media Visual & Semantic Search Engine - Web Application
Features:
- Visual Image / Screenshot / Crop Search
- Search without Screenshot: Text & Metadata Search (Name, Title, Filename, Media ID)
- Search without Screenshot: Direct Image URL Search
- Reverse Image Search (Find similar images by Media ID)
- Browseable Media Gallery with instant live filters
"""

import os
import io
import time
import base64
from PIL import Image
from flask import Flask, request, jsonify, send_from_directory, render_template

from search_engine import ImageSearchEngine

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEDIA_DIR = os.path.join(BASE_DIR, "media_images")

app = Flask(__name__, static_folder="static", template_folder="templates")
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024 # 32MB max upload

print("[App] Initializing Enhanced Search Engine...")
engine = ImageSearchEngine()
print(f"[App] Search Engine ready with {len(engine.records)} images.")

def format_web_paths(results_list):
    """Adds web-accessible URL paths to result items."""
    for item in results_list:
        meta = item["meta"]
        rel = meta.get("local_rel_path", "")
        if rel.startswith("media_images/"):
            web_path = "/media/" + rel[len("media_images/"):]
        else:
            web_path = "/media/" + rel
        item["web_url"] = web_path
    return results_list

@app.route("/")
def index():
    return render_template("index.html", total_images=len(engine.records))

@app.route("/media/<path:filename>")
def serve_media(filename):
    """Serves media images from the media_images directory."""
    return send_from_directory(MEDIA_DIR, filename)

@app.route("/api/status")
def status():
    return jsonify({
        "status": "online",
        "total_indexed": len(engine.records),
        "has_deep_model": engine.ort_session is not None,
        "media_dir": MEDIA_DIR
    })

@app.route("/api/search", methods=["POST"])
def search_visual():
    """Visual search endpoint for images, screenshots, and crops."""
    try:
        threshold = float(request.form.get("threshold", 80.0))
    except (ValueError, TypeError):
        threshold = 80.0

    try:
        top_k = int(request.form.get("top_k", 30))
    except (ValueError, TypeError):
        top_k = 30

    query_img = None

    if "image" in request.files:
        file = request.files["image"]
        if file.filename:
            query_img = Image.open(file.stream)
    elif "file" in request.files:
        file = request.files["file"]
        if file.filename:
            query_img = Image.open(file.stream)

    if query_img is None:
        data = request.get_json(silent=True) or {}
        b64 = data.get("image_base64") or request.form.get("image_base64")
        if b64:
            if "," in b64:
                b64 = b64.split(",", 1)[1]
            img_bytes = base64.b64decode(b64)
            query_img = Image.open(io.BytesIO(img_bytes))

    if query_img is None:
        return jsonify({"error": "No query image provided"}), 400

    # Optional cropping
    crop_x = request.form.get("crop_x")
    crop_y = request.form.get("crop_y")
    crop_w = request.form.get("crop_w")
    crop_h = request.form.get("crop_h")

    if crop_x and crop_y and crop_w and crop_h:
        try:
            x = max(0, int(float(crop_x)))
            y = max(0, int(float(crop_y)))
            w = int(float(crop_w))
            h = int(float(crop_h))
            if w > 5 and h > 5:
                query_img = query_img.crop((x, y, x + w, y + h))
        except Exception as e:
            print(f"Crop parsing error: {e}")

    results = engine.search_visual(query_img, threshold=threshold, top_k=top_k)
    results["results"] = format_web_paths(results["results"])
    return jsonify(results)

@app.route("/api/search_text", methods=["POST", "GET"])
def search_text():
    """
    Search image without screenshot:
    Matches by title, keyword, filename, Drupal Media ID (MID), alt text.
    """
    if request.method == "POST":
        data = request.get_json(silent=True) or request.form
        query = data.get("query", "")
        threshold = float(data.get("threshold", 60.0))
        top_k = int(data.get("top_k", 50))
    else:
        query = request.args.get("query", "")
        threshold = float(request.args.get("threshold", 60.0))
        top_k = int(request.args.get("top_k", 50))

    if not query.strip():
        return jsonify({"error": "Search query is empty", "results": []}), 400

    results = engine.search_text(query, threshold=threshold, top_k=top_k)
    results["results"] = format_web_paths(results["results"])
    return jsonify(results)

@app.route("/api/search_url", methods=["POST"])
def search_url():
    """
    Search image without screenshot:
    Fetch remote image by URL and perform visual similarity search.
    """
    data = request.get_json(silent=True) or request.form
    url = data.get("url", "").strip()
    threshold = float(data.get("threshold", 80.0))
    top_k = int(data.get("top_k", 30))

    if not url:
        return jsonify({"error": "No image URL provided"}), 400

    try:
        results = engine.search_by_url(url, threshold=threshold, top_k=top_k)
        results["results"] = format_web_paths(results["results"])
        return jsonify(results)
    except Exception as e:
        return jsonify({"error": f"Failed to download and search image from URL: {str(e)}"}), 400

@app.route("/api/similar/<media_id>")
def find_similar(media_id):
    """Find visually similar images for an existing image in the collection."""
    threshold = float(request.args.get("threshold", 70.0))
    top_k = int(request.args.get("top_k", 20))

    results = engine.find_similar_by_id(media_id, threshold=threshold, top_k=top_k)
    if "error" in results:
        return jsonify(results), 404

    results["results"] = format_web_paths(results["results"])
    return jsonify(results)

@app.route("/api/gallery")
def get_gallery():
    """Browse all media items with pagination and bundle filters."""
    bundle = request.args.get("bundle", "all")
    page = int(request.args.get("page", 1))
    per_page = int(request.args.get("per_page", 36))
    search_q = request.args.get("q", "").strip().lower()

    filtered = []
    for entry in engine.records:
        meta = entry["meta"]
        if bundle != "all" and meta.get("bundle") != bundle:
            continue
        if search_q:
            text = f"{meta.get('name', '')} {meta.get('filename', '')} {meta.get('media_id', '')}".lower()
            if search_q not in text:
                continue
        filtered.append(meta)

    total_items = len(filtered)
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    page_items = filtered[start_idx:end_idx]

    formatted = []
    for m in page_items:
        rel = m.get("local_rel_path", "")
        web_path = "/media/" + (rel[len("media_images/"):] if rel.startswith("media_images/") else rel)
        formatted.append({
            "meta": m,
            "web_url": web_path
        })

    return jsonify({
        "total": total_items,
        "page": page,
        "per_page": per_page,
        "total_pages": max(1, (total_items + per_page - 1) // per_page),
        "items": formatted
    })

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting server on http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
