from datetime import datetime, date, timedelta
from app.memory import get_session, update_session
import re

# OpenAI-compatible tools schema for Groq API
TOOLS_SCHEMA = [
  {
    "type": "function",
    "function": {
      "name": "set_exam",
      "description": "Set the exam date and compute how many days remain until it.",
      "parameters": {
        "type": "object",
        "properties": {
          "date": {"type": "string", "description": "Exam date in YYYY-MM-DD format."}
        },
        "required": ["date"]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "allocate_topics",
      "description": "Distribute a list of exam topics across the remaining days before the exam.",
      "parameters": {
        "type": "object",
        "properties": {
          "topics": {
            "type": "array",
            "items": {"type": "string"},
            "description": "List of study topics to allocate."
          }
        },
        "required": ["topics"]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "handle_missed_day",
      "description": "Reshuffle the remaining study plan because the user missed a scheduled day.",
      "parameters": {
        "type": "object",
        "properties": {
          "missed_day": {
            "type": "string",
            "description": "The exact day label that was missed, e.g. 'Day 3 (2026-08-27)'"
          }
        },
        "required": ["missed_day"]
      }
    }
  },
  {
    "type": "function",
    "function": {
      "name": "mark_day_completed",
      "description": "Mark a study day as completed so its topics are locked and won't be reshuffled.",
      "parameters": {
        "type": "object",
        "properties": {
          "day": {
            "type": "string",
            "description": "The exact day label that was completed, e.g. 'Day 1 (2026-08-25)'"
          }
        },
        "required": ["day"]
      }
    }
  }
]

def parse_date(date_str: str) -> date:
    return datetime.strptime(date_str.strip(), "%Y-%m-%d").date()

def parse_date_from_day_label(label: str) -> str:
    # Day label format: "Day X (YYYY-MM-DD)"
    match = re.search(r'\((.*?)\)', label)
    if match:
        return match.group(1)
    return ""

def set_exam(session_id: str, date: str) -> dict:
    """
    Sets the exam date in memory, calculates days_left, and returns status.
    """
    state = get_session(session_id)
    try:
        exam_d = parse_date(date)
        today_d = parse_date(state["today"])
    except ValueError:
        return {"error": "Invalid date format. Please use YYYY-MM-DD."}
    
    days_left = (exam_d - today_d).days
    if days_left <= 0:
        return {
            "error": f"Exam date {date} must be in the future. Today is {state['today']} (days remaining: {days_left})."
        }
    
    update_session(session_id, exam_date=date, days_left=days_left)
    return {
        "exam_date": date,
        "days_left": days_left,
        "message": f"Exam date set to {date}. You have {days_left} days left."
    }

def round_robin_allocate(topics: list[str], days: list[str]) -> dict[str, list[str]]:
    """
    Distributes a list of topics evenly across the days list.
    """
    plan = {d: [] for d in days}
    if not topics:
        return plan
    for i, topic in enumerate(topics):
        day = days[i % len(days)]
        plan[day].append(topic)
    
    # if topics ran out before days did, fill remaining empty days with "Review / buffer"
    for d in days:
        if not plan[d]:
            plan[d] = ["Review / buffer"]
    return plan

def allocate_topics(session_id: str, topics: list[str]) -> dict:
    """
    Distributes a list of topics across remaining days starting tomorrow.
    """
    state = get_session(session_id)
    if not state["exam_date"] or state["days_left"] <= 0:
        return {
            "error": "Exam date is not set or has already passed. Please call set_exam before allocating topics."
        }
    
    try:
        today_d = parse_date(state["today"])
    except ValueError:
        return {"error": "Invalid state 'today' date format."}
    
    # Generate day labels starting tomorrow
    days = []
    for k in range(1, state["days_left"] + 1):
        day_date = today_d + timedelta(days=k)
        days.append(f"Day {k} ({day_date.isoformat()})")
        
    day_plan = round_robin_allocate(topics, days)
    update_session(session_id, day_plan=day_plan, topics=topics)
    
    return {
        "day_plan": day_plan,
        "message": f"Successfully allocated {len(topics)} topics across {state['days_left']} days."
    }

def handle_missed_day(session_id: str, missed_day: str) -> dict:
    """
    Catch-up shuffle: Marks a day as missed, collects topics assigned to it (and future days),
    and reshuffles them across future uncompleted days.
    """
    state = get_session(session_id)
    day_plan = state["day_plan"]
    if not day_plan:
        return {"error": "No study plan exists yet. Please allocate topics first."}
    
    if missed_day not in day_plan:
        return {"error": f"Day '{missed_day}' is not in the current plan. Available days: {list(day_plan.keys())}"}
    
    # Mark in missed_days
    missed_days = state["missed_days"]
    if missed_day not in missed_days:
        missed_days.append(missed_day)
    
    completed_days = state["completed_days"]
    today_str = state["today"]
    
    try:
        today_d = parse_date(today_str)
    except ValueError:
        return {"error": "Invalid state 'today' date format."}
        
    topics_to_reallocate = []
    remaining_days = []
    
    for day_label, day_topics in day_plan.items():
        if day_label in completed_days:
            continue
            
        day_date_str = parse_date_from_day_label(day_label)
        if not day_date_str:
            continue
        try:
            day_d = parse_date(day_date_str)
        except ValueError:
            continue
            
        is_today_or_later = day_d >= today_d
        is_missed = day_label in missed_days
        
        # Collect topics from missed day or future uncompleted days
        if day_label == missed_day or (is_today_or_later and not is_missed):
            for t in day_topics:
                if t != "Review / buffer" and t != "Missed" and t not in topics_to_reallocate:
                    topics_to_reallocate.append(t)
        
        # Remaining study days: today-or-later, not completed, not missed
        if is_today_or_later and not is_missed:
            remaining_days.append(day_label)
            
    # Perform reallocation
    new_alloc = round_robin_allocate(topics_to_reallocate, remaining_days)
    
    # Rebuild plan
    new_day_plan = {}
    for day_label in day_plan.keys():
        if day_label in completed_days:
            new_day_plan[day_label] = day_plan[day_label]
        elif day_label in missed_days:
            new_day_plan[day_label] = ["Missed"]
        elif day_label in new_alloc:
            new_day_plan[day_label] = new_alloc[day_label]
        else:
            # Fallback for past days not completed and not marked missed explicitly
            new_day_plan[day_label] = day_plan[day_label]
            
    update_session(session_id, day_plan=new_day_plan, missed_days=missed_days)
    
    return {
        "day_plan": new_day_plan,
        "message": f"Day '{missed_day}' marked as missed. Reallocated {len(topics_to_reallocate)} topics across {len(remaining_days)} remaining days."
    }

def mark_day_completed(session_id: str, day: str) -> dict:
    """
    Locks a study day as completed so its topics are not reshuffled.
    """
    state = get_session(session_id)
    day_plan = state["day_plan"]
    if not day_plan:
        return {"error": "No study plan exists yet. Please allocate topics first."}
    
    if day not in day_plan:
        return {"error": f"Day '{day}' is not in the current plan."}
        
    completed_days = state["completed_days"]
    if day not in completed_days:
        completed_days.append(day)
        
    missed_days = state["missed_days"]
    if day in missed_days:
        missed_days.remove(day)
        
    update_session(session_id, completed_days=completed_days, missed_days=missed_days)
    return {
        "completed_days": completed_days,
        "message": f"Day '{day}' marked as completed."
    }
