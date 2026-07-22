from pydantic import BaseModel, Field
from typing import List

class PolicyValidationError(ValueError):
    """Exception raised when policy parsing or validation fails."""
    pass

class AccountPolicy(BaseModel):
    """Pydantic model representing the parsed policy rules for a social media account."""
    account_id: str = Field(..., description="Unique identifier for the social account")
    goal: str = Field(..., description="The main mission or goal of the account")
    constraints: List[str] = Field(default_factory=list, description="Hard constraints/rules (e.g. word count, banned words)")
    examples: List[str] = Field(default_factory=list, description="Examples of high-quality/approved posts")
    rubric: List[str] = Field(default_factory=list, description="Evaluation rubric items or criteria used to grade posts")
    threshold: float = Field(..., description="Minimum threshold score required for automatic publishing approval")
    model_route: str = Field(..., description="Which AI model (e.g. gemini-1.5-flash, gemini-1.5-pro) to use")
