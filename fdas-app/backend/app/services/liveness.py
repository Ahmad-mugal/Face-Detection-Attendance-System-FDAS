from dataclasses import dataclass
from statistics import median

from fastapi import HTTPException, UploadFile, status

from app.config import (
    FACE_CONTINUITY_MIN_SIMILARITY,
    LIVENESS_ALLOWED_CHALLENGES,
    LIVENESS_BASELINE_FRAME_COUNT,
    LIVENESS_FRAME_COUNT,
    LIVENESS_MIN_BASELINE_DETECTED_FRAMES,
    LIVENESS_MIN_AREA_CHANGE_RATIO,
    LIVENESS_MIN_CENTER_SHIFT_RATIO,
    LIVENESS_MIN_DIRECTIONAL_FRAME_COUNT,
    LIVENESS_MIN_MOVEMENT_DETECTED_FRAMES,
    LIVENESS_MODE,
    LIVENESS_MOVEMENT_FRAME_COUNT,
    LIVENESS_PREVIEW_MIRRORED,
)
from app.services.face_matching import MAX_FACE_IMAGE_BYTES, validate_match_upload_file
from app.services.face_processing import (
    crop_face,
    decode_image_bytes,
    descriptor_similarity,
    detect_faces,
    generate_basic_descriptor,
)


LIVENESS_STATUS_PASSED = "Passed"
LIVENESS_STATUS_FAILED = "Failed"


@dataclass
class LivenessFrame:
    image_bytes: bytes
    width: int
    height: int
    face_count: int
    face_box: tuple[int, int, int, int] | None
    face_descriptor: list[float] | None


@dataclass
class LivenessResult:
    passed: bool
    status: str
    message: str
    livenessStatus: str
    bestFrameBytes: bytes | None = None
    diagnostics: dict[str, bool | int | float | str | None] | None = None


def validate_challenge(challengeType: str) -> str:
    challenge = (challengeType or "").strip().upper()
    if challenge not in LIVENESS_ALLOWED_CHALLENGES:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid liveness challenge")
    return challenge


async def read_liveness_uploads(files: list[UploadFile]) -> list[bytes]:
    if len(files) < LIVENESS_FRAME_COUNT:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"At least {LIVENESS_FRAME_COUNT} liveness frames are required",
        )

    frame_bytes: list[bytes] = []
    for file in files[:LIVENESS_FRAME_COUNT]:
        validate_match_upload_file(file)
        content = await file.read()
        if not content:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Uploaded liveness frame is empty")
        if len(content) > MAX_FACE_IMAGE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="Uploaded liveness frame is larger than the 5 MB limit",
            )
        frame_bytes.append(content)
    return frame_bytes


def analyze_liveness_frames(frame_bytes: list[bytes]) -> list[LivenessFrame]:
    frames: list[LivenessFrame] = []
    for content in frame_bytes:
        image = decode_image_bytes(content)
        height, width = image.shape[:2]
        faces = detect_faces(image)
        face_box = faces[0] if len(faces) == 1 else None
        frames.append(
            LivenessFrame(
                image_bytes=content,
                width=width,
                height=height,
                face_count=len(faces),
                face_box=face_box,
                face_descriptor=(
                    generate_basic_descriptor(crop_face(image, face_box))
                    if face_box is not None
                    else None
                ),
            )
        )
    return frames


def face_center_x(face_box: tuple[int, int, int, int]) -> float:
    x, _, width, _ = face_box
    return float(x) + (float(width) / 2.0)


def face_area(face_box: tuple[int, int, int, int]) -> float:
    _, _, width, height = face_box
    return float(width) * float(height)


def build_liveness_diagnostics(
    frames: list[LivenessFrame],
    baseline_detected_frames: list[LivenessFrame],
    movement_detected_frames: list[LivenessFrame],
    challenge: str,
) -> dict[str, bool | int | float | str | None]:
    detected_frames = baseline_detected_frames + movement_detected_frames
    baseline_centers = [face_center_x(frame.face_box) for frame in baseline_detected_frames if frame.face_box is not None]
    movement_centers = [face_center_x(frame.face_box) for frame in movement_detected_frames if frame.face_box is not None]
    baseline_areas = [face_area(frame.face_box) for frame in baseline_detected_frames if frame.face_box is not None]
    movement_areas = [face_area(frame.face_box) for frame in movement_detected_frames if frame.face_box is not None]
    all_centers = baseline_centers + movement_centers
    frame_width = float(detected_frames[0].width) if detected_frames else None
    baseline_center = float(median(baseline_centers)) if baseline_centers else None
    end_center = movement_centers[-1] if movement_centers else None
    signed_displacement = (
        end_center - baseline_center
        if baseline_center is not None and end_center is not None
        else None
    )
    displacement_ratio = (
        signed_displacement / max(frame_width, 1.0)
        if signed_displacement is not None and frame_width is not None
        else None
    )
    raw_leftward_excursion_ratio = (
        (min(movement_centers) - baseline_center) / max(frame_width, 1.0)
        if movement_centers and baseline_center is not None and frame_width is not None
        else None
    )
    raw_rightward_excursion_ratio = (
        (max(movement_centers) - baseline_center) / max(frame_width, 1.0)
        if movement_centers and baseline_center is not None and frame_width is not None
        else None
    )
    preview_left_excursion_ratio = (
        raw_rightward_excursion_ratio
        if LIVENESS_PREVIEW_MIRRORED
        else (-raw_leftward_excursion_ratio if raw_leftward_excursion_ratio is not None else None)
    )
    preview_right_excursion_ratio = (
        -raw_leftward_excursion_ratio
        if LIVENESS_PREVIEW_MIRRORED and raw_leftward_excursion_ratio is not None
        else raw_rightward_excursion_ratio
    )
    baseline_area = float(median(baseline_areas)) if baseline_areas else None
    final_area = movement_areas[-1] if movement_areas else None
    maximum_area = max(movement_areas) if movement_areas else None
    area_growth_ratio = (
        (final_area - baseline_area) / max(baseline_area, 1.0)
        if baseline_area is not None and final_area is not None
        else None
    )
    maximum_area_growth_ratio = (
        (maximum_area - baseline_area) / max(baseline_area, 1.0)
        if baseline_area is not None and maximum_area is not None
        else None
    )

    def rounded(value: float | None) -> float | None:
        return round(value, 6) if value is not None else None

    return {
        "challenge": challenge,
        "submittedFrameCount": len(frames),
        "detectedFaceFrameCount": len(detected_frames),
        "baselineFrameCount": LIVENESS_BASELINE_FRAME_COUNT,
        "movementFrameCount": LIVENESS_MOVEMENT_FRAME_COUNT,
        "baselineDetectedFaceFrameCount": len(baseline_detected_frames),
        "movementDetectedFaceFrameCount": len(movement_detected_frames),
        "zeroFaceFrameCount": sum(frame.face_count == 0 for frame in frames),
        "singleFaceFrameCount": sum(frame.face_count == 1 for frame in frames),
        "multipleFaceFrameCount": sum(frame.face_count > 1 for frame in frames),
        "frameWidth": int(frame_width) if frame_width is not None else None,
        "startCenterX": rounded(baseline_center),
        "endCenterX": rounded(end_center),
        "minimumCenterX": rounded(min(all_centers) if all_centers else None),
        "maximumCenterX": rounded(max(all_centers) if all_centers else None),
        "signedDisplacementPixels": rounded(signed_displacement),
        "displacementRatio": rounded(displacement_ratio),
        "leftwardExcursionRatio": rounded(preview_left_excursion_ratio),
        "rightwardExcursionRatio": rounded(preview_right_excursion_ratio),
        "rawLeftwardExcursionRatio": rounded(raw_leftward_excursion_ratio),
        "rawRightwardExcursionRatio": rounded(raw_rightward_excursion_ratio),
        "requestedDirectionalDisplacementRatio": None,
        "directionalSupportingFrameCount": 0,
        "initialFaceArea": rounded(baseline_area),
        "finalFaceArea": rounded(final_area),
        "maximumFaceArea": rounded(maximum_area),
        "areaGrowthRatio": rounded(area_growth_ratio),
        "maximumAreaGrowthRatio": rounded(maximum_area_growth_ratio),
        "centerShiftThreshold": LIVENESS_MIN_CENTER_SHIFT_RATIO,
        "areaGrowthThreshold": LIVENESS_MIN_AREA_CHANGE_RATIO,
        "continuityThreshold": FACE_CONTINUITY_MIN_SIMILARITY,
        "continuityMinimumSimilarity": None,
        "continuityPassed": None,
        "previewMirrored": LIVENESS_PREVIEW_MIRRORED,
        "evaluationMethod": "median_stable_baseline_to_max_directional_excursion",
        "reason": None,
    }


def evaluate_liveness_frames(frames: list[LivenessFrame], challengeType: str) -> LivenessResult:
    challenge = validate_challenge(challengeType)
    baseline_frames = frames[:LIVENESS_BASELINE_FRAME_COUNT]
    movement_frames = frames[LIVENESS_BASELINE_FRAME_COUNT:LIVENESS_FRAME_COUNT]
    baseline_detected_frames = [frame for frame in baseline_frames if frame.face_box is not None]
    movement_detected_frames = [frame for frame in movement_frames if frame.face_box is not None]
    diagnostics = build_liveness_diagnostics(
        frames,
        baseline_detected_frames,
        movement_detected_frames,
        challenge,
    )
    if any(frame.face_count > 1 for frame in frames):
        diagnostics["reason"] = "At least one liveness frame contained multiple faces."
        diagnostics["continuityPassed"] = False
        return LivenessResult(
            passed=False,
            status="MultipleFacesDetected",
            message="Multiple faces detected. Please allow only one student in front of the camera for attendance.",
            livenessStatus=LIVENESS_STATUS_FAILED,
            diagnostics=diagnostics,
        )

    if any(frame.face_count == 0 for frame in frames):
        diagnostics["reason"] = "The tracked face disappeared from at least one required liveness frame."
        diagnostics["continuityPassed"] = False
        return LivenessResult(
            passed=False,
            status="NoFaceDetected",
            message="No face detected. Please stand in front of the camera.",
            livenessStatus=LIVENESS_STATUS_FAILED,
            diagnostics=diagnostics,
        )

    descriptors = [frame.face_descriptor for frame in frames]
    if any(descriptor is None for descriptor in descriptors):
        diagnostics["reason"] = "A required single-face descriptor could not be generated."
        diagnostics["continuityPassed"] = False
        return LivenessResult(
            passed=False,
            status="FaceContinuityLost",
            message="The active face could not be tracked continuously. Please retry.",
            livenessStatus=LIVENESS_STATUS_FAILED,
            diagnostics=diagnostics,
        )

    anchor_descriptor = descriptors[0]
    anchor_similarities = [
        descriptor_similarity(anchor_descriptor, descriptor)
        for descriptor in descriptors[1:]
    ]
    adjacent_similarities = [
        descriptor_similarity(descriptors[index - 1], descriptors[index])
        for index in range(1, len(descriptors))
    ]
    minimum_continuity = min(anchor_similarities + adjacent_similarities, default=1.0)
    continuity_passed = minimum_continuity >= FACE_CONTINUITY_MIN_SIMILARITY
    diagnostics["continuityMinimumSimilarity"] = round(minimum_continuity, 6)
    diagnostics["continuityPassed"] = continuity_passed
    if not continuity_passed:
        diagnostics["reason"] = "The detected subject changed unexpectedly during the liveness sequence."
        return LivenessResult(
            passed=False,
            status="FaceContinuityLost",
            message="The detected subject changed during the attendance attempt. Please retry with one student only.",
            livenessStatus=LIVENESS_STATUS_FAILED,
            diagnostics=diagnostics,
        )

    if (
        len(baseline_detected_frames) < LIVENESS_MIN_BASELINE_DETECTED_FRAMES
        or len(movement_detected_frames) < LIVENESS_MIN_MOVEMENT_DETECTED_FRAMES
    ):
        diagnostics["reason"] = (
            "Not enough detected-face frames for a stable baseline and movement sequence."
        )
        return LivenessResult(
            passed=False,
            status="NoFaceDetected",
            message="No face was detected clearly enough for liveness checking.",
            livenessStatus=LIVENESS_STATUS_FAILED,
            diagnostics=diagnostics,
        )

    baseline_centers = [face_center_x(frame.face_box) for frame in baseline_detected_frames if frame.face_box is not None]
    movement_centers = [face_center_x(frame.face_box) for frame in movement_detected_frames if frame.face_box is not None]
    baseline_areas = [face_area(frame.face_box) for frame in baseline_detected_frames if frame.face_box is not None]
    movement_areas = [face_area(frame.face_box) for frame in movement_detected_frames if frame.face_box is not None]
    baseline_center = float(median(baseline_centers))
    baseline_area = max(float(median(baseline_areas)), 1.0)
    frame_width = max(float(baseline_detected_frames[0].width), 1.0)

    if challenge == "MOVE_LEFT":
        directional_ratios = [
            ((center - baseline_center) / frame_width)
            if LIVENESS_PREVIEW_MIRRORED
            else ((baseline_center - center) / frame_width)
            for center in movement_centers
        ]
        directional_ratio = max(directional_ratios)
        supporting_frames = sum(ratio >= LIVENESS_MIN_CENTER_SHIFT_RATIO for ratio in directional_ratios)
        passed = (
            directional_ratio >= LIVENESS_MIN_CENTER_SHIFT_RATIO
            and supporting_frames >= LIVENESS_MIN_DIRECTIONAL_FRAME_COUNT
        )
        detail = "Move face slightly left"
        diagnostics["requestedDirectionalDisplacementRatio"] = round(directional_ratio, 6)
        diagnostics["directionalSupportingFrameCount"] = supporting_frames
        diagnostics["reason"] = (
            "Preview-left displacement met the threshold in enough movement frames."
            if passed
            else "Preview-left displacement did not meet the threshold in enough movement frames."
        )
    elif challenge == "MOVE_RIGHT":
        directional_ratios = [
            ((baseline_center - center) / frame_width)
            if LIVENESS_PREVIEW_MIRRORED
            else ((center - baseline_center) / frame_width)
            for center in movement_centers
        ]
        directional_ratio = max(directional_ratios)
        supporting_frames = sum(ratio >= LIVENESS_MIN_CENTER_SHIFT_RATIO for ratio in directional_ratios)
        passed = (
            directional_ratio >= LIVENESS_MIN_CENTER_SHIFT_RATIO
            and supporting_frames >= LIVENESS_MIN_DIRECTIONAL_FRAME_COUNT
        )
        detail = "Move face slightly right"
        diagnostics["requestedDirectionalDisplacementRatio"] = round(directional_ratio, 6)
        diagnostics["directionalSupportingFrameCount"] = supporting_frames
        diagnostics["reason"] = (
            "Preview-right displacement met the threshold in enough movement frames."
            if passed
            else "Preview-right displacement did not meet the threshold in enough movement frames."
        )
    else:
        area_growth_ratios = [(area - baseline_area) / baseline_area for area in movement_areas]
        area_change_ratio = max(area_growth_ratios)
        supporting_frames = sum(ratio >= LIVENESS_MIN_AREA_CHANGE_RATIO for ratio in area_growth_ratios)
        passed = (
            area_change_ratio >= LIVENESS_MIN_AREA_CHANGE_RATIO
            and supporting_frames >= LIVENESS_MIN_DIRECTIONAL_FRAME_COUNT
        )
        detail = "Move closer to camera"
        diagnostics["requestedDirectionalDisplacementRatio"] = round(area_change_ratio, 6)
        diagnostics["directionalSupportingFrameCount"] = supporting_frames
        diagnostics["reason"] = (
            "Face-area growth met the threshold in enough movement frames."
            if passed
            else "Face-area growth did not meet the threshold in enough movement frames."
        )

    if not passed:
        return LivenessResult(
            passed=False,
            status="LivenessFailed",
            message=f"Liveness challenge failed. Please retry: {detail}.",
            livenessStatus=LIVENESS_STATUS_FAILED,
            diagnostics=diagnostics,
        )

    return LivenessResult(
        passed=True,
        status="LivenessPassed",
        message="Liveness challenge passed.",
        livenessStatus=LIVENESS_STATUS_PASSED,
        bestFrameBytes=movement_detected_frames[-1].image_bytes,
        diagnostics=diagnostics,
    )


def verify_liveness(frame_bytes: list[bytes], challengeType: str) -> LivenessResult:
    return evaluate_liveness_frames(analyze_liveness_frames(frame_bytes), challengeType)


def liveness_info() -> dict:
    return {
        "mode": LIVENESS_MODE,
        "frameCount": LIVENESS_FRAME_COUNT,
        "baselineFrameCount": LIVENESS_BASELINE_FRAME_COUNT,
        "movementFrameCount": LIVENESS_MOVEMENT_FRAME_COUNT,
        "allowedChallenges": LIVENESS_ALLOWED_CHALLENGES,
        "minCenterShiftRatio": LIVENESS_MIN_CENTER_SHIFT_RATIO,
        "minAreaChangeRatio": LIVENESS_MIN_AREA_CHANGE_RATIO,
        "singleFaceRequired": True,
        "continuityThreshold": FACE_CONTINUITY_MIN_SIMILARITY,
        "diagnosticsExposed": True,
        "previewMirrored": LIVENESS_PREVIEW_MIRRORED,
        "productionGradePad": False,
        "notes": "Basic movement challenge-response liveness foundation only; not certified production-grade presentation attack detection.",
    }
