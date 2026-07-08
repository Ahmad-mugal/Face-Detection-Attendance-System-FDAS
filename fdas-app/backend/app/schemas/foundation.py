from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str
    database: str


class InfoResponse(BaseModel):
    appName: str
    version: str
    database: str
    note: str


