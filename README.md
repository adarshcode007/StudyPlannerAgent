# Exam Countdown Planner (Agentic AI)

An AI-powered Study Countdown and Catch-Up Planner that spreads exam topics across the days remaining before an exam, maintains state memory across turns, and dynamically reshuffles the remaining schedule whenever a user reports missing a day.

It features a FastAPI backend, an agentic plan-act loop powered by Groq API (`llama-3.3-70b-versatile`), a Jupyter notebook demo, and a premium glassmorphic single-page web interface.

---

## Features & Implementation

### 1. Tools Implementation (`app/tools.py`)
The system implements four python functions exposed to the LLM agent via JSON schemas:
- **`set_exam(session_id, date)`**: Parses the exam date, calculates the days remaining relative to today, and stores them in session state.
- **`allocate_topics(session_id, topics)`**: Evenly distributes a list of study topics across the remaining days starting tomorrow using a deterministic round-robin allocation. If topics are fewer than days, trailing days are filled with `"Review / buffer"`. If topics exceed days, days are packed with multiple topics.
- **`handle_missed_day(session_id, missed_day)`**: Triggers the **catch-up shuffle**. Marks the day as missed, collects its unfinished topics along with all future days' topics, and redistributes them over the remaining days (excluding past, completed, or missed days).
- **`mark_day_completed(session_id, day)`**: Locks a study day as completed, preventing its topics from being reshuffled.

### 2. Session Memory Design (`app/memory.py`)
Session states persist in-memory using an in-process dictionary keyed by `session_id`. Each session stores:
- `chat_history`: Conversation logs (messages from roles: `user`, `assistant`, `tool`).
- `exam_date` and `days_left`.
- `topics`: Full list of study topics.
- `day_plan`: Day-by-day mapping of day labels to topics.
- `completed_days` and `missed_days`.

Because the agent reads the session state from memory on every turn, the user does not need to repeat their exam date or topic list when reporting status changes or missing a day.

### 3. One Honest Failure Story
During initial developer testing, we observed that when the user said *"I missed Day 3"*, the LLM agent would try to call `handle_missed_day` with arguments like `{"missed_day": "Day 3"}`. However, the system keys the plan using the full descriptive label, e.g. `"Day 3 (2026-08-27)"`. This mismatch led to tool errors returning `"Day 'Day 3' is not in the current plan"`.

**Resolution**:
1. We modified the tool output error message to return the complete list of available keys: `"Day 'Day 3' is not in the current plan. Available days: [...]"`.
2. We reinforced the system prompt in `app/agent.py` to instruct the agent to inspect the current session state history to locate the exact day label representing the missed day.
3. This enabled the agent's plan-act loop to correctly read the validation error, discover the full label in the next step, and re-invoke the tool with the correct argument (e.g. `"Day 3 (2026-08-27)"`) within the same turn.

---

## Getting Started

### Prerequisites
- Python 3.10+
- Groq API Key

### Installation

1. Clone the repository and navigate to the directory:
   ```bash
   cd StudyPlannerAgent
   ```
2. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set up environment variables. Copy `.env.example` to `.env` and fill in your Groq API Key:
   ```env
   GROQ_API_KEY=gsk_your_api_key_here
   ```

---

## Running the Application

### 1. Launching the Web Application
You can run the FastAPI server to access the premium glassmorphic web UI:
```bash
uvicorn app.main:app --reload
```
Once started, open [http://127.0.0.1:8000](http://127.0.0.1:8000) in your web browser. You can:
- Enter an exam date and list of topics to generate a plan.
- Watch the **AI Thought Chamber** render the agent's step-by-step reasoning and tool calls in real-time.
- Mark study days as **Completed** or **Missed** directly on the interactive cards, triggering real-time catch-up reshuffles!

### 2. Running Unit Tests
To verify the core scheduling and catch-up shuffle algorithms without LLM dependencies, run:
```bash
python test_logic.py
```

### 3. Notebook Demo
Open the `notebook_demo.ipynb` in your Jupyter notebook server or IDE to see the trace of the plan-act loop across three mock scenarios using FastAPI's self-contained `TestClient`.
