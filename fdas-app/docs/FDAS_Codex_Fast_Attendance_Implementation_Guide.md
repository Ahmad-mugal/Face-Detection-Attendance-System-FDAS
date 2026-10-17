# FDAS — CODEX IMPLEMENTATION GUIDE
## Reversible Fast Attendance Mode: No Liveness by Default, Multi-Face Detection and Recognition

**Type:** Controlled major feature change /   architecture refactor  
**Project:** Face Detection Attendance System (FDAS)  
**Status:** Implementation instructions, NOT an assertion that changes have already been made  
**Scope:** Actual working local React/Vite frontend + FastAPI/SQLite backend; preserve production records  
**Important:** Audit the **current working repository and newest `docs/development_journey.md`** before editing. Older FYP proposal/SRS/chapters describe superseded behaviors.

## 1. User requirement and non-negotiable result

The user wants normal attendance to be fast and simple:

- **No liveness challenge in the default attendance workflow.** Do not display “MOVE_CLOSER,” countdowns, liveness-failed messages, liveness progress, or wait for motion/area-growth frames. Do not run the liveness code secretly in the background for attendance.
- **Do not delete liveness code.** Preserve the complete existing verified liveness implementation and its tests. It must be possible to restore the prior liveness-required attendance mode via explicit, documented backend configuration without reimplementing it.
- **Recognize enrolled people using the existing InsightFace/ArcFace model.** Keep department access, deep-ready eligibility, recognition score/margin checks, and duplicate safety.
- **Show live rectangle boxes** around every real face detected in the webcam view, properly aligned with moving faces and responsive resizing/mirroring.
- **Support 2+ people in the same camera view.** Detect each face separately, recognize each against authorized registered students, and independently mark attendance for each eligible, confidently identified, not-yet-marked student. Do not reject an entire scene just because it contains multiple faces.
- **Aim for 1–2 seconds** from availability of a usable stable camera frame to an attendance result for a recognized person on the user's actual laptop, with measured evidence. This is a performance target, NOT a guaranteed promise. Cold model startup and camera permission are reported separately. Multi-person total completion may take longer on CPU depending on the number of faces.
- **Do not make recognition permissive merely to hit the speed target.** Unknown, low-score, ambiguous, cross-department, inactive, deep-incomplete, duplicate, or otherwise ineligible subjects must never create unauthorized attendance records.

This change intentionally **reduces spoofing resistance**. A photograph, phone screen or recorded video may be able to fool recognition when liveness is disabled. Acknowledge this honestly in user-facing guidance and documentation; do not claim anti-spoofing protection exists in Fast Mode.

## 2. Starting system baseline — verify, do not assume the paths are current

Historical baseline in `development_journey.md` through Phase 10.12D and more recent agent reports:

- Frontend: React + Vite + Tailwind CSS, generally `frontend/`, port `5173`.
- Backend: FastAPI + Uvicorn + SQLAlchemy + SQLite, generally `backend/`, port `8000`.
- Current normal attendance: one stable face; exact-one-face/continuity checks; mandatory `MOVE_CLOSER` liveness (area growth `0.12`); three fresh, quality-gated ArcFace frames; minimum `2-of-3` identity consensus; deep identity threshold `0.85`; distinct-identity margin `0.07`; active, authorized department, deep-ready student; duplicate prevention; persistence.
- Recognition: InsightFace `buffalo_l`, ONNX Runtime CPU, `arcface_v1` 512-dimensional embeddings, per-student `mean_top_3` gallery scoring. Historical `opencv_basic_v1` threshold `0.75` remains as legacy code only; **no automatic legacy fallback**.
- Face enrollment: protected 25-sample workflow, exact-one-face and continuity safeguards, deep-ready requires at least **20 active valid ArcFace embeddings**, non-destructive Deep Enrollment Recovery.
- Server-side access: approved Admin, Department Operator, All Departments Operator; Student is not an account/role with login.
- Unique attendance: one `AttendanceRecord` per `(sessionId, studentId)`, record status `Present`.
- Separate timing flaw (not in scope): no active AttendanceTimeWindow still starts a one-hour default session; grace period is stored/displayed but not enforced. Do **not** alter this during the Fast Attendance change.

Inspect these probable files/modules, locate renamed equivalents, and follow the real call chain:

- `frontend/src/components/LiveAttendanceStation.jsx`
- `frontend/src/pages/admin/AdminLiveAttendance.jsx`
- `frontend/src/pages/user/UserAttendance.jsx`
- `frontend/src/api/attendanceMarkingApi.js`
- `frontend/src/api/attendanceSessionsApi.js`
- `backend/app/config.py`
- `backend/app/routers/attendance_marking.py`
- `backend/app/services/attendance_marking.py`
- `backend/app/services/liveness.py` and `backend/app/routers/liveness.py`
- `backend/app/services/deep_face_matching.py`
- `backend/app/services/face_processing.py` / deep-face detector wrappers
- database models for `Student`, `FaceTemplateEmbedding`, `AttendanceSession`, and `AttendanceRecord`
- `backend/app/verify_phase10_10.py` and the current final regression runner

Search additionally for: `MOVE_CLOSER`, `exactly_one_face`, `MultipleFacesDetected`, `FaceContinuityLost`, `livenessStatus`, `Start Scanning`, `mean_top_3`, `arcface_v1`, `consensus`, `startCamera`, `canvas`, `FACE_MATCH_THRESHOLD`, `DEEP_MATCH_THRESHOLD`, `mark-by-face-live`, `getUserMedia`.

**First deliverable:** Write a short architecture audit stating exactly where the existing flow blocks multiple faces, enforces liveness, gathers three recognition queries, performs ArcFace inference, and writes attendance. Show which parts can be reused safely. Do not blindly delete/rewrite the existing service.

## 3. Architectural requirement: explicitly switchable modes

Implement a **backend-authoritative attendance mode** rather than deleting the old path.

Suggested modes (names can fit existing project conventions):

| Mode | Default | Behavior |
| --- | --- | --- |
| `FAST_MULTI_FACE` | **Yes** | No liveness frames/checks. Each detected face is recognized separately with the deep model; all eligible, distinct identities can be marked. Live bounding boxes appear. |
| `SECURE_SINGLE_FACE` | Available, off | Existing exact-one-face, continuous `MOVE_CLOSER`, three-query / 2-of-3 ArcFace attendance pipeline, unchanged when restored. |

Prefer one authoritative environment configuration such as `FDAS_ATTENDANCE_MODE=FAST_MULTI_FACE` or `SECURE_SINGLE_FACE`. Add an explicit `.env.example` entry and safe documentation. The old `LIVENESS_*` settings stay in the repository for secure mode. Do not introduce conflicting frontend-only flags that could bypass backend policy. A read-only authenticated capability response may report the active mode to the UI.

**Default operation must not invoke liveness.** Mode switches require deliberate backend configuration and restart (or an existing safe server-side configuration mechanism), not an unprotected UI toggle. Switching back to `SECURE_SINGLE_FACE` must route to the previous actual implementation and restore all its liveness/exact-one-face checks. Test both modes. Do not equate `livenessStatus=NotChecked` with `Passed`.

A future mode supporting **simultaneous multi-face + per-person liveness** is a different, nontrivial engineering project. Do not claim that simply flipping liveness on will retain simultaneous multi-face operation. In the restored secure mode, use its previously verified one-face-at-a-time attendance behavior until explicitly redesigned and tested.

## 4. Do not weaken enrollment protections

The old exact-one-face rejection is appropriate for **enrollment** because a 25-image batch must belong to one person. The request to accept multiple faces applies **only to live attendance**.

Do not relax or remove exact-one-face, continuity, batch validation, or backend revalidation in:

- New Student/Register Face, automated 25-sample enrollment;
- Deep Enrollment Recovery;
- Enrollment image and embedding ownership;
- Single-person independent diagnostics unless independently redesigned.

Avoid editing a shared helper in a way that permits multi-person enrollment. Instead provide an **attendance-specific multiple-face detection path**, while leaving protected enrollment paths unchanged.

## 5. Actual multi-face detector, boxes, and per-face identity decisions

### 5.1 Detect EVERY face

Use the **existing deep detector** (e.g., SCRFD/InsightFace detections exposed by the actual `buffalo_l` pipeline) to enumerate real faces and obtain validated bounding boxes/landmarks. Do not simply call a helper that returns the largest face or rejects `faceCount > 1`. Reconcile Haar/OpenCV checks carefully: patterned backgrounds previously caused false Haar positives, so do not use raw Haar face count as an unconditional global reject in Fast Mode when the authoritative deep detector finds real faces. Keep safeguards against invalid boxes, duplicate detections, and faces too small to identify.

Return one bounded result per detected face containing only appropriate UI-safe metadata: a temporary face/track ID, normalized/pixel bbox plus source image width/height and orientation, status (`detecting`, `processing`, `recognized`, `unknown`, `ambiguous`, `already_marked`, or rejected reason), and authorized identity labels **only after server-confirmed matching**. Never send embeddings, secret tokens, or raw biometric vectors to the UI.

A camera frame with 2 faces should yield 2 independently evaluated face objects. If one is unknown/ambiguous, a different valid recognized face should still be marked. No global `MultipleFacesDetected` short-circuit in the FAST attendance path.

### 5.2 Identity per face

For each high-quality detected face:

1. Use the existing ArcFace recognition model to extract the face embedding from its **own aligned face**, not the entire multi-person frame mislabeled as one individual.
2. Load/reuse the **cached gallery of active + department-eligible + deep-ready** student `arcface_v1` templates; preserve data invalidation when students are added/disabled/reenrolled or access/session department changes.
3. Preserve the `mean_top_3` student aggregation or an equivalent **verified** policy; do not silently switch to maximum-single-template or legacy `opencv_basic_v1` matching.
4. Preserve **deep `0.85` threshold** and **distinct-identity `0.07` minimum margin** initially. Do not automatically accept a low-confidence match because another person is present or to make the page feel faster.
5. If identity is confidently recognized, apply active-session, Admin/Operator department scope, student active status and deep-readiness checks, then duplicate check. Save one Present record if permitted.
6. Otherwise leave that individual unmarked; other faces continue independently.

### 5.3 Two faces must not claim the same student

Add deterministic one-to-one **identity assignment per frame/batch**. If two face detections both point to Student #22, do NOT mark two faces as independently verified #22. Resolve using clear high-confidence distinct-identity ranking, a well-defined one-to-one assignment procedure, or conservatively mark one and flag the other as identity conflict/ambiguous. Session database uniqueness remains the last defense but does not replace correct display/identity association.

Use transient per-face tracking (e.g., bounding-box IoU/short-lived track IDs across frames) to avoid repeatedly re-running identity matching on a face that was just marked. Reset tracking when camera/session stops, route changes, or department changes. Never persist fragile transient face tracks as permanent student identity evidence.

### 5.4 Atomic attendance and partial success

Use existing attendance transactional persistence and database uniqueness. For a frame with three faces:

- registered, eligible A -> `Present` (or `AlreadyMarked` if in current session);
- registered, eligible B -> independent `Present`;
- unknown C -> no record, but A/B still succeed.

Handle duplicate concurrent requests/idempotently. Do not create duplicate attendance rows during repeated scans or overlapping requests. If a recoverable failure affects one face, other validated results should still complete safely. Document whether each request uses one database transaction or isolated per-face transactions; preserve database integrity and avoid partially misattributed rows.

### 5.5 REST/API contract

Audit the existing attendance API and adopt the least risky change. A **new protected batch/multi-face endpoint** (e.g. `POST /api/attendance/mark-by-face-fast`) is preferable if replacing the single-person route would break the restored secure mode. It should accept an active session and a camera frame, enforce all current authorization on the **backend**, and respond with the array of face outcomes plus record IDs/statuses. Keep the previous liveness-required endpoint callable only through the intended secure mode/policy, not as an accidental permission bypass. Maintain any compatible existing report/list APIs and records.

Do not let a client post a claimed `studentId`, claimed `livenessStatus=Passed`, or claimed confidence and have the backend trust it. The backend computes identities and statuses.

## 6. Fast recognition path — measure before changing the matching policy

The old flow collects baseline/movement frames for `MOVE_CLOSER` and three fresh post-liveness recognition queries. Merely hiding the liveness UI is insufficient. Create a genuine low-latency inference pipeline:

- Warm the InsightFace model once at application startup or first authorized use, without reloading weights per frame or per face.
- Resize incoming frames appropriately while preserving enough face resolution; profile realistic 1-, 2-, and 3-person cases.
- Detect once per submitted frame, align/embed all faces efficiently, use NumPy/vectorized cosine operations and a cached, authorized gallery where practical.
- Avoid repeated database reads, repeated image encoding/decoding, multiple redundant requests, serial per-face model reloads, and artificial wait intervals.
- Remove the **mandatory three-query/2-of-3 wait from FAST mode only** if actual profiling shows it blocks the target. The fast path may use one high-quality ArcFace query for initial recognition, with an optional tightly bounded fresh second confirmation on uncertain results; all threshold/margin and per-face eligibility checks remain mandatory. Label this as a **different confidence/robustness policy** from the old secure mode, and demonstrate it with identity/unknown tests before enabling normal attendance. Do not pretend single-frame decisions are equivalent to 2-of-3 consensus.
- Preserve exact old 3-query/2-of-3 logic in `SECURE_SINGLE_FACE` mode for future reactivation.
- Keep **minimal real image quality safeguards** needed to reject impossible/unusable faces. Audit whether the current blur cutoff (`50`), lighting, face size, centering and edge clearances are unnecessarily blocking otherwise recognizable images. Do **not** simply disable every quality check: collect measured failure reasons and make evidence-based small adjustments only, documenting effect on false acceptance/rejection.
- Avoid processing every display animation frame. Use a bounded scan rate, in-flight guard, backpressure/cancellation, and short per-identity cooldown after a successful mark. UI bounding boxes should feel live even while inference runs; don't issue overlapping attendance writes for the same track.
- Maintain meaningful failure messages rather than a generic “liveness failed.”

**Performance evaluation target:** In a warmed local application, under ordinary camera/lighting conditions, aim for p95 end-to-end time of **2 seconds or less per confidently recognized student** from submission of a usable frame to user-visible attendance outcome. Also report p50, p95, max, detector time, embedding time, gallery comparison time, database-write time, frontend roundtrip, and separate cold-start times. If hardware cannot meet 2 seconds without unsafe relaxation, clearly report measured time and the bottleneck. Do not invent benchmarks or overclaim performance.

## 7. React camera overlay and user experience

Implement live bounding rectangles around **all** detected real faces in Admin and Operator attendance screens, using a shared reusable component:

- Same webcam stream as the existing attendance page; preserve start/stop/session lifecycle and camera-permission handling.
- Layer an overlay canvas/SVG on top of the preview, with `pointer-events: none`, correct z-index, and 1-to-1 mapping from detector coordinates to video coordinates.
- Correct aspect ratio, `object-fit` (`cover` vs `contain`), letterboxing/cropping, CSS mirroring, DPR scaling, responsive resize, and orientation. Bounding boxes must follow actual faces on screen rather than being offset, stretched, or attached to the wrong person.
- Distinguish detection/pending, accepted/already-marked, unknown/ambiguous safely. Show identity name/roll only after successful backend confirmation and only to an authorized operator. No name for unrecognized faces.
- Show a clear small counter: `Faces detected: N`, `Marked this scan: M`, `Already marked: D`, `Unrecognized/Not eligible: U`, as supported by actual results.
- Keep `Start Session`, `Stop Session`, `Start Scanning`, `Stop Scanning` behavior unless a better existing equivalent exists. Do not start attendance automatically just because webcam preview opens, unless the current UI already intentionally separates these and the user approves changing that.
- In FAST mode remove/hide all mandatory liveness instructions, MOVE_CLOSER prompts, liveness timers/capture indicators and liveness failure toasts. Show simple guidance: **“Look toward the camera. Multiple registered students can be recognized together.”**
- In SECURE mode, restore the historical single-person movement instructions and UI automatically from backend-reported mode.
- For two registered people, show two boxes and independent successful attendance results; for mixed known/unknown, only known students are marked. Do not label every box as “recognized” just because any face was detected.
- Use accessible messages/legend, readable contrast, no flicker from box tracking, and mobile-friendly layout. Never call native `alert`/`confirm` for scan updates.

## 8. Database, reports, permissions and audit integrity

Preserve all production students, images, templates, embeddings, attendance history, notifications, classes, user accounts and access scopes. No reseeding, truncation, model migration, destructive enrollment rewrite, or global threshold reduction.

- New FAST-mode attendance records should record the **truthful** liveness state, preferably existing `NotChecked` if compatible. Do not store `Passed` when no challenge occurred. If introducing a new `Skipped`/`Disabled` state, do so additively with migration-safe handling and update frontend reports/tests; do not silently break historical data or status filters.
- Preserve `Present`, sessionId/studentId uniqueness, marked timestamp, recognition confidence, ArcFace provider/version/method and identity margin metadata.
- Reports, Print and Export CSV must continue showing only authorized department/class/student records and handle the truthful liveness state.
- Don't change JWT, PBKDF2, user approval, forgot-password flow, scoped notifications, SMTP, bulk import, protected deletion or Admin/Operator access checks.
- Don't modify the known AttendanceTimeWindow fallback/grace-period issue as a side effect; track it separately for a later explicit decision.
- Avoid caching an AllDepartments gallery after the operator changes to a restricted department; gallery filtering must be backend authoritative on every session/request.

## 9. Safety and privacy expectations (important viva disclosure)

With liveness disabled, this is intentionally **face recognition attendance without verified live-human presence**. A printed photo, image on a phone, or replayed video may be accepted if it produces a strong ArcFace match. Do not call it spoof-proof, anti-spoofed, presentation-attack-resistant, or equivalent.

Keep authorization, deep recognition threshold, margin, conflict handling, duplicate checks, and audit metadata. Display a restrained Admin-only explanatory note about the current liveness-disabled Fast Mode (not a constant alarming popup for operators). Documentation must state the limitation honestly and that a retained secure mode can be turned back on.

## 10. Phased implementation order for Codex

**Checkpoint A — Read-only audit and plan**

1. Inspect real source and newest `development_journey.md`, tests, and current branch status. Confirm actual call chain and historical state; note any worktree changes before starting.
2. Make a concise file-by-file change map, list preserved services, identify timing bottlenecks and existing test gaps.
3. Create a safety branch/checkpoint and confirm ignored `.env`, database and storage cannot enter Git. Snapshot counts/hashes of production data read-only. Do not run mutation verifiers against production.

**Checkpoint B — Reversible mode and backend tests**

4. Introduce server-side mode selection and authenticated capability response. Keep entire old secure flow intact.
5. Verify `FAST_MULTI_FACE` does not call liveness; `SECURE_SINGLE_FACE` still calls it and still rejects multiple faces as before. Verify server denies unauthorized clients irrespective of mode.

**Checkpoint C — Multi-face deep identification / persistence**

6. Implement reusable attendance-only detection of multiple deep faces and per-face embedding/scoring, one-to-one identity assignment, authorization and duplicate protection, batch result schema/API.
7. Unit/integration tests with controlled fixtures plus actual live image frames from two **distinct consenting registered students**, if available. Do not fabricate real-world success using synthetic mocks.

**Checkpoint D — Speed work**

8. Time detector, embeddings, matching and DB writes. Apply warm model, gallery caching, vectorization, bounded scan and fast single-query policy only as justified. Verify threshold/margin and negatives remain conservative.
9. Measure warmed one-person and two-person latency, document hardware/software conditions and distribution. If 1–2 sec isn't met, stop and report concrete bottleneck/next optimization; no unsafe threshold reductions.

**Checkpoint E — Live UI**

10. Draw and track aligned rectangles for all faces. Wire FAST results, duplicate/unknown/conflict states, multi-student counters and safe messages. Restore old instructions in SECURE mode.
11. Run visual checks on 375, 480, 768, 1024, 1440, 1920px widths, full-screen camera and resized/browser-zoom states.

**Checkpoint F — Regression and reversibility**

12. Test old secure mode from real configuration on disposable data with preserved MOVE_CLOSER/2-of-3 requirements. Switch back to FAST and confirm no liveness runs. Test enrollment still rejects multiple people and still produces validated 25-sample batches. Test independent diagnostic and recovery remain unaffected.
13. Run final isolated backend regression, relevant browser smoke, `npm.cmd run lint`, `npm.cmd run build`, Python compile, and verify production DB/storage counts/hashes unchanged. If old tests assume hardcoded single-face-only FAST behavior, update them accurately without suppressing real regressions. Keep old SECURE tests.
14. Append this as a **new phase** to `docs/development_journey.md` with exact decisions, files, endpoints, tests, performance measurements, security tradeoffs and rollback instructions. Do **not** begin Final Documentation Synchronization & Implementation Freeze.

## 11. Required acceptance tests

Test actual behavior **on isolated data** and verify, not just assert the UI visually:

| Case | Expected result |
| --- | --- |
| 0 faces | No attendance; overlay empty; no exception/spam. |
| 1 eligible deep-ready registered face | Bounding box and valid `Present` promptly, with correct student ID. |
| 2 distinct eligible registered faces visible together | Two boxes, two correct independent Present records in same authorized session; neither mislabeled. |
| 3 faces: two eligible, one unknown | Eligible two marked; unknown not marked; two accepted records only. |
| 2 faces competing for one identity | No double assignment; uncertain face rejected/flagged. |
| Registered but deep-incomplete student | Box visible; no attendance; helpful “Face enrollment incomplete/Not eligible” where authorized. |
| Student from different department | No attendance, no information leakage, regardless of visual detection. |
| Disabled/inactive student | No attendance, even if score high. |
| Low similarity <0.85 | No attendance. |
| Top-2 identity margin <0.07 | No attendance / ambiguous. |
| Same student scanned repeatedly | At most one attendance row per student and session; later result already marked. |
| Session closed / caller unauthorized / user disabled | No attendance, secure API rejection. |
| Bad image / bad dimensions / corrupted bytes | Bounded safe error, no writes. |
| FAST mode camera active | No MOVE_CLOSER, frame-growth, liveness countdown or liveness rejection. |
| New FAST attendance record | Truthful liveness status NotChecked/Skipped; no fabricated “Passed”. |
| Enrollment camera sees 2 people | Protected enrollment rejects/pauses; no contaminated 25-sample batch. |
| SECURE mode re-enabled | Old liveness, exact-one-face and original ArcFace consensus operate and reject spoof/static tests as before. |
| Admin/Operator separate access scopes | Correct departments only in gallery, attendance and report/CSV/print. |
| Camera box positioning | Correct scaling/mirroring, face follows movement across viewport sizes. |
| Real webcam performance | Report one/two/three faces, warmed/cold timings and p50/p95; never fake 1–2-second result. |

Also add regression tests for simultaneous submissions, same frame repeated rapidly, face moving out of the scene, crossing faces, overlapping faces, changing department mid-scan, camera denied/stopped, and no recognized candidates.

## 12. Explicit boundaries / do not touch

- Do not reset, reseed or rewrite production DB, enrolled images or old attendance.
- Do not remove `services/liveness.py`, liveness tests or historical phase records.
- Do not loosen protected single-person enrollment, recovery or historical diagnostic rules.
- Do not fall back to OpenCV basic `0.75` matching automatically.
- Do not silently lower ArcFace threshold `0.85` or margin `0.07`.
- Do not bypass authorization, student readiness, department restrictions, duplicate prevention or active-session checks.
- Do not confuse drawing bounding boxes with confirming a student's identity.
- Do not promise 100% recognition, 100% anti-spoofing, or 1–2 seconds regardless of lighting/hardware/number of faces.
- Do not change scheduling/grace-period semantics in this task.
- Do not start final documentation freeze.

## 13. Final report required from Codex

After implementation, report all of the following clearly:

1. Read-only audit and changed-file list with key code locations.
2. Exact new attendance mode configuration, default value and **step-by-step re-enable liveness** instructions.
3. Backend endpoint/API contract and per-face assignment/duplicate rules.
4. Proof that two/three actual faces can be shown and independently handled; distinguish synthetic tests from genuine distinct-person webcam verification.
5. Truthful current safety properties and spoofing limitation.
6. Performance benchmark table with laptop CPU, input resolution, candidate identity/gallery size, warm-up status, one/two/three faces, average/p50/p95/max latency, and method of measurement.
7. Old SECURE mode and enrollment regression proof.
8. All unit/integration/browser/lint/build tests with pass/fail and any remaining blockers.
9. Before-and-after production data inventories and assurances tests used disposable copies.
10. `development_journey.md` update and any residual limitations.

**Completion must mean genuine FAST multi-face functionality, not merely disabling a liveness button while leaving the backend single-person rejection in place.** If implementation cannot yet validate real two-person recognition or meet the latency target, report that precisely as PARTIAL and identify the next controlled test; never falsely call it PASS.
