"""
schemas.py
Request/response models for the interview API.
"""

from pydantic import BaseModel, Field


class StartSessionRequest(BaseModel):
    resume_text: str = Field(..., min_length=10, description="Raw resume text (parsed by the resume_parser node)")
    job_description: str | None = Field(None, description="Optional JD text; weights question topics toward skills it emphasizes")
    max_questions: int | None = Field(None, ge=1, le=20)
    target_company: str | None = Field(
        None,
        description="Optional: switches question_generator into company-specific mode. Falls back to the general pool for topics that company's bank is thin on."
    )

class QuestionOut(BaseModel):
    question_id: str
    question_text: str
    topic: str
    question_type: str
    difficulty: str
    source: str  # "verbatim" | "adapted" | "generated"
    is_follow_up: bool = False


class RoundResult(BaseModel):
    question: QuestionOut
    candidate_answer: str
    scores: dict
    weighted_score: float
    feedback: str


class SessionResponse(BaseModel):
    session_id: str
    status: str  # "in_progress" | "complete"
    question_number: int
    max_questions: int
    question: QuestionOut | None = None
    last_result: RoundResult | None = None
    final_report: dict | None = None


class AnswerRequest(BaseModel):
    answer: str = Field(..., min_length=1)
