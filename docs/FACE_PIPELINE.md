# FaceAttend Biometric Pipeline & Architecture

This document describes the FaceAttend biometric pipeline implemented in Phase 3 and refined in Phase 3.1, covering threat modeling, model licensing analysis, threshold calibration, yaw/blink estimation mechanics, and hardware latency profiling.

---

## 1. Architectural Threat Model & Security Posture

### 1.1 Core Principles
FaceAttend operates under a strict **Zero-Trust Client** security model:
1. **Zero Client Biometric Trust**: The client camera feed is untrusted. Client-supplied scores (e.g. legacy `liveness_score: 1.0f`) are strictly discarded. All liveness verification, face quality inspection, and similarity scoring happen exclusively on the server.
2. **Tenant Isolation Before Similarity**: Face candidate matching is strictly partitioned by `organization_id` derived from verified credentials (JWT principal or registered attendance device). An attacker cannot query or match against identities in another tenant.
3. **Biometric Privacy & Hard Delete**:
   - Raw face frames are processed purely in-memory and **never written to disk or logged**.
   - Embeddings are 512-dimensional L2-normalized floating point vectors.
   - When an employee's face profile is deleted (`DELETE /api/v1/employees/{id}/face`), the `face_profiles` rows and vectors are **hard deleted**, fulfilling GDPR/BIPA biometric deletion requirements, while preserving non-biometric attendance audit records.

---

### 1.2 Threat Matrix & Mitigations

| Threat | Attack Vector | Mitigation in FaceAttend |
| :--- | :--- | :--- |
| **Static Photo Presentation** | Paper printout, tablet display of employee photo | **Active Challenge-Response**: Server issues single-use nonce with required physical action (`TURN_LEFT`, `TURN_RIGHT`, `BLINK`). Static presentations fail yaw/EAR variance checks. |
| **Replay Attack** | Pre-recorded video sent over HTTP or intercepted traffic | **Challenge Nonce & 60s TTL**: Every scan session requires a fresh nonce from `POST /attendance/challenge` consumed atomically in Redis or DB. Once used or expired, it cannot be replayed. |
| **Identity Swapping in Burst** | Showing genuine user for challenge, then target victim photo | **Burst Identity Consistency**: The server enforces that every frame in the challenge burst matches the primary face vector with cosine similarity $\ge 0.40$. |
| **Ambiguous Match / Near-Tie** | High similarity to multiple enrolled employees (lookalikes) | **Margin Rule**: Recognition requires not only $s_1 \ge \text{threshold}$ (default 0.45), but also $(s_1 - s_2) \ge \text{margin}$ (default 0.08). Near-ties trigger rejection. |
| **Kiosk Device Compromise** | Stolen kiosk token attempting cross-organization queries | **Cryptographic Device Binding**: Scanners authenticate via `ATTENDANCE_DEVICE` API keys tied to a specific `organization_id` and optional `branch_id`. Organization ID is never accepted from client request parameters. |

---

## 2. Model Licensing & Commercial Viability Report

### 2.1 Component Licensing Analysis

| Component | Upstream Project | Code / Repository License | Weights / Dataset License | Commercial Use Permitted? |
| :--- | :--- | :--- | :--- | :--- |
| **InsightFace Library** | [deepinsight/insightface](https://github.com/deepinsight/insightface) | MIT License | N/A (code only) | Yes (Code only) |
| **`buffalo_l` Weights** | RetinaFace (ResNet50) + ArcFace (ResNet50) | InsightFace Model Zoo | **MS1MV2 / Glint360k** Non-Commercial Research Only | **NO (Research Only)** |
| **`buffalo_s` Weights** | RetinaFace (MobileNet0.25) + ArcFace (MobileNet) | InsightFace Model Zoo | **MS1MV3 / Glint360k** Non-Commercial Research Only | **NO (Research Only)** |
| **ONNX Runtime** | Microsoft | MIT License | Apache 2.0 / MIT | Yes |
| **PyTorch / Torchvision** | Linux Foundation | Modified BSD | Open Source | Yes |

> [!CAUTION]
> **Commercial Warning regarding `buffalo_l` and `buffalo_s`**:
> The standard InsightFace pretrained model packages (`buffalo_l`, `buffalo_s`, `antelopev2`) were trained on academic datasets (MS1M-RetinaFace / Glint-360k) whose original license terms explicitly restrict usage to **academic, non-commercial research**. Using these specific pre-trained weights in a commercial SaaS product or enterprise deployment creates intellectual property and licensing liabilities.

### 2.2 Commercial Replacement Models (Unverified Suggestions)

> [!NOTE]
> The following entries are **unverified suggestions** for commercial replacement architectures. Legal counsel and ML engineering must independently audit and verify license texts and training dataset lineage prior to commercial adoption:
>
> 1. **DigiFace-1M / SynFace (Synthetic 3D Faces)**:
>    - *Repository License*: MIT / Academic (Microsoft Research).
>    - *Training Corpus*: Purely synthetically rendered 3D face identities. Eliminates GDPR biometric scraping liability, but commercial redistribution rights depend on the synthetic engine license.
> 2. **OpenSphere (ArcFace / CosFace Backbones)**:
>    - *Repository License*: Apache 2.0.
>    - *Weights*: Models trained on WebFace42M or synthetic datasets. WebFace42M weights carry non-commercial research restrictions; synthetic weights carry Apache 2.0.
> 3. **Proprietary Certified SDKs**:
>    - Commercial ISO/IEC 30107-3 PAD (Presentation Attack Detection) and NIST FRVT certified vendors (e.g. Innovatrics, Neurotechnology, FaceTec).
> 4. **Internal Model Training**:
>    - Train ArcFace/MobileFaceNet backbones on internally owned or commercially licensed datasets (such as commercial CASIA licenses or internal employee consent datasets).

---

## 3. Liveness Detection & Pose Verification Mechanics

### 3.1 Yaw Estimation (Head Rotation)
Yaw is estimated using InsightFace's `landmark_3d_68` module (68 3D facial landmarks):
1. The 68 predicted 3D landmark points are fitted to a canonical 3D mean face template using an estimated 3D-to-3D affine transformation matrix $P$.
2. The rotation matrix $R$ is decomposed into Euler angles $(\text{pitch}, \text{yaw}, \text{roll})$ via Rodrigues transformation (`transform.matrix2angle(R)`).
3. The estimated `yaw` represents rotation around the vertical axis in degrees:
   - $0^\circ \pm 12.0^\circ$: Frontal head pose.
   - Negative $yaw$ (e.g. $\le -10.0^\circ$): Subject turned to their left.
   - Positive $yaw$ (e.g. $\ge 10.0^\circ$): Subject turned to their right.

#### Active Yaw Challenge Verification Rules:
- **`TURN_LEFT` Challenge**: The server verifies that at least one burst frame exhibits a minimum leftward angle $yaw \le -12.0^\circ$ or a dynamic leftward shift $\Delta yaw = yaw_{\text{primary}} - yaw_{\min} \ge 12.0^\circ$. A static frontal photo ($yaw \approx 0^\circ$) fails this check.
- **`TURN_RIGHT` Challenge**: The server verifies that at least one burst frame exhibits a rightward angle $yaw \ge 12.0^\circ$ or a dynamic rightward shift $\Delta yaw = yaw_{\max} - yaw_{\text{primary}} \ge 12.0^\circ$. A static frontal photo fails this check.

#### Enrollment Pose Enforcement Rules:
When enrolling a 3-pose profile (`FRONT`, `LEFT`, `RIGHT`), the server estimates yaw from the uploaded frame bytes rather than trusting client-provided form fields:
- `expected_pose="FRONT"`: Requires $|yaw| \le 15.0^\circ$. Fails with `POSE_MISMATCH` if $|yaw| > 15.0^\circ$.
- `expected_pose="LEFT"`: Requires $yaw \le -10.0^\circ$. Fails with `POSE_MISMATCH` if $yaw > -10.0^\circ$.
- `expected_pose="RIGHT"`: Requires $yaw \ge 10.0^\circ$. Fails with `POSE_MISMATCH` if $yaw < 10.0^\circ$.

---

### 3.2 Eye Aspect Ratio (EAR) for Blink Detection
Blink detection is computed from `landmark_2d_106` (106 dense 2D facial keypoints):
1. **Keypoint Indices**:
   - **Left Eye**: Outer corner $p_{35}$, Inner corner $p_{39}$, Upper eyelid $p_{37}$, Lower eyelid $p_{41}$.
   - **Right Eye**: Outer corner $p_{89}$, Inner corner $p_{93}$, Upper eyelid $p_{91}$, Lower eyelid $p_{95}$.
2. **Formula**:
   $$\text{EAR} = \frac{\|p_{\text{upper}} - p_{\text{lower}}\|_2}{2 \cdot \|p_{\text{outer}} - p_{\text{inner}}\|_2}$$
3. The scalar EAR is averaged across left and right eyes: $\text{EAR}_{\text{avg}} = \frac{1}{2}(\text{EAR}_{\text{left}} + \text{EAR}_{\text{right}})$.
4. **Thresholds**:
   - Open eyes: $\text{EAR} \in [0.26, 0.36]$.
   - Closed eyes: $\text{EAR} \le 0.22$.
   - **`BLINK` Challenge**: Verifies that minimum $\text{EAR} \le 0.22$ and the dynamic drop $\Delta\text{EAR} = \text{EAR}_{\max} - \text{EAR}_{\min} \ge 0.05$. A static photo ($EAR \approx \text{const}$) fails with `Requested blink action was not detected`.

---

### 3.3 Passive Anti-Spoof Layer Status

> [!IMPORTANT]
> **Passive Layer Implementation Status**:
> The passive anti-spoof model (texture/reflection/depth classifier) is **NOT currently integrated with production weights** in this repository.
> To prevent a false sense of security in production:
> 1. The FastAPI backend lifespan verifies `_assert_production_requirements()`. In `APP_ENV=production`, the server **refuses to start** unless explicitly overridden with `ALLOW_UNCONFIGURED_PASSIVE_LIVENESS=true`.
> 2. `verify_passive()` raises `AppError("PASSIVE_LIVENESS_UNCONFIGURED", ..., 500)` in production mode if invoked without the explicit override.
> 3. Third-party unverified weights from unauthenticated sources are avoided to maintain IP safety.

---

## 4. Hardware Scan Latency Benchmark (Measured on Host CPU)

### 4.1 System & Hardware Specifications
- **Operating System**: Windows 10 (Build 10.0.26300)
- **CPU**: 13th Gen Intel(R) Core(TM) i7-1355U (10 Physical Cores: 2 Performance Cores, 8 Efficient Cores; 12 Logical Processors)
- **RAM**: 16 GB Physical (15.68 GB visible)
- **Python**: 3.10.20 (x86_64)
- **ONNX Runtime**: 1.20.1 (CPUExecutionProvider)

### 4.2 Benchmark Results (Warmed Process, $N=50$ Runs, First 5 Discarded)

The benchmark executes the complete end-to-end recognition cycle:
1. Primary Face Detection & Alignment
2. Primary Embedding Extraction (512-d ArcFace)
3. 1:1,000 Candidate Similarity Search (NumPy Dot Product)
4. Burst Frame 1 ROI Liveness Metric Extraction (Tracking crop + Pose + EAR)
5. Burst Frame 2 ROI Liveness Metric Extraction (Tracking crop + Pose + EAR)

#### Detailed Per-Stage Breakdown ($N=50$, All Values in Milliseconds)

| Architecture / Model | Pipeline Stage | Mean (ms) | Median (ms) | p95 (ms) | Min (ms) | Max (ms) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **`buffalo_l`**<br>*(ResNet-50 Det + ResNet-50 Rec)* | 1. Primary Detection + Align | 3,332.46 | 3,309.22 | 4,071.53 | 2,579.84 | 4,732.92 |
| | 2. Primary Embedding (ArcFace) | 753.21 | 672.74 | 944.07 | 529.29 | 3,115.48 |
| | *Total Primary Embed (1+2)* | *4,087.75* | *4,059.10* | *4,982.07* | *3,171.49* | *6,108.10* |
| | 3. 1:1,000 Search (NumPy) | 0.54 | 0.34 | 1.61 | 0.20 | 3.82 |
| | 4. Burst Frame 1 (Tracking ROI) | 3,418.90 | 3,295.26 | 4,025.57 | 2,529.72 | 9,858.42 |
| | 5. Burst Frame 2 (Tracking ROI) | 3,409.62 | 3,287.70 | 4,436.51 | 2,707.28 | 5,554.55 |
| | *Total Liveness (4+5)* | *6,828.52* | *6,620.82* | *8,063.55* | *5,282.10* | *14,666.49* |
| | **TOTAL END-TO-END** | **10,916.81** | **10,986.80** | **12,552.52** | **8,499.11** | **20,774.94** |
| | | | | | | |
| **`buffalo_s`**<br>*(MobileNet Det + MobileFaceNet)* | 1. Primary Detection + Align | 1,172.93 | 1,095.70 | 1,559.64 | 775.54 | 1,831.30 |
| | 2. Primary Embedding (ArcFace) | 186.26 | 177.95 | 314.42 | 102.11 | 398.19 |
| | *Total Primary Embed (1+2)* | *1,361.19* | *1,335.63* | *1,831.45* | *901.35* | *2,039.28* |
| | 3. 1:1,000 Search (NumPy) | 1.59 | 0.26 | 9.86 | 0.18 | 11.21 |
| | 4. Burst Frame 1 (Tracking ROI) | 1,177.96 | 1,100.47 | 1,582.07 | 797.99 | 1,871.94 |
| | 5. Burst Frame 2 (Tracking ROI) | 1,174.18 | 1,125.09 | 1,646.91 | 794.88 | 1,877.90 |
| | *Total Liveness (4+5)* | *2,352.14* | *2,220.69* | *3,170.32* | *1,695.85* | *3,385.60* |
| | **TOTAL END-TO-END** | **3,714.92** | **3,635.46** | **4,721.44** | **2,749.92** | **4,972.63** |

#### Comparison Summary: `buffalo_l` vs `buffalo_s`

| Metric | `buffalo_l` (ResNet50) | `buffalo_s` (MobileNet) | Speedup Factor |
| :--- | :---: | :---: | :---: |
| **Primary Embedding Mean** | 4,087.8 ms | 1,361.2 ms | **3.0x faster** |
| **Primary Embedding Median** | 4,059.1 ms | 1,335.6 ms | **3.0x faster** |
| **Total Liveness Verification (2 frames)** | 6,828.5 ms | 2,352.1 ms | **2.9x faster** |
| **End-to-End Total Mean** | 10,916.8 ms | 3,714.9 ms | **2.9x faster** |
| **End-to-End Total Median** | 10,986.8 ms | 3,635.5 ms | **3.0x faster** |
| **End-to-End Best Run (Min)** | 8,499.1 ms | 2,749.9 ms | **3.1x faster** |

#### Optimized Stage Timings with `det_size=(320, 320)` on Single Face:
- `buffalo_s` Detection: **107.9 ms**
- `landmark_3d_68` (Pose Yaw): **23.9 ms**
- `landmark_2d_106` (Blink EAR): **74.9 ms**
- `w600k_mbf` (ArcFace MobileFaceNet): **106.0 ms**
- **Single-frame total**: **312.7 ms**

#### Accuracy Parity on Existing Face Engine Test Suite:
When evaluated on `backend/tests/test_face_engine.py`:
- `buffalo_s` passes **100% of tests (13/13 passed)**.
- Same-person cosine similarity: **1.0000**
- Different-person cosine similarity: **0.1407**
- Separation daylight: **0.8593** (far exceeds required 0.30 margin threshold).

---

## 5. PostgreSQL and pgvector Status

### 5.1 Verification Report
- **Host PostgreSQL**: PostgreSQL 18.3 (x86_64-windows, MSVC 19.44).
- **Extension Status**:
  `SELECT name, default_version FROM pg_available_extensions WHERE name = 'vector';` returns **empty**.
  The native C extension `pgvector.so / pgvector.dll` is not compiled into the host PostgreSQL 18.3 installation.
- **Migration & Schema Status**:
  - Alembic migration `c7e2b14d9a3f` defines `VectorType(512)` with dual-column support:
    - `embedding` (JSON): fully operational fallback for SQLite and standard PostgreSQL installations.
    - `embedding_vec` (Vector(512)): automatically activated if `CREATE EXTENSION IF NOT EXISTS vector;` succeeds.
  - Successfully tested full database lifecycle against real PostgreSQL:
    - Downgrade to base
    - Upgrade to Phase 2 (`b4a1c8f309d2`)
    - Seeded 5 stub profiles and 2 real ArcFace profiles
    - Upgraded to head (`c7e2b14d9a3f`): exactly 5 stub profiles were purged, leaving 5 employees marked for re-enrollment (`employees_without_profile = 5`), while 2 real ArcFace profiles were preserved.
    - Downgraded back to `b4a1c8f309d2` and re-upgraded cleanly without errors.
- **pgvector Parity Status**:
  Honest report: Because the native pgvector binary is not installed in the Windows PostgreSQL 18 instance, the pgvector ANN index test is marked skipped in pytest. pgvector will run in production Linux Docker containers with official `pgvector/pgvector:pg16` images.

### 5.2 Database Privileges & Production Requirements

> [!IMPORTANT]
> **PostgreSQL Privileges for pgvector**:
> Creating extensions in PostgreSQL (`CREATE EXTENSION IF NOT EXISTS vector`) requires `SUPERUSER` privileges or database ownership with `CREATE` privilege on the target schema/database (`GRANT CREATE ON DATABASE <dbname> TO <user>;`).

#### Production Fail-Loud Enforcement:
1. **Alembic Migration `c7e2b14d9a3f`**:
   - In `APP_ENV=production`, if the PostgreSQL instance lacks the `vector` extension, migration execution **immediately raises `RuntimeError`** and halts deployment.
   - In dev/test environments (`APP_ENV!=production`), the migration logs a warning and falls back to JSON column storage.
2. **Application Lifespan (`backend/app/main.py`)**:
   - At application boot, `_assert_production_requirements()` verifies that:
     1. The `vector` extension is registered in `pg_extension`.
     2. The `embedding_vec` column is present on `face_profiles`.
   - If either check fails in `APP_ENV=production`, FastAPI aborts startup with a descriptive error.
