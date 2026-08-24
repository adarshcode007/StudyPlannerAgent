import os
from datetime import date
from dotenv import load_dotenv

load_dotenv()

# In-memory dictionary to store session states
SESSION_STATE = {}

def get_session(session_id: str) -> dict:
    """
    Retrieve or create the session state for a given session_id.
    """
    if session_id not in SESSION_STATE:
        SESSION_STATE[session_id] = {
            "chat_history": [],
            "exam_date": None,
            "today": os.getenv("TODAY_OVERRIDE") or date.today().isoformat(),
            "days_left": 0,
            "topics": [],
            "day_plan": {},
            "missed_days": [],
            "completed_days": []
        }
    return SESSION_STATE[session_id]

def update_session(session_id: str, **kwargs) -> dict:
    """
    Merge updates into the session state.
    """
    state = get_session(session_id)
    for key, value in kwargs.items():
        if key in state:
            state[key] = value
    return state

def reset_session(session_id: str) -> dict:
    """
    Wipe state for a session and return a fresh default state.
    """
    if session_id in SESSION_STATE:
        del SESSION_STATE[session_id]
    return get_session(session_id)
