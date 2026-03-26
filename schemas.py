from pydantic import BaseModel, Field


class AnalysisResponse(BaseModel):
    session_id: str = Field(..., examples=["abc-123"])
    sector: str = Field(..., examples=["pharmaceuticals"])
    generated_at: str = Field(..., examples=["2025-03-26T15:00:00+00:00"])
    requests_remaining: int = Field(..., examples=[9])
    report: str = Field(..., description="Full Markdown report")


class ErrorResponse(BaseModel):
    detail: str = Field(..., examples=["Invalid API key"])
