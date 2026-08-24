# Project Spec: Exam Countdown Planner (Agentic AI)

Feed this file to your coding agent (or use it yourself) as the build spec. It covers architecture, tools, memory, the plan-act loop, FastAPI endpoints, the catch-up shuffle logic, and what the notebook demo + README must contain.

---

## 1. Goal

Build one AI agent (not a chatbot) that spreads a user's exam topics across the days remaining before an exam, remembers the plan across turns, and **reshuffles the remaining topics when the user reports a missed day**.

The agent must show:
- A **plan-act loop**: it reasons, decides which tool to call, looks at the tool's result, and decides the next step — more than one step per goal.
- **≥2 tools** implemented as real Python functions the LLM calls via function/tool calling.
- **Memory** that persists across turns in the same session (exam date, topic list, the day-by-day plan, and which days were missed).

---

## 2. Tech stack

- **Backend**: FastAPI (Python 3.10+)
- **LLM**: Groq API (OpenAI-compatible `chat.completions` with `tools=[...]`), model: `llama-3.3-70b-versatile` (or `llama-3.1-8b-instant` for speed/cost)
- **Groq SDK**: `groq` Python package (or plain `requests` against `https://api.groq.com/openai/v1/chat/completions`)
- **Memory store**: simple in-process Python dict keyed by `session_id` (fine for a course project — no DB needed)
- **Demo**: Jupyter notebook that calls the FastAPI endpoint with `requests` and prints the full step-by-step trace
- **Env config**: `.env` file with `GROQ_API_KEY=...`, loaded via `python-dotenv`

---

## 3. File structure

```
exam-countdown-planner/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app, /chat and /reset endpoints
│   ├── agent.py              # plan-act loop, calls Groq, dispatches tool calls
│   ├── tools.py               # set_exam, allocate_topics, handle_missed_day
│   ├── memory.py              # session state schema + get/update/reset helpers
│   └── schemas.py             # Pydantic request/response models
├── notebook_demo.ipynb        # runs 2-3 example goals, prints full trace
├── requirements.txt
├── .env.example
└── README.md
```

---

## 4. Memory design (`app/memory.py`)

One dict per `session_id`. This is the "remembers earlier turns" requirement — the agent must read this state back on every turn, not just append chat history.

```python
SESSION_STATE = {
    "session_id": {
        "chat_history": [ {"role": "user"/"assistant"/"tool", "content": ...}, ... ],
        "exam_date": "2026-09-20" or None,
        "today": "2026-08-24",          # can be overridden for demo/testing
        "days_left": 27,                 # computed by set_exam
        "topics": ["Topic A", "Topic B", ...] or [],
        "day_plan": { "Day 1 (2026-08-25)": ["Topic A"], "Day 2 (2026-08-26)": ["Topic B"], ... },
        "missed_days": ["Day 3 (2026-08-27)"],
        "completed_days": ["Day 1 (2026-08-25)"],
    }
}
```

Functions to implement:
- `get_session(session_id)` — creates a fresh state dict if it doesn't exist
- `update_session(session_id, **kwargs)` — merges updates
- `reset_session(session_id)` — wipes state (used by `/reset` endpoint, and by the notebook between demo goals if you want a clean run)

---

## 5. Tools (`app/tools.py`)

Each tool is a plain Python function **plus** a JSON schema describing it for Groq's `tools` parameter. Implement at minimum these three (the assignment names two; the third is what makes the catch-up shuffle real and pushes you past "at least two"):

### Tool 1 — `set_exam(session_id: str, date: str) -> dict`
- Parses `date` (ISO format `YYYY-MM-DD`).
- Computes `days_left = (exam_date - today).days`.
- Stores `exam_date`, `days_left` in session memory.
- Returns `{"exam_date": ..., "days_left": ..., "message": ...}`. If `days_left <= 0`, return an error message instead of a plan (exam date must be in the future).

### Tool 2 — `allocate_topics(session_id: str, topics: list[str]) -> dict`
- Requires `exam_date`/`days_left` already set (if not, return an error telling the agent to call `set_exam` first — this is what forces the multi-step behavior).
- Distributes `topics` evenly across `days_left` days, starting tomorrow. If there are more topics than days, pack multiple topics per day (round-robin so no day is empty and no day is overloaded by more than 1 topic vs. any other day). If there are more days than topics, leave the extra trailing days as `"Review / buffer"`.
- Stores `day_plan` and `topics` in session memory.
- Returns the full `day_plan` dict.

### Tool 3 — `handle_missed_day(session_id: str, missed_day: str) -> dict`
This is the **catch-up shuffle**. Logic:
1. Mark `missed_day` in `missed_days`.
2. Collect the topic(s) that were assigned to `missed_day` but not in `completed_days`.
3. Recompute `remaining_days` = all days in the original plan that are today-or-later and not already completed.
4. Re-run the same round-robin allocation from Tool 2, but only over `remaining_days`, using: (topics from the missed day) + (topics from all not-yet-reached future days) — i.e. don't touch days already completed, only reshuffle forward.
5. If there are now more topics than remaining days, compress by putting 2 topics on the earliest remaining days first (closest to the exam gets lighter, not heavier — see Section 6).
6. Update `day_plan` in memory, return the new plan plus a short human-readable summary of what changed.

**JSON schemas**: write an OpenAI-style `tools` list, e.g.:
```python
TOOLS_SCHEMA = [
  {
    "type": "function",
    "function": {
      "name": "set_exam",
      "description": "Set the exam date and compute how many days remain until it.",
      "parameters": {
        "type": "object",
        "properties": {"date": {"type": "string", "description": "Exam date, YYYY-MM-DD"}},
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
          "topics": {"type": "array", "items": {"type": "string"}}
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
          "missed_day": {"type": "string", "description": "The day label that was missed, e.g. 'Day 3 (2026-08-27)'"}
        },
        "required": ["missed_day"]
      }
    }
  }
]
```
`session_id` is not part of the LLM-facing schema — inject it server-side when dispatching the call (the LLM shouldn't need to know about sessions).

---

## 6. Allocation algorithm detail (keep it simple, deterministic, testable)

```python
def round_robin_allocate(topics: list[str], days: list[str]) -> dict[str, list[str]]:
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
```
This single function is reused by both `allocate_topics` and `handle_missed_day` (just called with a different `topics` list and a different `days` list) — keep the two tools thin wrappers around it so the shuffle logic is easy to explain in your README.

---

## 7. Agent plan-act loop (`app/agent.py`)

This is the core "agent, not chatbot" piece. Pseudocode:

```python
def run_agent(session_id: str, user_message: str) -> dict:
    state = memory.get_session(session_id)
    state["chat_history"].append({"role": "user", "content": user_message})

    trace = []  # <-- collect every step for the notebook to print

    for step in range(MAX_STEPS):  # e.g. MAX_STEPS = 5
        response = call_groq(
            messages=[SYSTEM_PROMPT] + state["chat_history"],
            tools=TOOLS_SCHEMA,
        )
        msg = response.choices[0].message
        trace.append({"step": step, "type": "assistant_thought", "content": msg.content})

        if not msg.tool_calls:
            # model decided it's done — final answer
            state["chat_history"].append({"role": "assistant", "content": msg.content})
            trace.append({"step": step, "type": "final_answer", "content": msg.content})
            break

        state["chat_history"].append(msg)  # keep the tool_call request in history
        for call in msg.tool_calls:
            args = json.loads(call.function.arguments)
            trace.append({"step": step, "type": "tool_call", "tool": call.function.name, "args": args})

            result = dispatch_tool(call.function.name, session_id, args)  # runs tools.py function
            trace.append({"step": step, "type": "tool_result", "tool": call.function.name, "result": result})

            state["chat_history"].append({
                "role": "tool", "tool_call_id": call.id,
                "content": json.dumps(result)
            })
        # loop continues -> model sees tool result, decides next step

    memory.update_session(session_id, **state)
    return {"final_answer": trace[-1]["content"], "trace": trace}
```

**System prompt** (put in `agent.py`) must explicitly tell the model:
- It is a study-planning agent with tools `set_exam`, `allocate_topics`, `handle_missed_day`.
- It must call `set_exam` before `allocate_topics` if the exam date isn't known yet.
- It must call `handle_missed_day` whenever the user says they missed / skipped / didn't do a study day.
- It should reason briefly about what it needs before calling a tool (this is what makes the multi-step trace visible in the notebook).

---

## 8. FastAPI endpoints (`app/main.py`)

```python
POST /chat
  body: { "session_id": "abc123", "message": "My exam is on 2026-09-20, topics: Algebra, Chemistry, History, Biology, Grammar" }
  returns: { "final_answer": "...", "trace": [ ...step-by-step... ], "state": { ...current memory snapshot... } }

POST /reset
  body: { "session_id": "abc123" }
  returns: { "status": "reset" }

GET /state/{session_id}
  returns current memory snapshot (useful for debugging / notebook display)
```

---

## 9. Notebook demo (`notebook_demo.ipynb`)

Must run against the FastAPI server (start it with `uvicorn app.main:app --reload` in a terminal, or spin it up in-process with `TestClient` from `fastapi.testclient` so the notebook is self-contained — recommended for submission simplicity).

Include **3 example goals** in separate cells, each printing the full trace clearly:

1. **Goal 1 — cold start**: `"My exam is on 2026-09-15. I need to study Algebra, Chemistry, History, Biology, and Grammar."` → should trigger `set_exam` then `allocate_topics` in the same turn (multi-step, same user message).
2. **Goal 2 — missed day (same session)**: `"I missed Day 3, I was sick."` → should trigger `handle_missed_day`, and the printed trace + new plan should visibly differ from Goal 1's plan (proves memory: it knows the exam date/topics without being told again).
3. **Goal 3 — new session / edge case**: e.g. an exam date only 2 days away with 6 topics (tests the "more topics than days" packing), or a fresh session to show `set_exam` alone is correctly rejected by `allocate_topics` if called with no date yet.

For each goal, print:
```python
result = requests.post(f"{BASE_URL}/chat", json={"session_id": SID, "message": goal}).json()
for step in result["trace"]:
    print(step)   # or format nicely
print("FINAL ANSWER:", result["final_answer"])
```
This raw trace list **is** your proof of agentic behavior — don't hide it, that's the graded artifact.

---

## 10. README.md requirements (3 short paragraphs, per the assignment)

1. **Tools**: name `set_exam`, `allocate_topics`, and `handle_missed_day` (or your two if you scope to exactly two), one line each on what they do.
2. **Memory**: explain that the session dict remembers `exam_date`, `topics`, and `day_plan` across turns, so a later "I missed a day" message doesn't need to repeat the exam date or topic list.
3. **One honest failure**: pick something real once you build it, e.g. "the model initially tried to call `allocate_topics` before `set_exam` and got a tool-error result back — we fixed it by making the error message explicit enough that the model retried in the correct order on the next loop iteration" or "Groq's tool-call JSON was occasionally malformed for very long topic lists, fixed by truncating/validating args before dispatch." Don't fabricate — note whatever you actually hit.

---

## 11. requirements.txt

```
fastapi
uvicorn
groq
python-dotenv
pydantic
requests
jupyter
```

---

## 12. Suggested build order

1. `tools.py` + `memory.py` — test the allocation/shuffle logic with plain unit calls, no LLM yet.
2. `agent.py` — wire up Groq tool calling against those tested functions.
3. `main.py` — expose `/chat`, `/reset`, `/state`.
4. `notebook_demo.ipynb` — run the 3 goals, confirm the trace shows multiple steps and correct memory reuse.
5. `README.md` — write last, once you know your real failure story.