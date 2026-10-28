#!/usr/bin/env python3
"""
Enhanced Drupal Media Visual & Semantic Search Engine
Features:
1. Deep Neural Feature Extraction (MobileNetV2 via ONNX Runtime)
2. Multi-Perceptual Hashing (dHash, pHash, aHash, wHash)
3. Normalized Cross-Correlation (NCC) & 3D HSV Color Histograms
4. Text & Metadata Search (Search without screenshot: by name, title, filename, MID, alt text)
5. Remote Image URL Search (Search without screenshot: directly by image URL)
6. Reverse Image Search (Find similar images by Media ID)
"""

import os
import io
import time
import json
import pickle
import re
import urllib.request
import numpy as np
from PIL import Image
import imagehash
import cv2
import cairosvg
import onnxruntime as ort

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
INDEX_FILE = os.path.join(BASE_DIR, "image_index.pkl")
MANIFEST_FILE = os.path.join(BASE_DIR, "media_manifest.json")
MODEL_PATH = os.path.join(BASE_DIR, "models", "mobilenetv2.onnx")

class ImageSearchEngine:
    def __init__(self, manifest_path=MANIFEST_FILE, index_path=INDEX_FILE, model_path=MODEL_PATH):
        self.manifest_path = manifest_path
        self.index_path = index_path
        self.model_path = model_path
        self.records = []
        self.deep_matrix = None # Precomputed numpy matrix (N, 1000) for vector search
        self.ort_session = None
        self.is_ready = False

        self._init_deep_model()
        self.load_or_build_index()

    def _init_deep_model(self):
        """Initializes ONNX Runtime session for MobileNetV2."""
        if os.path.exists(self.model_path):
            try:
                opts = ort.SessionOptions()
                opts.intra_op_num_threads = 4
                self.ort_session = ort.InferenceSession(
                    self.model_path,
                    sess_options=opts,
                    providers=['CPUExecutionProvider']
                )
                self.input_name = self.ort_session.get_inputs()[0].name
                self.output_name = self.ort_session.get_outputs()[0].name
                print("[Search Engine] MobileNetV2 deep neural model loaded successfully.")
            except Exception as e:
                print(f"[Search Engine] Warning: Could not load ONNX model ({e}). Continuing with hashes.")
                self.ort_session = None
        else:
            print(f"[Search Engine] Warning: Model not found at {self.model_path}")
            self.ort_session = None

    def _render_image(self, file_path_or_bytes):
        """Loads and returns an RGB PIL Image and OpenCV BGR image with adaptive alpha compositing."""
        if isinstance(file_path_or_bytes, str) and file_path_or_bytes.endswith('.svg'):
            png_bytes = cairosvg.svg2png(url=file_path_or_bytes, output_width=256)
            im = Image.open(io.BytesIO(png_bytes))
        elif isinstance(file_path_or_bytes, str):
            im = Image.open(file_path_or_bytes)
        elif isinstance(file_path_or_bytes, bytes):
            im = Image.open(io.BytesIO(file_path_or_bytes))
        elif isinstance(file_path_or_bytes, Image.Image):
            im = file_path_or_bytes
        else:
            raise ValueError("Unsupported image input type")

        if im.mode in ('RGBA', 'LA') or (im.mode == 'P' and 'transparency' in im.info):
            im = im.convert('RGBA')
            r, g, b, a = im.split()
            arr = np.array(im)
            alpha_mask = arr[:, :, 3] > 20
            if np.any(alpha_mask):
                mean_brightness = arr[alpha_mask, :3].mean()
                bg_color = (30, 30, 30) if mean_brightness > 128 else (240, 240, 240)
            else:
                bg_color = (255, 255, 255)

            bg = Image.new('RGB', im.size, bg_color)
            bg.paste(im, mask=a)
            pil_img = bg
        else:
            pil_img = im.convert('RGB')

        cv_img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
        return pil_img, cv_img

    def _extract_deep_features(self, pil_img):
        """Extracts normalized 1000-D feature embedding using MobileNetV2."""
        if self.ort_session is None:
            return np.zeros(1000, dtype=np.float32)

        try:
            resized = pil_img.convert('RGB').resize((224, 224))
            arr = np.array(resized, dtype=np.float32) / 255.0
            mean = np.array([0.485, 0.456, 0.406], dtype=np.float32)
            std = np.array([0.229, 0.224, 0.225], dtype=np.float32)
            arr = (arr - mean) / std
            arr = arr.transpose(2, 0, 1)[np.newaxis, ...].astype(np.float32)

            feat = self.ort_session.run([self.output_name], {self.input_name: arr})[0][0]
            norm = np.linalg.norm(feat)
            if norm > 0:
                feat = feat / norm
            return feat.astype(np.float32)
        except Exception as e:
            return np.zeros(1000, dtype=np.float32)

    def _compute_features(self, pil_img, cv_img):
        """Computes deep features, multi-hashes, color histogram, and thumbnail."""
        deep_feat = self._extract_deep_features(pil_img)
        ph = imagehash.phash(pil_img)
        dh = imagehash.dhash(pil_img)
        ah = imagehash.average_hash(pil_img)
        wh = imagehash.whash(pil_img)

        # 3D Color Histogram in HSV
        hsv = cv2.cvtColor(cv_img, cv2.COLOR_BGR2HSV)
        hist = cv2.calcHist([hsv], [0, 1, 2], None, [8, 8, 8], [0, 180, 0, 256, 0, 256])
        cv2.normalize(hist, hist)

        # 64x64 thumbnail for fast NCC
        small = cv2.resize(cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY), (64, 64))

        return {
            'deep_feat': deep_feat,
            'phash': ph,
            'dhash': dh,
            'ahash': ah,
            'whash': wh,
            'hist': hist.flatten(),
            'thumb': small,
            'width': pil_img.width,
            'height': pil_img.height
        }

    def load_or_build_index(self, force_rebuild=False):
        """Loads index cache if valid and contains deep embeddings, else rebuilds."""
        if not force_rebuild and os.path.exists(self.index_path):
            try:
                t0 = time.time()
                with open(self.index_path, 'rb') as f:
                    self.records = pickle.load(f)

                # Verify deep_feat presence in cache
                if self.records and 'deep_feat' in self.records[0]:
                    self._build_matrix()
                    self.is_ready = True
                    print(f"[Search Engine] Loaded {len(self.records)} indexed images (with Deep Embeddings) in {time.time()-t0:.3f}s")
                    return
                else:
                    print("[Search Engine] Upgrading index cache with Deep Neural Embeddings...")
            except Exception as e:
                print(f"[Search Engine] Cache load error: {e}, rebuilding...")

        self.rebuild_index()

    def _build_matrix(self):
        """Compiles deep embeddings into a fast 2D matrix for vectorized cosine similarity."""
        vectors = [r['deep_feat'] for r in self.records]
        if vectors:
            self.deep_matrix = np.array(vectors, dtype=np.float32)
        else:
            self.deep_matrix = None

    def rebuild_index(self):
        """Indexes all 792 images from manifest with Deep Embeddings and Multi-Hashes."""
        if not os.path.exists(self.manifest_path):
            raise FileNotFoundError(f"Manifest not found: {self.manifest_path}")

        with open(self.manifest_path, 'r', encoding='utf-8') as f:
            manifest = json.load(f)

        t0 = time.time()
        print(f"[Search Engine] Building enhanced visual index for {len(manifest)} media items...")
        indexed = []

        for idx, item in enumerate(manifest):
            rel_path = item.get('local_rel_path')
            full_path = os.path.join(BASE_DIR, rel_path) if not os.path.isabs(rel_path) else rel_path

            if not os.path.exists(full_path):
                continue

            try:
                pil_img, cv_img = self._render_image(full_path)
                feats = self._compute_features(pil_img, cv_img)

                item_copy = dict(item)
                item_copy['width'] = feats['width']
                item_copy['height'] = feats['height']

                indexed.append({
                    'meta': item_copy,
                    'deep_feat': feats['deep_feat'],
                    'phash': feats['phash'],
                    'dhash': feats['dhash'],
                    'ahash': feats['ahash'],
                    'whash': feats['whash'],
                    'hist': feats['hist'],
                    'thumb': feats['thumb']
                })
            except Exception as e:
                print(f"Warning: Failed to index {full_path}: {e}")

            if (idx + 1) % 50 == 0 or idx == len(manifest) - 1:
                print(f"  Indexed {idx+1}/{len(manifest)} items...", end="\r", flush=True)

        elapsed = time.time() - t0
        print(f"\n[Search Engine] Enhanced index built: {len(indexed)} images in {elapsed:.2f}s ({len(indexed)/elapsed:.1f} imgs/sec)")

        with open(self.index_path, 'wb') as f:
            pickle.dump(indexed, f)

        self.records = indexed
        self._build_matrix()
        self.is_ready = True

    def search_visual(self, query_img_input, threshold=80.0, top_k=50):
        """
        Visual search with fused Deep Embeddings + Multi-Perceptual Hashes + NCC + Color Histogram.
        query_img_input: PIL Image, file path, bytes, or numpy array.
        """
        t0 = time.time()

        if isinstance(query_img_input, np.ndarray):
            q_cv = query_img_input
            q_pil = Image.fromarray(cv2.cvtColor(q_cv, cv2.COLOR_BGR2RGB))
        else:
            q_pil, q_cv = self._render_image(query_img_input)

        q_feats = self._compute_features(q_pil, q_cv)
        q_deep = q_feats['deep_feat']
        q_ph = q_feats['phash']
        q_dh = q_feats['dhash']
        q_ah = q_feats['ahash']
        q_wh = q_feats['whash']
        q_hist = q_feats['hist']
        q_thumb = q_feats['thumb']

        # Vectorized cosine similarities across all indexed images
        if self.deep_matrix is not None and np.linalg.norm(q_deep) > 0:
            deep_similarities = np.dot(self.deep_matrix, q_deep) * 100.0
            deep_similarities = np.clip(deep_similarities, 0.0, 100.0)
        else:
            deep_similarities = np.zeros(len(self.records), dtype=np.float32)

        results = []

        for idx, entry in enumerate(self.records):
            deep_sim = float(deep_similarities[idx])

            # Perceptual hash distances
            d_dh = q_dh - entry['dhash']
            d_ph = q_ph - entry['phash']
            d_ah = q_ah - entry['ahash']
            d_wh = q_wh - entry['whash']

            sim_dh = max(0.0, (1.0 - d_dh / 64.0)) * 100.0
            sim_ph = max(0.0, (1.0 - d_ph / 64.0)) * 100.0
            sim_ah = max(0.0, (1.0 - d_ah / 64.0)) * 100.0
            sim_wh = max(0.0, (1.0 - d_wh / 64.0)) * 100.0

            hash_avg = (sim_dh + sim_ph) / 2.0
            struct_score = max(sim_dh, sim_ph, hash_avg)

            # Spatial NCC on 64x64 thumbnail
            res_ncc = cv2.matchTemplate(q_thumb, entry['thumb'], cv2.TM_CCOEFF_NORMED)
            ncc_score = max(0.0, float(res_ncc[0][0])) * 100.0

            # Color histogram correlation
            hist_corr = cv2.compareHist(
                q_hist.reshape((8, 8, 8)),
                entry['hist'].reshape((8, 8, 8)),
                cv2.HISTCMP_CORREL
            )
            hist_score = max(0.0, float(hist_corr)) * 100.0

            # Fused similarity:
            # 1. Deep similarity is highly accurate for real photos, scenes, variations
            # 2. Perceptual hashes are highly accurate for exact crops, logos, graphics
            # 3. Spatial NCC & Hist provide verification
            candidate_scores = []

            # Deep feature score (valid if struct is not completely discordant)
            if deep_sim > 70.0 and struct_score > 50.0:
                candidate_scores.append(deep_sim)
                candidate_scores.append(0.6 * deep_sim + 0.4 * struct_score)

            # Structural score
            if struct_score >= 72.0:
                candidate_scores.append(struct_score)
                if ncc_score > 70.0:
                    candidate_scores.append(0.5 * struct_score + 0.5 * ncc_score)
                if hist_score > 70.0:
                    candidate_scores.append(0.6 * struct_score + 0.4 * hist_score)

            # If both agree:
            if struct_score > 75.0 and deep_sim > 75.0:
                candidate_scores.append(max(struct_score, deep_sim))

            final_score = max(candidate_scores) if candidate_scores else max(struct_score * 0.7, deep_sim * 0.7)

            if final_score >= threshold:
                results.append({
                    'score': round(final_score, 1),
                    'match_type': 'visual',
                    'score_details': {
                        'deep_sim': round(deep_sim, 1),
                        'dhash': round(sim_dh, 1),
                        'phash': round(sim_ph, 1),
                        'ncc': round(ncc_score, 1),
                        'hist': round(hist_score, 1)
                    },
                    'meta': entry['meta']
                })

        results.sort(key=lambda x: x['score'], reverse=True)
        results = results[:top_k]
        elapsed_ms = (time.time() - t0) * 1000.0

        return {
            'query_type': 'visual',
            'query_width': q_pil.width,
            'query_height': q_pil.height,
            'threshold': threshold,
            'total_indexed': len(self.records),
            'match_count': len(results),
            'elapsed_ms': round(elapsed_ms, 2),
            'results': results
        }

    # Backward compatibility
    search = search_visual

    def search_text(self, text_query, threshold=60.0, top_k=50):
        """
        Search image without screenshot by text query:
        Matches Drupal Media Name, Filename, Media ID (MID), Alt Text, Bundle.
        """
        t0 = time.time()
        q_raw = text_query.strip()
        q_lower = q_raw.lower()
        q_tokens = [t for t in re.split(r'[\s\-_,.]+', q_lower) if len(t) > 1]

        results = []

        # Check if query is numeric (Media ID search like "824")
        is_num = q_raw.isdigit()
        target_mid = int(q_raw) if is_num else None

        for entry in self.records:
            meta = entry['meta']
            mid = meta.get('media_id')
            name = (meta.get('name') or '').lower()
            filename = (meta.get('filename') or '').lower()
            alt = (meta.get('alt') or '').lower()
            bundle = (meta.get('bundle') or '').lower()

            score = 0.0
            reasons = []

            # 1. Exact Media ID match
            if target_mid is not None and mid == target_mid:
                score = 100.0
                reasons.append("Exact Media ID match")
            elif is_num and str(mid) == q_raw:
                score = 100.0
                reasons.append("Exact Media ID match")
            else:
                # 2. Exact Title / Name match
                if q_lower == name:
                    score = 99.0
                    reasons.append("Exact title match")
                elif q_lower in name:
                    score = max(score, 90.0 + (len(q_lower) / max(1, len(name))) * 8.0)
                    reasons.append("Title substring match")

                # 3. Filename match
                if q_lower in filename:
                    score = max(score, 88.0)
                    reasons.append("Filename match")

                # 4. Token overlap match
                if q_tokens:
                    token_hits = sum(1 for t in q_tokens if t in name or t in filename or t in alt)
                    if token_hits > 0:
                        token_ratio = token_hits / len(q_tokens)
                        token_score = 65.0 + (token_ratio * 30.0)
                        if token_score > score:
                            score = token_score
                            reasons.append(f"{token_hits}/{len(q_tokens)} keyword match")

                # 5. Alt text match
                if alt and q_lower in alt:
                    score = max(score, 82.0)
                    reasons.append("Alt text match")

            score = min(100.0, score)

            if score >= threshold:
                results.append({
                    'score': round(score, 1),
                    'match_type': 'text',
                    'match_reason': ", ".join(reasons),
                    'meta': meta
                })

        results.sort(key=lambda x: x['score'], reverse=True)
        results = results[:top_k]
        elapsed_ms = (time.time() - t0) * 1000.0

        return {
            'query_type': 'text',
            'query_text': q_raw,
            'threshold': threshold,
            'total_indexed': len(self.records),
            'match_count': len(results),
            'elapsed_ms': round(elapsed_ms, 2),
            'results': results
        }

    def search_by_url(self, image_url, threshold=80.0, top_k=50):
        """
        Search image without screenshot by URL:
        Downloads remote image and performs visual search.
        """
        req = urllib.request.Request(image_url, headers={
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36'
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            img_bytes = resp.read()

        res = self.search_visual(img_bytes, threshold=threshold, top_k=top_k)
        res['query_type'] = 'url'
        res['query_url'] = image_url
        return res

    def find_similar_by_id(self, media_id, threshold=70.0, top_k=20):
        """
        Find visually similar images for an existing image in the database.
        """
        target_entry = None
        try:
            mid = int(media_id)
        except ValueError:
            mid = media_id

        for entry in self.records:
            if entry['meta'].get('media_id') == mid:
                target_entry = entry
                break

        if not target_entry:
            return {'error': f'Media ID {media_id} not found in database', 'results': []}

        rel_path = target_entry['meta']['local_rel_path']
        full_path = os.path.join(BASE_DIR, rel_path) if not os.path.isabs(rel_path) else rel_path

        res = self.search_visual(full_path, threshold=threshold, top_k=top_k + 1)
        # Exclude the query item itself
        filtered = [r for r in res['results'] if str(r['meta'].get('media_id')) != str(mid)]
        res['results'] = filtered[:top_k]
        res['match_count'] = len(filtered)
        res['query_type'] = 'similar'
        res['query_media_id'] = mid
        res['query_name'] = target_entry['meta'].get('name')
        return res

if __name__ == "__main__":
    engine = ImageSearchEngine()
    print("Testing text search for 'smiling':")
    res = engine.search_text('smiling')
    print(f"Found {res['match_count']} matches in {res['elapsed_ms']}ms.")
