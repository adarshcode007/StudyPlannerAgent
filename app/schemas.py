from pydantic import BaseModel, Field

class ChatRequest(BaseModel):
    session_id: str = Field(..., description="Unique session identifier for the user.")
    message: str = Field(..., description="Message containing instructions or study schedule status updates.")

class ChatResponse(BaseModel):
    final_answer: str = Field(..., description="The final text response from the agent.")
    trace: list[dict] = Field(..., description="Detailed step-by-step trace of the plan-act loop.")
    state: dict = Field(..., description="Snapshot of the session's internal memory state.")

class ResetRequest(BaseModel):
    session_id: str = Field(..., description="Unique session identifier to reset.")

class ResetResponse(BaseModel):
    status: str = Field("reset", description="Status of the reset request.")
