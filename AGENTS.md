# AGENTS.md — Contributor & AI Agent Guidelines

This document governs autonomous agents and developers working on the FaceRem / FaceAttend codebase.

---

## 1. Core Delivery Rules

1. **Implement Only What Is Requested**: Implement only the phase, stage, or task explicitly requested by the user. Do not anticipate or pre-implement future phases until prompted.
2. **Minimal Diffs & Documentation Integrity**: Maintain clean, minimal diffs. Preserve all existing comments, docstrings, and architectural invariants unless instructed otherwise.
3. **Build & Compilation Verification**:
   - At the end of each stage, compile or check the affected components (e.g., `./gradlew assembleDebug` for Android; Python import or OpenAPI generation checks for backend; TypeScript checks for web).
   - Resolve any syntax, compilation, or typing errors immediately.
   - Do not run slow integration or UI test suites unless explicitly directed by the user.
4. **Handoff Reporting**: At task completion, report:
   - Specific files modified or created.
   - Compilation/build verification command and exit status.
   - Explicit list of what was **not verified** or left for subsequent stages.
   - **Stop and wait for user review** before proceeding.

---

## 2. Product & Security Principles

- **Tenant Isolation**: Every database query and business operation must derive tenant scope (`organization_id`) directly from the authenticated session (JWT claims or verified device record). Never trust a client-supplied `organization_id` in request payloads or headers.
- **Biometric Privacy & Consent**:
  - Biometric face embeddings are sensitive personal data.
  - Face enrollment requires explicit user consent recorded with a timestamp.
  - Raw images are not stored long-term; if temporary face audit snapshots or profile avatars are stored, they must follow strict encryption and automatic retention purge policies (e.g., 7-day retention).
  - Removing an employee's face profile must never delete historical attendance records.
- **Biometric Pipeline Division**:
  - The Android client uses Google ML Kit strictly for on-device face detection, bounding box tracking, pose angle validation, and liveness challenges.
  - The Android client **never** computes or stores face recognition embeddings.
  - The server (backend) performs face validation, embedding extraction (InsightFace/ArcFace), and vector matching (`pgvector` cosine similarity).
- **Separation of Concerns**:
  - **Android**: Jetpack Compose screens must never invoke Retrofit services, repositories, or business logic directly. Route all interactions through ViewModels and Use Cases via `FaceCaptureSource` or repository interfaces.
  - **Web Console**: Browser code must never handle raw backend JWT tokens. Use the Next.js BFF proxy (`/api/proxy/*`) with `httpOnly`, `SameSite=Lax`, and `Secure` cookies.
  - **Backend**: Adhere strictly to the layered architecture (`routers` -> `services` -> `repositories` -> SQLAlchemy `models`).

---

## 3. Coding Standards & Status Conventions

- **Status Taxonomy**: When documenting or reporting implementation status, use strictly:
  - `Implemented`: Verified present in code, compiled, and functional.
  - `Partial`: Incomplete implementation or stubbed behavior present.
  - `Planned`: Designed in architecture or roadmap, but code does not yet exist.
- **No Marketing Language**: Avoid buzzwords like "enterprise-grade" or "tamper-evident" unless verified by code.
- **Terminology**:
  - Administrative staff **sign in** and **sign out** to management consoles.
  - Employees **check in** and **check out** via kiosk facial attendance.

