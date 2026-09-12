from pydantic import BaseModel


class LivenessInfo(BaseModel):
    mode: str
    frameCount: int
    baselineFrameCount: int
    movementFrameCount: int
    allowedChallenges: list[str]
    minCenterShiftRatio: float
    minAreaChangeRatio: float
    singleFaceRequired: bool
    continuityThreshold: float
    diagnosticsExposed: bool
    previewMirrored: bool
    productionGradePad: bool
    notes: str
