#!/usr/bin/env python3
"""
Threshold Calibration Tool for FaceRem ArcFace Engine.

Evaluates genuine and impostor similarity distributions on biometric datasets,
computes FAR/FRR curves and Equal Error Rate (EER), and recommends production thresholds
and margin parameters for a target False Acceptance Rate (default 0.001 / 0.1%).
"""

import argparse
from dataclasses import dataclass
import io
import itertools
from pathlib import Path
import sys

import numpy as np
from PIL import Image

# Ensure backend root is on sys.path
backend_root = Path(__file__).resolve().parents[1]
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from app.face import get_engine  # noqa: E402


@dataclass
class CalibrationResult:
    target_far: float
    recommended_threshold: float
    recommended_margin: float
    eer: float
    eer_threshold: float
    num_identities: int
    num_images: int
    num_genuine_pairs: int
    num_impostor_pairs: int
    sweep_table: list[dict]


def load_dataset(dataset_dir: Path) -> dict[str, list[bytes]]:
    """Loads images grouped by identity from folder structure: dataset/<identity_id>/*.jpg"""
    identities: dict[str, list[bytes]] = {}
    valid_exts = {".jpg", ".jpeg", ".png", ".webp"}

    for person_dir in dataset_dir.iterdir():
        if not person_dir.is_dir():
            continue
        person_name = person_dir.name
        images = []
        for img_path in person_dir.iterdir():
            if img_path.is_file() and img_path.suffix.lower() in valid_exts:
                try:
                    images.append(img_path.read_bytes())
                except Exception as exc:
                    print(f"Warning: could not read {img_path}: {exc}", file=sys.stderr)
        if images:
            identities[person_name] = images

    return identities


def compute_distributions(
    identities: dict[str, list[bytes]]
) -> tuple[np.ndarray, np.ndarray, float]:
    """
    Computes genuine and impostor cosine similarity distributions.
    Also computes 95th percentile impostor gap for margin recommendation.
    """
    engine = get_engine()
    identity_embeddings: dict[str, list[np.ndarray]] = {}

    print(f"Extracting embeddings for {len(identities)} identities...")
    for person_id, img_list in identities.items():
        embs = []
        for img_bytes in img_list:
            try:
                emb = engine.embed(img_bytes)
                vec = np.asarray(emb.vector, dtype=np.float32)
                norm = float(np.linalg.norm(vec))
                if norm > 1e-6:
                    vec = vec / norm
                embs.append(vec)
            except Exception as exc:
                print(f"Skipping frame for {person_id}: {exc}", file=sys.stderr)
        if embs:
            identity_embeddings[person_id] = embs

    genuine_scores: list[float] = []
    impostor_scores: list[float] = []

    # 1. Genuine pairs (same identity)
    for person_id, embs in identity_embeddings.items():
        if len(embs) < 2:
            continue
        for v1, v2 in itertools.combinations(embs, 2):
            sim = float(np.dot(v1, v2))
            genuine_scores.append(sim)

    # 2. Impostor pairs (different identities)
    person_ids = list(identity_embeddings.keys())
    for idx1 in range(len(person_ids)):
        for idx2 in range(idx1 + 1, len(person_ids)):
            embs1 = identity_embeddings[person_ids[idx1]]
            embs2 = identity_embeddings[person_ids[idx2]]
            for v1 in embs1:
                for v2 in embs2:
                    sim = float(np.dot(v1, v2))
                    impostor_scores.append(sim)

    # Margin estimation: difference between top genuine and highest impostor match
    impostor_arr = np.asarray(impostor_scores, dtype=np.float32)
    margin_recommendation = 0.08
    if len(impostor_arr) > 0:
        # 99th percentile of impostor similarity vs baseline
        p99_impostor = float(np.percentile(impostor_arr, 99))
        p999_impostor = float(np.percentile(impostor_arr, 99.9))
        margin_recommendation = max(0.05, min(0.15, (p999_impostor - p99_impostor) * 1.5))

    return (
        np.asarray(genuine_scores, dtype=np.float32),
        impostor_arr,
        float(margin_recommendation),
    )


def sweep_thresholds(
    genuine: np.ndarray,
    impostor: np.ndarray,
    target_far: float = 0.001,
    margin_rec: float = 0.08,
) -> CalibrationResult:
    """Performs threshold sweep from 0.0 to 1.0 to find FAR, FRR, EER and recommended threshold."""
    thresholds = np.linspace(0.0, 1.0, 201)
    sweep_table = []

    best_eer_diff = float("inf")
    eer_val = 0.0
    eer_thresh = 0.5
    recommended_thresh = 0.5
    found_target_far = False

    total_gen = len(genuine) if len(genuine) > 0 else 1
    total_imp = len(impostor) if len(impostor) > 0 else 1

    for t in thresholds:
        # False Accept: impostor score >= threshold
        fa_count = int(np.sum(impostor >= t))
        far = fa_count / total_imp

        # False Reject: genuine score < threshold
        fr_count = int(np.sum(genuine < t))
        frr = fr_count / total_gen

        sweep_table.append({
            "threshold": float(t),
            "far": float(far),
            "frr": float(frr),
            "fa_count": fa_count,
            "fr_count": fr_count,
        })

        # Track EER (|FAR - FRR| minimum)
        diff = abs(far - frr)
        if diff < best_eer_diff:
            best_eer_diff = diff
            eer_val = (far + frr) / 2.0
            eer_thresh = float(t)

        # Track recommended threshold for target FAR (first threshold where FAR <= target_far)
        if not found_target_far and far <= target_far:
            recommended_thresh = float(t)
            found_target_far = True

    if not found_target_far:
        recommended_thresh = float(thresholds[-1])

    return CalibrationResult(
        target_far=target_far,
        recommended_threshold=recommended_thresh,
        recommended_margin=round(margin_rec, 3),
        eer=eer_val,
        eer_threshold=eer_thresh,
        num_identities=0,
        num_images=0,
        num_genuine_pairs=len(genuine),
        num_impostor_pairs=len(impostor),
        sweep_table=sweep_table,
    )


def print_report(result: CalibrationResult) -> None:
    print("\n" + "=" * 70)
    print("           FACEREM THRESHOLD CALIBRATION REPORT")
    print("=" * 70)
    print(f"Total Genuine Pairs Evaluated : {result.num_genuine_pairs:,}")
    print(f"Total Impostor Pairs Evaluated: {result.num_impostor_pairs:,}")
    print(f"Equal Error Rate (EER)        : {result.eer * 100:.3f}% at threshold {result.eer_threshold:.3f}")
    print(f"Target FAR                    : {result.target_far * 100:.4f}% ({result.target_far})")
    print(f"Recommended Match Threshold   : {result.recommended_threshold:.3f}")
    print(f"Recommended Match Margin      : {result.recommended_margin:.3f}")
    print("-" * 70)

    print("\nThreshold Sweep Sampling:")
    print(f"{'Threshold':>10} | {'FAR (%)':>12} | {'FRR (%)':>12} | {'Notes':<20}")
    print("-" * 60)

    sample_thresholds = [0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70]
    for row in result.sweep_table:
        t = row["threshold"]
        # Print samples close to landmarks
        is_landmark = any(abs(t - st) < 0.002 for st in sample_thresholds)
        is_rec = abs(t - result.recommended_threshold) < 0.002
        is_eer = abs(t - result.eer_threshold) < 0.002

        if is_landmark or is_rec or is_eer:
            notes = []
            if is_eer:
                notes.append("EER")
            if is_rec:
                notes.append("TARGET FAR (REC)")
            note_str = ", ".join(notes)
            print(f"{t:10.2f} | {row['far'] * 100:11.4f}% | {row['frr'] * 100:11.4f}% | {note_str:<20}")

    print("\n" + "=" * 70)
    print("RECOMMENDED PRODUCTION CONFIGURATION (.env)")
    print("=" * 70)
    print(f"FACE_MATCH_THRESHOLD={result.recommended_threshold:.3f}")
    print(f"FACE_MATCH_MARGIN={result.recommended_margin:.3f}")
    print("=" * 70 + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Calibrate biometric thresholds for FaceRem.")
    parser.add_argument(
        "--dataset",
        type=Path,
        help="Path to dataset directory containing subdirectories per identity.",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        help="Path to precomputed pairs CSV (columns: identity_a, identity_b, similarity).",
    )
    parser.add_argument(
        "--target-far",
        type=float,
        default=0.001,
        help="Target False Acceptance Rate (default: 0.001 / 0.1%%).",
    )
    args = parser.parse_args()

    if not args.dataset and not args.csv:
        parser.error("Either --dataset or --csv must be specified.")

    if args.dataset:
        if not args.dataset.exists() or not args.dataset.is_dir():
            print(f"Error: Dataset directory does not exist: {args.dataset}", file=sys.stderr)
            sys.exit(1)

        identities = load_dataset(args.dataset)
        num_identities = len(identities)
        total_images = sum(len(imgs) for imgs in identities.values())
        images_per_id = [len(imgs) for imgs in identities.values()]
        avg_images = total_images / max(num_identities, 1)

        # Statistical validity warnings
        if num_identities < 20:
            print(
                f"\n[WARNING] Dataset has only {num_identities} identities (minimum 20 recommended). "
                "Confidence intervals for FAR and EER may be statistically unreliable.",
                file=sys.stderr,
            )
        if any(c < 3 for c in images_per_id):
            low_count = sum(1 for c in images_per_id if c < 3)
            print(
                f"\n[WARNING] {low_count} identities have fewer than 3 images (minimum 3 required for multi-pose analysis). "
                "Intra-class variance may be underestimated.",
                file=sys.stderr,
            )

        genuine, impostor, margin_rec = compute_distributions(identities)
    else:
        # Load precomputed CSV
        import csv
        genuine_list = []
        impostor_list = []
        with open(args.csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                id_a = row.get("identity_a") or row.get("id1")
                id_b = row.get("identity_b") or row.get("id2")
                sim = float(row.get("similarity") or row.get("score"))
                if id_a == id_b:
                    genuine_list.append(sim)
                else:
                    impostor_list.append(sim)
        genuine = np.asarray(genuine_list, dtype=np.float32)
        impostor = np.asarray(impostor_list, dtype=np.float32)
        margin_rec = 0.08

    result = sweep_thresholds(genuine, impostor, target_far=args.target_far, margin_rec=margin_rec)
    print_report(result)


if __name__ == "__main__":
    main()

