"""
Pydantic schemas for data validation, serialization, and agent request/response structures.
"""
import re
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, field_validator


EMAIL_REGEX = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
PHONE_REGEX = r"^\+?[0-9\s\-().]{7,25}$"


class LeadCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=100, description="Lead's full name")
    email: str = Field(..., description="Valid business or personal email address")
    phone_number: str = Field(..., description="Valid contact phone number with optional country code")
    company: str = Field(..., min_length=1, max_length=120, description="Company or organization name")
    message: str = Field(..., min_length=5, description="Inquiry or message text")

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        cleaned = v.strip().lower()
        if not re.match(EMAIL_REGEX, cleaned):
            raise ValueError(f"Invalid email address format: '{v}'")
        return cleaned

    @field_validator("phone_number")
    @classmethod
    def validate_phone_format(cls, v: str) -> str:
        cleaned = v.strip()
        if not re.match(PHONE_REGEX, cleaned):
            raise ValueError(
                f"Invalid phone number format: '{v}'. Must contain 7-25 digits, optional '+' and standard separators."
            )
        return cleaned

    @field_validator("name", "company", "message")
    @classmethod
    def sanitize_strings(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Field cannot be empty or only whitespace.")
        return cleaned


class LeadStatusUpdate(BaseModel):
    status: Literal["New", "Contacted", "Qualified", "Disqualified"] = Field(
        ..., description="New pipeline status"
    )
    reason: str = Field(..., min_length=3, description="Audit reason or justification for status update")
    agent_name: Optional[str] = Field("API_User", description="Identity of caller or AI Agent")


class LeadResponse(BaseModel):
    id: int
    name: str
    email: str
    phone_number: str
    company: str
    message: str
    classification: str
    confidence_score: float
    business_intent: Optional[str] = None
    extracted_requirements: List[str] = []
    ai_response: Optional[str] = None
    status: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class AIAnalysisResult(BaseModel):
    classification: Literal["Hot Lead", "Warm Lead", "Cold Lead"]
    confidence_score: float = Field(..., ge=0.0, le=1.0)
    business_intent: str
    extracted_requirements: List[str]
    personalized_response: str
    suggested_follow_up: str


class AgentExecuteRequest(BaseModel):
    instruction: str = Field(..., min_length=5, description="Natural language command for the Hermes agent")
    lead_id: Optional[int] = Field(None, description="Optional lead ID for targeted commands")
    email: Optional[str] = Field(None, description="Optional email for lookup")


class AgentExecuteResponse(BaseModel):
    instruction: str
    agent_reasoning: str
    tool_executed: Optional[str] = None
    tool_input: Optional[Dict[str, Any]] = None
    tool_result: Optional[Dict[str, Any]] = None
    final_response: str
    success: bool
