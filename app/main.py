import os
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.schemas import ChatRequest, ChatResponse, ResetRequest, ResetResponse
from app.agent import run_agent
from app.memory import get_session, reset_session

app = FastAPI(title="Exam Countdown Planner (Agentic AI)")

# Enable CORS for local testing
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For local testing convenience
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Endpoints matching the spec exactly
@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(payload: ChatRequest):
    try:
        result = run_agent(payload.session_id, payload.message)
        # Handle case where error occurred inside trace
        return ChatResponse(
            final_answer=result.get("final_answer", "Error in plan-act loop."),
            trace=result.get("trace", []),
            state=result.get("state", {})
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )

@app.post("/reset", response_model=ResetResponse)
async def reset_endpoint(payload: ResetRequest):
    reset_session(payload.session_id)
    return ResetResponse(status="reset")

@app.get("/state/{session_id}")
async def get_state_endpoint(session_id: str):
    state = get_session(session_id)
    return state

# Mount static files folder to serve the frontend UI
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)

app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
async def read_index():
    index_file = os.path.join(static_dir, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return {"message": "Welcome to Exam Countdown Planner. Frontend UI not yet created."}
