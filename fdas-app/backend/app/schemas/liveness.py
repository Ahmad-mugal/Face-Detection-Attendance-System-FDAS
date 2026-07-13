from pydantic import BaseModel


class LivenessInfo(BaseModel):
    mode: str
    frameCount: int
    allowedChallenges: list[str]
    minCenterShiftRatio: float
    minAreaChangeRatio: float
    productionGradePad: bool
    notes: str
