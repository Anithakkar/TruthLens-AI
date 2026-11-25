from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str
    api_version: str


class AnalysisAvailabilityResponse(BaseModel):
    available: bool
    message: str
