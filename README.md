The project implements four core tools for the AI agent:
- `set_exam` sets the target exam date and calculates remaining study days
- `allocate_topics` distributes study topics across the calendar using round-robin allocation and automatically injects spaced-repetition revision tasks
- `handle_missed_day` executes the catch-up shuffle by moving future topics forward when a day is marked missed
- `mark_day_completed` locks completed days to exempt them from reshuffling.

Session memory is stored in-process via a dictionary keyed by `session_id` that holds conversation history, exam details, generated schedules, and progress logs (completed/missed days).
By persisting this state across turns, the agent can reason using historical schedule information without requiring the user to repeat their exam date, topic list, or previous study progress in subsequent messages.

One honest failure occurred during developer testing when the user entered broad subject domains like 'History' or 'Chemistry'.
The agent initially auto-generated subtopics for them without asking the user for their specific target topics, leading to incorrect schedule assumptions.
We resolved this by implementing double-depth classification rules in the system prompt:
- broad subjects (Category A) now halt the planner and trigger conversational rejections that prompt the user for specific study chapters
- only manageable topics (Category B) are auto-divided.
