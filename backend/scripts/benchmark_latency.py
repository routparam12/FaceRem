"""
Comprehensive Hardware Scan Latency Benchmark for FaceAttend Face Pipeline.
Profiles warmed process (N=50, discarding first 5 runs) across all pipeline stages.
Compares buffalo_l and buffalo_s architectures.
"""

import io
import os
import platform
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ.setdefault("JWT_SECRET", "benchmark-secret-that-is-long-enough-for-hs256-abcdef")
os.environ.setdefault("INSIGHTFACE_MODEL_NAME", "buffalo_l")

import insightface
from app.face import InsightFaceEngine
from app.liveness import ChallengeLivenessService


def get_hardware_info():
    uname = platform.uname()
    total_ram_gb = 16.0
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        c_ulonglong = ctypes.c_ulonglong
        class MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ('dwLength', ctypes.c_ulong),
                ('dwMemoryLoad', ctypes.c_ulong),
                ('ullTotalPhys', c_ulonglong),
                ('ullAvailPhys', c_ulonglong),
                ('ullTotalPageFile', c_ulonglong),
                ('ullAvailPageFile', c_ulonglong),
                ('ullTotalVirtual', c_ulonglong),
                ('ullAvailVirtual', c_ulonglong),
                ('ullAvailExtendedVirtual', c_ulonglong),
            ]
        stat = MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
        kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
        total_ram_gb = round(stat.ullTotalPhys / (1024 ** 3), 2)
    except Exception:
        pass

    return {
        "system": f"{uname.system} {uname.release} ({uname.version})",
        "cpu": uname.processor or platform.processor(),
        "logical_cores": os.cpu_count() or 1,
        "ram_gb": total_ram_gb,
        "python": sys.version.split()[0],
    }


def stats(arr):
    return {
        "mean": float(np.mean(arr)),
        "median": float(np.median(arr)),
        "p95": float(np.percentile(arr, 95)),
        "min": float(np.min(arr)),
        "max": float(np.max(arr)),
    }


def run_benchmark_for_model(model_name: str, single_face_bytes: bytes, n_runs: int = 50, n_warmup: int = 5):
    print("\n" + "=" * 70, flush=True)
    print(f"BENCHMARKING MODEL: {model_name} (N={n_runs} warmed iterations, {n_warmup} discarded warmup)", flush=True)
    print("=" * 70, flush=True)

    os.environ["INSIGHTFACE_MODEL_NAME"] = model_name
    from app.config import get_settings
    settings = get_settings()
    settings.insightface_model_name = model_name

    t0 = time.perf_counter()
    engine = InsightFaceEngine()
    init_ms = (time.perf_counter() - t0) * 1000
    print(f"Initialization / Cold Load: {init_ms:.1f} ms", flush=True)

    # Warmup runs (discarded)
    for w in range(n_warmup):
        engine.embed(single_face_bytes)
        engine.extract_burst_metrics(single_face_bytes, tracking_bbox=(20.0, 20.0, 200.0, 200.0))
        print(f"  Warmup {w+1}/{n_warmup} done", flush=True)

    primary_embed = engine.embed(single_face_bytes)
    tracking_bbox = primary_embed.bbox
    primary_vec = np.asarray(primary_embed.vector, dtype=np.float32)

    # 1,000 candidate database for search
    n_candidates = 1000
    candidate_db = np.random.randn(n_candidates, len(primary_vec)).astype(np.float32)
    candidate_db /= np.linalg.norm(candidate_db, axis=1, keepdims=True)

    # Profiling arrays
    det_latencies = []
    rec_latencies = []
    embed_latencies = []
    search_latencies = []
    burst1_latencies = []
    burst2_latencies = []
    liveness_total_latencies = []
    e2e_latencies = []

    for idx in range(n_runs):
        if (idx + 1) % 10 == 0 or idx == 0:
            print(f"  Iteration {idx+1}/{n_runs}...", flush=True)
        t_e2e_start = time.perf_counter()

        # Stage 1: Embed Primary Frame (Detection + Alignment + ArcFace Recognition)
        t_embed_start = time.perf_counter()
        img = Image.open(io.BytesIO(single_face_bytes)).convert("RGB")

        t_det_start = time.perf_counter()
        faces = engine._detect(img)
        t_det_end = time.perf_counter()

        t_rec_start = time.perf_counter()
        face = faces[0]
        rec_model = engine._app.models["recognition"]
        feat = rec_model.get(np.asarray(img)[:, :, ::-1], face)
        feat_norm = float(np.linalg.norm(feat))
        feat = feat / feat_norm
        t_rec_end = time.perf_counter()

        t_embed_end = time.perf_counter()

        # Stage 2: 1:1,000 Vector Similarity Search
        t_search_start = time.perf_counter()
        sims = np.dot(candidate_db, feat)
        best_match_idx = int(np.argmax(sims))
        best_sim = float(sims[best_match_idx])
        t_search_end = time.perf_counter()

        # Stage 3: Burst Frame 1 Processing (Using Tracking BBox ROI)
        t_b1_start = time.perf_counter()
        m1 = engine.extract_burst_metrics(single_face_bytes, tracking_bbox=tracking_bbox)
        sim1 = float(np.dot(feat, np.asarray(m1.vector, dtype=np.float32)))
        t_b1_end = time.perf_counter()

        # Stage 4: Burst Frame 2 Processing (Using Tracking BBox ROI)
        t_b2_start = time.perf_counter()
        m2 = engine.extract_burst_metrics(single_face_bytes, tracking_bbox=tracking_bbox)
        sim2 = float(np.dot(feat, np.asarray(m2.vector, dtype=np.float32)))
        t_b2_end = time.perf_counter()

        t_e2e_end = time.perf_counter()

        det_ms = (t_det_end - t_det_start) * 1000
        rec_ms = (t_rec_end - t_rec_start) * 1000
        embed_ms = (t_embed_end - t_embed_start) * 1000
        search_ms = (t_search_end - t_search_start) * 1000
        b1_ms = (t_b1_end - t_b1_start) * 1000
        b2_ms = (t_b2_end - t_b2_start) * 1000
        live_ms = b1_ms + b2_ms
        e2e_ms = (t_e2e_end - t_e2e_start) * 1000

        det_latencies.append(det_ms)
        rec_latencies.append(rec_ms)
        embed_latencies.append(embed_ms)
        search_latencies.append(search_ms)
        burst1_latencies.append(b1_ms)
        burst2_latencies.append(b2_ms)
        liveness_total_latencies.append(live_ms)
        e2e_latencies.append(e2e_ms)

    s_det = stats(det_latencies)
    s_rec = stats(rec_latencies)
    s_emb = stats(embed_latencies)
    s_search = stats(search_latencies)
    s_b1 = stats(burst1_latencies)
    s_b2 = stats(burst2_latencies)
    s_live = stats(liveness_total_latencies)
    s_e2e = stats(e2e_latencies)

    print(f"\nRESULTS FOR {model_name} (All values in milliseconds):")
    print(f"{'Pipeline Stage':<34} | {'Mean':>8} | {'Median':>8} | {'p95':>8} | {'Min':>8} | {'Max':>8}")
    print("-" * 82)
    print(f"{'1. Primary Detection + Align':<34} | {s_det['mean']:>8.2f} | {s_det['median']:>8.2f} | {s_det['p95']:>8.2f} | {s_det['min']:>8.2f} | {s_det['max']:>8.2f}")
    print(f"{'2. Primary Embedding (ArcFace)':<34} | {s_rec['mean']:>8.2f} | {s_rec['median']:>8.2f} | {s_rec['p95']:>8.2f} | {s_rec['min']:>8.2f} | {s_rec['max']:>8.2f}")
    print(f"{'   Total Primary Embed (1+2)':<34} | {s_emb['mean']:>8.2f} | {s_emb['median']:>8.2f} | {s_emb['p95']:>8.2f} | {s_emb['min']:>8.2f} | {s_emb['max']:>8.2f}")
    print(f"{'3. 1:1,000 Search (NumPy Dot)':<34} | {s_search['mean']:>8.2f} | {s_search['median']:>8.2f} | {s_search['p95']:>8.2f} | {s_search['min']:>8.2f} | {s_search['max']:>8.2f}")
    print(f"{'4. Burst Frame 1 (ROI Tracking)':<34} | {s_b1['mean']:>8.2f} | {s_b1['median']:>8.2f} | {s_b1['p95']:>8.2f} | {s_b1['min']:>8.2f} | {s_b1['max']:>8.2f}")
    print(f"{'5. Burst Frame 2 (ROI Tracking)':<34} | {s_b2['mean']:>8.2f} | {s_b2['median']:>8.2f} | {s_b2['p95']:>8.2f} | {s_b2['min']:>8.2f} | {s_b2['max']:>8.2f}")
    print(f"{'   Total Liveness (4+5)':<34} | {s_live['mean']:>8.2f} | {s_live['median']:>8.2f} | {s_live['p95']:>8.2f} | {s_live['min']:>8.2f} | {s_live['max']:>8.2f}")
    print("=" * 82)
    print(f"{'TOTAL END-TO-END RECOGNITION':<34} | {s_e2e['mean']:>8.2f} | {s_e2e['median']:>8.2f} | {s_e2e['p95']:>8.2f} | {s_e2e['min']:>8.2f} | {s_e2e['max']:>8.2f}")
    print("=" * 82)

    return {
        "model": model_name,
        "det": s_det,
        "rec": s_rec,
        "emb": s_emb,
        "search": s_search,
        "b1": s_b1,
        "b2": s_b2,
        "live": s_live,
        "e2e": s_e2e,
    }


def main():
    hw = get_hardware_info()
    print("=" * 70)
    print("HARDWARE & SYSTEM SPECIFICATIONS")
    print("=" * 70)
    print(f"OS:                {hw['system']}")
    print(f"CPU:               {hw['cpu']}")
    print(f"Logical Threads:   {hw['logical_cores']}")
    print(f"Total RAM:         {hw['ram_gb']} GB")
    print(f"Python Version:    {hw['python']}")
    print("=" * 70)

    # Prepare single face image (portrait kiosk style)
    # Using InsightFace sample image cropped to single face
    samples_dir = Path(insightface.__file__).parent / "data" / "images"
    sample_path = samples_dir / "t1.jpg"
    if not sample_path.exists():
        print(f"Sample image {sample_path} not found.")
        return

    # Extract portrait face
    from app.face import InsightFaceEngine
    engine = InsightFaceEngine()
    scene = Image.open(sample_path).convert("RGB")
    detected = engine._detect(scene)
    face = sorted(detected, key=lambda f: (f.bbox[2] - f.bbox[0]) * (f.bbox[3] - f.bbox[1]), reverse=True)[0]
    x1, y1, x2, y2 = face.bbox
    w, h = x2 - x1, y2 - y1
    pad = 0.4
    crop = scene.crop((
        max(0, int(x1 - w * pad)),
        max(0, int(y1 - h * pad)),
        min(scene.width, int(x2 + w * pad)),
        min(scene.height, int(y2 + h * pad)),
    ))

    buf = io.BytesIO()
    crop.save(buf, "JPEG", quality=90)
    single_face_bytes = buf.getvalue()
    print(f"Benchmark Test Image: {crop.size[0]}x{crop.size[1]} portrait ({len(single_face_bytes)} bytes)")

    # Run for buffalo_l
    res_l = run_benchmark_for_model("buffalo_l", single_face_bytes, n_runs=50, n_warmup=5)

    # Run for buffalo_s
    res_s = run_benchmark_for_model("buffalo_s", single_face_bytes, n_runs=50, n_warmup=5)

    # Comparative Summary
    print("\n" + "=" * 82)
    print("COMPARATIVE LATENCY SUMMARY: buffalo_l vs buffalo_s (Warmed N=50)")
    print("=" * 82)
    print(f"{'Metric':<30} | {'buffalo_l Mean (ms)':<22} | {'buffalo_s Mean (ms)':<22}")
    print("-" * 82)
    print(f"{'Primary Face Detection':<30} | {res_l['det']['mean']:<22.2f} | {res_s['det']['mean']:<22.2f}")
    print(f"{'Primary ArcFace Embedding':<30} | {res_l['rec']['mean']:<22.2f} | {res_s['rec']['mean']:<22.2f}")
    print(f"{'Total Primary Embed':<30} | {res_l['emb']['mean']:<22.2f} | {res_s['emb']['mean']:<22.2f}")
    print(f"{'1:1,000 Candidate Search':<30} | {res_l['search']['mean']:<22.2f} | {res_s['search']['mean']:<22.2f}")
    print(f"{'Burst Frame 1 ROI Liveness':<30} | {res_l['b1']['mean']:<22.2f} | {res_s['b1']['mean']:<22.2f}")
    print(f"{'Burst Frame 2 ROI Liveness':<30} | {res_l['b2']['mean']:<22.2f} | {res_s['b2']['mean']:<22.2f}")
    print(f"{'Total Burst Liveness':<30} | {res_l['live']['mean']:<22.2f} | {res_s['live']['mean']:<22.2f}")
    print("-" * 82)
    print(f"{'END-TO-END TOTAL':<30} | {res_l['e2e']['mean']:<22.2f} | {res_s['e2e']['mean']:<22.2f}")
    print(f"{'END-TO-END MEDIAN':<30} | {res_l['e2e']['median']:<22.2f} | {res_s['e2e']['median']:<22.2f}")
    print(f"{'END-TO-END p95':<30} | {res_l['e2e']['p95']:<22.2f} | {res_s['e2e']['p95']:<22.2f}")
    print("=" * 82)


if __name__ == "__main__":
    main()
