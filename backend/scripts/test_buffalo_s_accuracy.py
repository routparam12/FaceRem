import io
import os
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageEnhance

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["JWT_SECRET"] = "test-secret-that-is-long-enough-for-hs256-abcdef"
os.environ["INSIGHTFACE_MODEL_NAME"] = "buffalo_s"

import insightface
from app.face import InsightFaceEngine
from app.config import get_settings

get_settings().insightface_model_name = "buffalo_s"
engine = InsightFaceEngine()

samples = Path(insightface.__file__).parent / "data" / "images"
scene = Image.open(samples / "t1.jpg").convert("RGB")
detected = sorted(engine._detect(scene), key=lambda f: f.bbox[0])

def crop(face, pad=0.6):
    x1, y1, x2, y2 = face.bbox
    w, h = x2 - x1, y2 - y1
    return scene.crop((
        max(0, int(x1 - w * pad)),
        max(0, int(y1 - h * pad)),
        min(scene.width, int(x2 + w * pad)),
        min(scene.height, int(y2 + h * pad)),
    ))

f0, f3 = crop(detected[0]), crop(detected[3])

def _jpeg(img, q=70):
    b = io.BytesIO()
    img.save(b, "JPEG", quality=q)
    return b.getvalue()

v0 = np.asarray(engine.embed(_jpeg(f0)).vector)
v3 = np.asarray(engine.embed(_jpeg(f3)).vector)

dimmed = ImageEnhance.Brightness(f0).enhance(0.65).rotate(9, expand=True, fillcolor=(128, 128, 128))
dimmed = dimmed.resize((int(dimmed.width * 0.55), int(dimmed.height * 0.55)), Image.LANCZOS)
v_same = np.asarray(engine.embed(_jpeg(dimmed, 55)).vector)

sim_same = float(np.dot(v0, v_same))
sim_diff = float(np.dot(v0, v3))
gap = sim_same - sim_diff

print(f"buffalo_s Results:")
print(f"  Same person similarity:      {sim_same:.4f} (must be > {engine.default_threshold})")
print(f"  Different person similarity: {sim_diff:.4f} (must be < {engine.default_threshold})")
print(f"  Separation gap:              {gap:.4f} (must be > 0.30)")
print(f"  All separation tests pass:   {sim_same > engine.default_threshold and sim_diff < engine.default_threshold and gap > 0.30}")

