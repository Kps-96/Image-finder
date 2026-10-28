#!/usr/bin/env python3
"""
CLI Visual & Semantic Search Tool
Usage:
  # Visual search with screenshot:
  python cli_search.py --image path/to/screenshot.png --threshold 80

  # Search without screenshot by text / keyword / Media ID:
  python cli_search.py --text "woman smiling"
  python cli_search.py --text "824"

  # Search without screenshot by image URL:
  python cli_search.py --url "https://dam.nadentalgroup.com/sites/default/files/..."

  # Reverse visual search (find similar images by Media ID):
  python cli_search.py --similar 824
"""

import sys
import os
import argparse
import json
from search_engine import ImageSearchEngine

def main():
    parser = argparse.ArgumentParser(description="Visual & Semantic Search Engine for Drupal Media Images")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--image", "-i", help="Path to query image or screenshot file")
    group.add_argument("--text", "-s", help="Search without screenshot: by keyword, name, filename, or Media ID")
    group.add_argument("--url", "-u", help="Search without screenshot: by remote image URL")
    group.add_argument("--similar", help="Reverse search: find visually similar images for a given Media ID")

    parser.add_argument("--threshold", "-t", type=float, default=None, help="Similarity threshold percentage (default: 80 visual, 50 text)")
    parser.add_argument("--top", "-k", type=int, default=20, help="Maximum number of results (default: 20)")
    parser.add_argument("--json", action="store_true", help="Output results in JSON format")

    args = parser.parse_args()
    engine = ImageSearchEngine()

    if args.image:
        if not os.path.exists(args.image):
            print(f"Error: Query image not found: {args.image}", file=sys.stderr)
            sys.exit(1)
        th = args.threshold if args.threshold is not None else 80.0
        results = engine.search_visual(args.image, threshold=th, top_k=args.top)
        query_desc = f"Image file: {args.image}"

    elif args.text:
        th = args.threshold if args.threshold is not None else 50.0
        results = engine.search_text(args.text, threshold=th, top_k=args.top)
        query_desc = f"Text query: \"{args.text}\""

    elif args.url:
        th = args.threshold if args.threshold is not None else 80.0
        results = engine.search_by_url(args.url, threshold=th, top_k=args.top)
        query_desc = f"Image URL: {args.url}"

    elif args.similar:
        th = args.threshold if args.threshold is not None else 65.0
        results = engine.find_similar_by_id(args.similar, threshold=th, top_k=args.top)
        query_desc = f"Visual similarity to Media ID: {args.similar}"

    if args.json:
        print(json.dumps(results, indent=2))
        return

    print("=" * 70)
    print("SEARCH RESULTS")
    print(f"Query:             {query_desc}")
    print(f"Match Threshold:   {results.get('threshold')}%")
    print(f"Total Indexed:     {results.get('total_indexed')} media items")
    print(f"Matches Found:     {results.get('match_count')}")
    print(f"Search Duration:   {results.get('elapsed_ms')} ms")
    print("=" * 70)

    if not results.get('results'):
        print("\nNo images found matching your query.")
        return

    for idx, match in enumerate(results['results'], 1):
        score = match['score']
        meta = match['meta']
        match_type = match.get('match_type', 'match')
        details = match.get('score_details', {})
        reason = match.get('match_reason', '')

        extra_info = []
        if details.get('deep_sim'):
            extra_info.append(f"Deep Neural Sim: {details['deep_sim']}%")
        if details.get('dhash'):
            extra_info.append(f"dHash: {details['dhash']}%")
        if reason:
            extra_info.append(f"Reason: {reason}")

        info_str = f" ({', '.join(extra_info)})" if extra_info else ""
        print(f"\n[{idx}] {score}% MATCH{info_str}")
        print(f"    Media ID:    {meta.get('media_id')}")
        print(f"    Media Name:  {meta.get('name')}")
        print(f"    Bundle:      {meta.get('bundle')}")
        print(f"    File:        {meta.get('filename')}")
        print(f"    Dimensions:  {meta.get('width')} x {meta.get('height')}")
        print(f"    Local Path:  {meta.get('local_rel_path')}")
        if meta.get('alt'):
            print(f"    Alt Text:    {meta.get('alt')}")
        print(f"    Remote URL:  {meta.get('remote_url')}")

    print("\n" + "=" * 70)

if __name__ == "__main__":
    main()
