#!/usr/bin/env python3
"""
Drupal Media Module Image Scraper
Specifically extracts all images and SVGs from the Drupal Media library
(media--image and media--svg_image) as displayed in Drupal's Media administration.
"""

import os
import sys
import time
import json
import csv
from urllib.parse import urlparse, urljoin
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

TARGET_SITE = "https://nginx-nadg-palm-bay-dental-main.nadg1.amazee.io"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MEDIA_OUTPUT_DIR = os.path.join(BASE_DIR, "media_images")
CONCURRENCY = 16

ALT_HOSTS = [
    "https://dam.nadentalgroup.com",
    "https://hub.nadentalgroup.com",
    TARGET_SITE
]

def create_session():
    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        raise_on_status=False
    )
    adapter = HTTPAdapter(max_retries=retries, pool_connections=CONCURRENCY, pool_maxsize=CONCURRENCY)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    })
    return session

def fetch_media_bundle(session, endpoint, file_rel_name):
    url = f"{TARGET_SITE}/jsonapi/{endpoint}?include={file_rel_name},thumbnail"
    entities = []
    included_files = {}

    print(f"\n[+] Fetching {endpoint} from JSON:API...")
    while url:
        resp = session.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        
        for inc in data.get("included", []):
            if inc.get("type") == "file--file":
                included_files[inc["id"]] = inc

        entities.extend(data.get("data", []))
        url = data.get("links", {}).get("next", {}).get("href")
        print(f"    Loaded {len(entities)} media items...", end="\r", flush=True)

    print(f"    Total {endpoint} items: {len(entities)} (Found {len(included_files)} associated files)")
    return entities, included_files

def prepare_media_download_tasks(session):
    os.makedirs(MEDIA_OUTPUT_DIR, exist_ok=True)
    
    images, img_files = fetch_media_bundle(session, "media/image", "field_media_image")
    svgs, svg_files = fetch_media_bundle(session, "media/svg_image", "field_media_svg_image")

    all_media = [(item, "image", "field_media_image") for item in images] + \
                [(item, "svg_image", "field_media_svg_image") for item in svgs]
    
    all_files = {**img_files, **svg_files}
    
    tasks = []
    seen_dest_filenames = {}

    for item, bundle, file_field in all_media:
        mid = item.get("attributes", {}).get("drupal_internal__mid")
        name = item.get("attributes", {}).get("name", "")
        created = item.get("attributes", {}).get("created", "")
        changed = item.get("attributes", {}).get("changed", "")
        
        # Relationships
        rel_field = item.get("relationships", {}).get(file_field, {})
        file_ref = rel_field.get("data")
        alt = rel_field.get("meta", {}).get("alt", "")

        thumb_ref = item.get("relationships", {}).get("thumbnail", {}).get("data")
        thumb_alt = item.get("relationships", {}).get("thumbnail", {}).get("meta", {}).get("alt", "")
        if not alt and thumb_alt:
            alt = thumb_alt

        target_file_id = None
        if file_ref and file_ref.get("id"):
            target_file_id = file_ref["id"]
        elif thumb_ref and thumb_ref.get("id"):
            target_file_id = thumb_ref["id"]

        file_entity = all_files.get(target_file_id) if target_file_id else None
        
        if not file_entity:
            print(f"[-] Warning: Media item mid={mid} ('{name}') has no referenced file entity.")
            continue

        file_attrs = file_entity.get("attributes", {})
        raw_filename = file_attrs.get("filename", f"media_{mid}.bin")
        filemime = file_attrs.get("filemime", "")
        filesize = file_attrs.get("filesize", 0)
        uri_obj = file_attrs.get("uri", {})
        drupal_uri = uri_obj.get("value", "")
        remote_url = uri_obj.get("url", "")

        # Subdirectory by bundle
        bundle_dir = "images" if bundle == "image" else "svgs"
        dest_folder = os.path.join(MEDIA_OUTPUT_DIR, bundle_dir)
        os.makedirs(dest_folder, exist_ok=True)

        # Handle filename collisions cleanly by prepending mid if duplicate filename
        if raw_filename in seen_dest_filenames and seen_dest_filenames[raw_filename] != target_file_id:
            safe_filename = f"mid_{mid}_{raw_filename}"
        else:
            safe_filename = raw_filename
            seen_dest_filenames[raw_filename] = target_file_id

        local_file_path = os.path.join(dest_folder, safe_filename)
        rel_local_path = os.path.join("media_images", bundle_dir, safe_filename)

        tasks.append({
            "media_id": mid,
            "media_uuid": item.get("id"),
            "name": name,
            "bundle": bundle,
            "alt": alt,
            "created": created,
            "updated": changed,
            "file_uuid": target_file_id,
            "filename": safe_filename,
            "original_filename": raw_filename,
            "filemime": filemime,
            "expected_filesize": filesize,
            "drupal_uri": drupal_uri,
            "remote_url": remote_url,
            "local_file_path": local_file_path,
            "local_rel_path": rel_local_path
        })

    return tasks

def download_media_item(session, task):
    local_path = task["local_file_path"]
    orig_url = task["remote_url"]

    # Candidate URLs to try
    candidate_urls = []
    if orig_url.startswith("http"):
        candidate_urls.append(orig_url)
        # Add alternatives with same path
        parsed = urlparse(orig_url)
        path = parsed.path
        for host in ALT_HOSTS:
            alt_url = host + path
            if alt_url not in candidate_urls:
                candidate_urls.append(alt_url)
    else:
        path = orig_url
        for host in ALT_HOSTS:
            candidate_urls.append(urljoin(host, path))

    success = False
    last_err = None
    downloaded_size = 0
    used_url = None

    for url in candidate_urls:
        try:
            resp = session.get(url, stream=True, timeout=20)
            if resp.status_code == 200:
                with open(local_path, "wb") as f:
                    for chunk in resp.iter_content(chunk_size=65536):
                        if chunk:
                            f.write(chunk)
                downloaded_size = os.path.getsize(local_path)
                success = True
                used_url = url
                break
            else:
                last_err = f"HTTP {resp.status_code}"
        except Exception as e:
            last_err = str(e)

    if success:
        return {
            "status": "success",
            "downloaded_size": downloaded_size,
            "used_url": used_url,
            "task": task
        }
    else:
        return {
            "status": "failed",
            "error": last_err or "Unknown failure",
            "task": task
        }

def main():
    start_time = time.time()
    session = create_session()

    print("============================================================")
    print("Drupal Media Module Image Scraper")
    print(f"Target: {TARGET_SITE}")
    print("============================================================")

    tasks = prepare_media_download_tasks(session)
    print(f"\n[+] Total Media items to download: {len(tasks)}")

    success_cnt = 0
    fail_cnt = 0
    total_bytes = 0
    manifest = []

    print(f"\n[+] Starting concurrent download with {CONCURRENCY} workers...")

    with ThreadPoolExecutor(max_workers=CONCURRENCY) as executor:
        future_map = {executor.submit(download_media_item, session, t): t for t in tasks}
        total = len(future_map)
        done = 0

        for fut in as_completed(future_map):
            done += 1
            res = fut.result()
            task = res["task"]
            status = res["status"]

            if status == "success":
                success_cnt += 1
                size = res["downloaded_size"]
                total_bytes += size
                task["download_status"] = "success"
                task["downloaded_size"] = size
                task["download_source_url"] = res["used_url"]
            else:
                fail_cnt += 1
                task["download_status"] = "failed"
                task["downloaded_size"] = 0
                task["error"] = res.get("error", "Unknown error")
                task["download_source_url"] = ""
                print(f"\n[-] Failed: mid={task['media_id']} '{task['name']}': {task.get('error')}")

            manifest.append(task)
            pct = (done / total) * 100
            print(f"Progress: {done}/{total} ({pct:.1f}%) | Success: {success_cnt} | Failed: {fail_cnt}", end="\r", flush=True)

    print("\n\n[+] Writing manifests...")

    # Sort manifest by media_id descending (like Drupal admin view)
    def parse_mid(x):
        try:
            return int(x.get("media_id", 0))
        except (ValueError, TypeError):
            return 0

    manifest.sort(key=parse_mid, reverse=True)

    manifest_json_path = os.path.join(BASE_DIR, "media_manifest.json")
    with open(manifest_json_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    manifest_csv_path = os.path.join(BASE_DIR, "media_manifest.csv")
    csv_fields = [
        "media_id", "name", "bundle", "alt", "filename", "filemime",
        "downloaded_size", "download_status", "download_source_url",
        "local_rel_path", "created", "updated", "media_uuid", "file_uuid"
    ]
    with open(manifest_csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=csv_fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(manifest)

    elapsed = time.time() - start_time
    mb = total_bytes / (1024 * 1024)

    print("=" * 60)
    print("MEDIA MODULE SCRAPE SUMMARY")
    print(f"Total media items processed: {len(tasks)}")
    print(f"Successfully downloaded:     {success_cnt}")
    print(f"Failed:                      {fail_cnt}")
    print(f"Total downloaded size:       {mb:.2f} MB")
    print(f"Time elapsed:                {elapsed:.2f} seconds")
    print(f"Media files directory:       {MEDIA_OUTPUT_DIR}")
    print(f"Manifest JSON:               {manifest_json_path}")
    print(f"Manifest CSV:                {manifest_csv_path}")
    print("=" * 60)

if __name__ == "__main__":
    main()
