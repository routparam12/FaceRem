"""
Face embedding, quality evaluation, and organization-scoped vector search.

Recognition is a server responsibility. All inference is offloaded from the async event loop.
Embeddings are L2-normalized 512-d ArcFace vectors.
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from dataclasses import dataclass
from functools import lru_cache
import io
import logging

import numpy as np
from PIL import Image, ImageOps, UnidentifiedImageError
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .models import Employee, FaceProfile
from .security import AppError

logger = logging.getLogger("faceattend.face")
settings = get_settings()

_executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)


@dataclass(frozen=True)
class QualityMetrics:
    passed: bool
    reason: str
    det_score: float
    face_width: int
    face_height: int
    blur_score: float
    brightness: float
    yaw: float
    pitch: float
    roll: float
    ear: float
    vector: list[float]
    bbox: tuple[float, float, float, float] | None = None


@dataclass(frozen=True)
class Embedding:
    vector: list[float]
    quality: float
    model_name: str
    model_version: str
    pose: str = "FRONT"
    yaw: float = 0.0
    ear: float = 0.3
    bbox: tuple[float, float, float, float] | None = None


def compute_blur_score(image: Image.Image) -> float:
    """Computes Laplacian variance as an edge-density / sharpness indicator."""
    gray = np.array(image.convert("L"), dtype=np.float32)
    if gray.shape[0] < 3 or gray.shape[1] < 3:
        return 0.0
    laplacian = (
        -4 * gray[1:-1, 1:-1]
        + gray[:-2, 1:-1] + gray[2:, 1:-1]
        + gray[1:-1, :-2] + gray[1:-1, 2:]
    )
    return float(laplacian.var())


def compute_eye_aspect_ratio(landmarks: np.ndarray) -> float:
    """Computes Eye Aspect Ratio (EAR) from 106-point facial landmarks."""
    if landmarks is None or len(landmarks) < 106:
        return 0.3
    # Left eye: corners 35, 39; eyelids 37, 41
    left_v = np.linalg.norm(landmarks[37] - landmarks[41])
    left_h = np.linalg.norm(landmarks[35] - landmarks[39])
    left_ear = left_v / (left_h + 1e-6)

    # Right eye: corners 89, 93; eyelids 91, 95
    right_v = np.linalg.norm(landmarks[91] - landmarks[95])
    right_h = np.linalg.norm(landmarks[89] - landmarks[93])
    right_ear = right_v / (right_h + 1e-6)

    return float((left_ear + right_ear) / 2.0)


class StubEngine:
    """
    A normalised grayscale descriptor for dev/test suites.
    Simulates quality and pose evaluation without downloading models.
    """

    model_name = "stub-gray16"
    model_version = "0"
    default_threshold = 0.62
    default_margin = 0.05

    def extract_frame_metrics(self, image_bytes: bytes) -> QualityMetrics:
        try:
            image = Image.open(io.BytesIO(image_bytes))
            image = ImageOps.exif_transpose(image).convert("L")
        except Exception:
            raise AppError("FACE_QUALITY_LOW", "The uploaded image could not be read.", 422, reason="CORRUPT")

        # Deterministic simulation for test suites based on image width
        if image.width == 111:
            raise AppError("MULTIPLE_FACES", "More than one face was detected.", 422, reason="MULTIPLE_FACES")
        if image.width == 112:
            raise AppError("FACE_NOT_FOUND", "No face was detected in the frame.", 422, reason="NO_FACE")
        if image.width == 113:
            raise AppError("FACE_QUALITY_LOW", "Frame is too blurry.", 422, reason="BLURRY")

        pixels = np.asarray(image, dtype=np.float32)
        if pixels.size == 0 or pixels.std() < 1e-4:
            raise AppError("FACE_QUALITY_LOW", "The image is blank or has no detail.", 422, reason="BLANK")

        resized = image.resize((16, 16))
        px16 = np.asarray(resized, dtype=np.float32).flatten()
        centred = px16 - px16.mean()
        norm = float(np.linalg.norm(centred))
        vec = (centred / max(norm, 1e-6)).tolist()

        return QualityMetrics(
            passed=True,
            reason="VALID",
            det_score=0.99,
            face_width=image.width,
            face_height=image.height,
            blur_score=50.0,
            brightness=float(pixels.mean()),
            yaw=0.0,
            pitch=0.0,
            roll=0.0,
            ear=0.3,
            vector=vec,
            bbox=(0.0, 0.0, float(image.width), float(image.height)),
        )

    def extract_burst_metrics(
        self,
        burst_bytes: bytes,
        tracking_bbox: tuple[float, float, float, float] | None = None,
    ) -> QualityMetrics:
        return self.extract_frame_metrics(burst_bytes)

    def embed(self, image_bytes: bytes, expected_pose: str | None = None) -> Embedding:
        try:
            image = Image.open(io.BytesIO(image_bytes))
            image = ImageOps.exif_transpose(image).convert("L")
        except Exception:
            raise AppError("FACE_QUALITY_LOW", "The uploaded image could not be read.", 422, reason="CORRUPT")

        if image.width == 111:
            raise AppError("MULTIPLE_FACES", "More than one face was detected.", 422, reason="MULTIPLE_FACES")
        if image.width == 112:
            raise AppError("FACE_NOT_FOUND", "No face was detected in the frame.", 422, reason="NO_FACE")
        if image.width == 113:
            raise AppError("FACE_QUALITY_LOW", "Frame is too blurry.", 422, reason="BLURRY")
        if image.width == 114:
            raise AppError("FACE_QUALITY_LOW", "Pose mismatch.", 422, reason="POSE_MISMATCH")

        pixels = np.asarray(image.resize((16, 16)), dtype=np.float32).flatten()
        centred = pixels - pixels.mean()
        norm = float(np.linalg.norm(centred))
        if norm < 1e-6:
            raise AppError("FACE_QUALITY_LOW", "The image is blank or has no detail.", 422, reason="BLANK")

        quality = float(min(1.0, pixels.std() / 64.0))
        pose = expected_pose or "FRONT"
        yaw = 0.0 if pose == "FRONT" else (-25.0 if pose == "LEFT" else 25.0)

        return Embedding(
            vector=(centred / norm).tolist(),
            quality=quality,
            model_name=self.model_name,
            model_version=self.model_version,
            pose=pose,
            yaw=yaw,
            bbox=(0.0, 0.0, float(image.width), float(image.height)),
        )


class InsightFaceEngine:
    """
    Real face recognition: RetinaFace detection + 106-point alignment + ArcFace 512-d embeddings.
    """

    model_name = "buffalo_l"
    model_version = "1"
    default_threshold = 0.45
    default_margin = 0.08
    _PAD_RATIO = 0.5

    def __init__(self) -> None:
        from insightface.app import FaceAnalysis

        self.model_name = settings.insightface_model_name
        self._app = FaceAnalysis(
            name=self.model_name,
            allowed_modules=["detection", "recognition", "landmark_3d_68", "landmark_2d_106"],
        )
        self._app.prepare(ctx_id=-1, det_size=(320, 320))

    def _detect(self, image: Image.Image) -> list:
        rgb = np.asarray(image)
        # InsightFace expects contiguous BGR array
        return self._app.get(np.ascontiguousarray(rgb[:, :, ::-1]))

    def extract_burst_metrics(
        self,
        burst_bytes: bytes,
        tracking_bbox: tuple[float, float, float, float] | None = None,
    ) -> QualityMetrics:
        """
        Fast-path metric extraction for burst liveness frames.
        Crops ROI around primary face bounding box with 35% margin to avoid full detection.
        Falls back to downscaled burst frame if face moves outside tracking window.
        """
        try:
            image = Image.open(io.BytesIO(burst_bytes))
            image = ImageOps.exif_transpose(image).convert("RGB")
        except (UnidentifiedImageError, OSError, Exception):
            raise AppError("FACE_QUALITY_LOW", "The uploaded burst image could not be read.", 422, reason="CORRUPT")

        # Fast tracking path: if primary face bbox is known, crop the ROI with 35% margin
        if tracking_bbox is not None:
            x1, y1, x2, y2 = tracking_bbox
            w, h = x2 - x1, y2 - y1
            pad = 0.35
            crop_box = (
                max(0, int(x1 - w * pad)),
                max(0, int(y1 - h * pad)),
                min(image.width, int(x2 + w * pad)),
                min(image.height, int(y2 + h * pad)),
            )
            cropped = image.crop(crop_box)
            faces = self._detect(cropped)
            if faces:
                face = faces[0]
                pose = face.pose if hasattr(face, "pose") and face.pose is not None else [0.0, 0.0, 0.0]
                landmarks = getattr(face, "landmark_2d_106", None)
                ear = compute_eye_aspect_ratio(landmarks)
                vector = np.asarray(face.normed_embedding, dtype=np.float32)
                norm = float(np.linalg.norm(vector))
                if norm > 1e-6:
                    vector = vector / norm
                return QualityMetrics(
                    passed=True,
                    reason="VALID",
                    det_score=float(face.det_score),
                    face_width=int(face.bbox[2] - face.bbox[0]),
                    face_height=int(face.bbox[3] - face.bbox[1]),
                    blur_score=50.0,
                    brightness=128.0,
                    yaw=float(pose[1]),
                    pitch=float(pose[0]),
                    roll=float(pose[2]),
                    ear=ear,
                    vector=vector.tolist(),
                    bbox=tracking_bbox,
                )

        # Fallback: downscale full burst frame to max 320px
        max_dim = 320
        if max(image.size) > max_dim:
            scale = max_dim / max(image.size)
            downscaled = image.resize((int(image.width * scale), int(image.height * scale)), Image.BILINEAR)
            faces = self._detect(downscaled)
        else:
            faces = self._detect(image)

        if not faces:
            raise AppError("FACE_NOT_FOUND", "No face was detected in burst frame.", 422, reason="NO_FACE")

        face = faces[0]
        pose = face.pose if hasattr(face, "pose") and face.pose is not None else [0.0, 0.0, 0.0]
        landmarks = getattr(face, "landmark_2d_106", None)
        ear = compute_eye_aspect_ratio(landmarks)
        vector = np.asarray(face.normed_embedding, dtype=np.float32)
        norm = float(np.linalg.norm(vector))
        if norm > 1e-6:
            vector = vector / norm
        return QualityMetrics(
            passed=True,
            reason="VALID",
            det_score=float(face.det_score),
            face_width=int(face.bbox[2] - face.bbox[0]),
            face_height=int(face.bbox[3] - face.bbox[1]),
            blur_score=50.0,
            brightness=128.0,
            yaw=float(pose[1]),
            pitch=float(pose[0]),
            roll=float(pose[2]),
            ear=ear,
            vector=vector.tolist(),
            bbox=None,
        )

    def extract_frame_metrics(self, image_bytes: bytes) -> QualityMetrics:
        try:
            image = Image.open(io.BytesIO(image_bytes))
            image = ImageOps.exif_transpose(image).convert("RGB")
        except (UnidentifiedImageError, OSError, Exception):
            raise AppError("FACE_QUALITY_LOW", "The uploaded image could not be read.", 422, reason="CORRUPT")

        # 1. Blur & Brightness on full frame
        blur_score = compute_blur_score(image)
        if blur_score < 25.0:
            raise AppError("FACE_QUALITY_LOW", "Frame is too blurry.", 422, reason="BLURRY")

        gray = np.array(image.convert("L"), dtype=np.float32)
        brightness = float(gray.mean())
        if brightness < 30.0:
            raise AppError("FACE_QUALITY_LOW", "Frame is too dark.", 422, reason="TOO_DARK")
        if brightness > 235.0:
            raise AppError("FACE_QUALITY_LOW", "Frame is overexposed.", 422, reason="TOO_BRIGHT")

        # 2. Face detection
        faces = self._detect(image)
        if not faces:
            border = int(min(image.size) * self._PAD_RATIO)
            faces = self._detect(ImageOps.expand(image, border=border, fill=(128, 128, 128)))

        if not faces:
            raise AppError("FACE_NOT_FOUND", "No face was detected in the frame.", 422, reason="NO_FACE")
        if len(faces) > 1:
            raise AppError("MULTIPLE_FACES", "More than one face was detected.", 422, reason="MULTIPLE_FACES")

        face = faces[0]

        # 3. Size check
        bbox = face.bbox
        w = int(bbox[2] - bbox[0])
        h = int(bbox[3] - bbox[1])
        if w < 50 or h < 50:
            raise AppError("FACE_QUALITY_LOW", "Face size is too small in the frame (minimum 50x50 required).", 422, reason="FACE_TOO_SMALL")

        # 4. Confidence check
        det_score = float(face.det_score)
        if det_score < 0.60:
            raise AppError("FACE_QUALITY_LOW", "Face detection confidence is too low.", 422, reason="LOW_DETECTION_SCORE")

        # 5. Pose angles
        pose = face.pose if hasattr(face, "pose") and face.pose is not None else [0.0, 0.0, 0.0]
        pitch = float(pose[0])
        yaw = float(pose[1])
        roll = float(pose[2])

        if abs(pitch) > 45.0 or abs(roll) > 40.0:
            raise AppError("FACE_QUALITY_LOW", "Head tilt is too extreme.", 422, reason="EXTREME_POSE")

        # 6. Eye Aspect Ratio
        landmarks = getattr(face, "landmark_2d_106", None)
        ear = compute_eye_aspect_ratio(landmarks)

        # 7. Embedding
        vector = np.asarray(face.normed_embedding, dtype=np.float32)
        norm = float(np.linalg.norm(vector))
        if norm > 1e-6:
            vector = vector / norm

        return QualityMetrics(
            passed=True,
            reason="VALID",
            det_score=det_score,
            face_width=w,
            face_height=h,
            blur_score=blur_score,
            brightness=brightness,
            yaw=yaw,
            pitch=pitch,
            roll=roll,
            ear=ear,
            vector=vector.tolist(),
            bbox=(float(bbox[0]), float(bbox[1]), float(bbox[2]), float(bbox[3])),
        )

    def embed(self, image_bytes: bytes, expected_pose: str | None = None) -> Embedding:
        metrics = self.extract_frame_metrics(image_bytes)

        # Classify pose by head yaw
        # InsightFace yaw: near 0 is front; positive / negative correspond to left / right
        yaw = metrics.yaw
        if abs(yaw) <= 12.0:
            detected_pose = "FRONT"
        elif yaw <= -14.0:
            detected_pose = "LEFT"
        elif yaw >= 14.0:
            detected_pose = "RIGHT"
        else:
            detected_pose = "FRONT"

        if expected_pose is not None:
            expected_pose = expected_pose.strip().upper()
            if expected_pose == "FRONT" and abs(yaw) > 15.0:
                raise AppError("FACE_QUALITY_LOW", f"Expected FRONT pose, but detected turned face (yaw={yaw:.1f}°).", 422, reason="POSE_MISMATCH")
            if expected_pose == "LEFT" and yaw > -10.0:
                raise AppError("FACE_QUALITY_LOW", f"Expected LEFT pose, but head is not turned sufficiently to the left (yaw={yaw:.1f}°).", 422, reason="POSE_MISMATCH")
            if expected_pose == "RIGHT" and yaw < 10.0:
                raise AppError("FACE_QUALITY_LOW", f"Expected RIGHT pose, but head is not turned sufficiently to the right (yaw={yaw:.1f}°).", 422, reason="POSE_MISMATCH")

        return Embedding(
            vector=metrics.vector,
            quality=metrics.det_score,
            model_name=self.model_name,
            model_version=self.model_version,
            pose=detected_pose,
            yaw=yaw,
            ear=metrics.ear,
            bbox=metrics.bbox,
        )


@lru_cache
def get_engine():
    if settings.face_engine == "insightface":
        return InsightFaceEngine()
    return StubEngine()


async def embed_async(image_bytes: bytes, expected_pose: str | None = None) -> Embedding:
    """Runs CPU inference off the async event loop using a worker thread."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(_executor, get_engine().embed, image_bytes, expected_pose)


def warmup_engine() -> None:
    """Pre-loads ONNX models and execution providers at startup."""
    try:
        engine = get_engine()
        dummy_img = Image.new("RGB", (640, 640), (128, 128, 128))
        buf = io.BytesIO()
        dummy_img.save(buf, format="JPEG")
        if isinstance(engine, InsightFaceEngine):
            engine._detect(dummy_img)
        logger.info("Face recognition engine warmed up successfully.")
    except Exception as exc:
        logger.warning(f"Engine warm up failed: {exc}")


@dataclass(frozen=True)
class Match:
    employee: Employee
    confidence: float


def find_best_match(db: Session, organization_id: str, vector: list[float]) -> Match | None:
    """
    Organization-scoped nearest-neighbour matching using employee-level max similarity and margin rule.
    Filters by organization BEFORE computing similarity.
    """
    engine = get_engine()

    # Query all active face profiles for this organization matching current engine version
    rows = db.execute(
        select(FaceProfile, Employee)
        .join(Employee, Employee.id == FaceProfile.employee_id)
        .where(
            FaceProfile.organization_id == organization_id,
            FaceProfile.revoked_at.is_(None),
            Employee.is_active.is_(True),
            FaceProfile.model_name == engine.model_name,
            FaceProfile.model_version == engine.model_version,
        )
    ).all()

    if not rows:
        return None

    query = np.asarray(vector, dtype=np.float32)
    norm = float(np.linalg.norm(query))
    if norm > 1e-6:
        query = query / norm

    # Group profiles by employee id to find maximum similarity across that person's embeddings
    emp_map: dict[str, Employee] = {}
    emp_scores: dict[str, float] = {}

    for profile, employee in rows:
        stored_vec = profile.embedding_vec if profile.embedding_vec is not None else profile.embedding
        if not stored_vec or len(stored_vec) != len(query):
            continue

        s_arr = np.asarray(stored_vec, dtype=np.float32)
        s_norm = float(np.linalg.norm(s_arr))
        if s_norm > 1e-6:
            s_arr = s_arr / s_norm

        sim = float(np.dot(s_arr, query))
        emp_id = employee.id
        emp_map[emp_id] = employee

        if emp_id not in emp_scores or sim > emp_scores[emp_id]:
            emp_scores[emp_id] = sim

    if not emp_scores:
        return None

    # Sort employees by maximum similarity descending
    ranked = sorted(emp_scores.items(), key=lambda kv: kv[1], reverse=True)
    top_emp_id, top_score = ranked[0]
    threshold = match_threshold()
    margin = match_margin()

    # Must exceed absolute threshold
    if top_score < threshold:
        return None

    # Margin rule: if multiple candidates, top score must separate from second best by >= margin
    if len(ranked) > 1:
        second_emp_id, second_score = ranked[1]
        if (top_score - second_score) < margin:
            logger.info(f"Margin rule rejected match: top={top_score:.3f}, second={second_score:.3f}, margin={margin}")
            return None

    return Match(employee=emp_map[top_emp_id], confidence=top_score)


def match_threshold() -> float:
    configured = settings.face_match_threshold
    return configured if configured is not None else get_engine().default_threshold


def match_margin() -> float:
    configured = settings.face_match_margin
    return configured if configured is not None else get_engine().default_margin
