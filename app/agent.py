import os
import json
from groq import Groq
from app import memory, tools
from dotenv import load_dotenv

load_dotenv()

def dispatch_tool(name: str, session_id: str, args: dict) -> dict:
    """
    Dispatches a tool call to the corresponding implementation in tools.py.
    """
    if name == "set_exam":
        return tools.set_exam(session_id, args.get("date"))
    elif name == "allocate_topics":
        return tools.allocate_topics(session_id, args.get("topics"))
    elif name == "handle_missed_day":
        return tools.handle_missed_day(session_id, args.get("missed_day"))
    elif name == "mark_day_completed":
        return tools.mark_day_completed(session_id, args.get("day"))
    else:
        return {"error": f"Unknown tool '{name}'"}

def run_agent(session_id: str, user_message: str) -> dict:
    """
    Executes the planning agent loop.
    Reads/writes session state, interfaces with Groq, executes tools,
    and collects the full execution trace.
    """
    state = memory.get_session(session_id)
    
    # Check if Groq API key is defined
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key or api_key == "your_groq_api_key_here":
        return {
            "final_answer": "Groq API key is not configured in .env. Please define GROQ_API_KEY to enable AI agent planning.",
            "trace": [{
                "step": 0,
                "type": "error",
                "content": "GROQ_API_KEY is missing or invalid in your .env file."
            }],
            "state": state
        }

    # Initialize Groq client
    client = Groq(api_key=api_key)
    
    # Append the user's message to chat history
    state["chat_history"].append({"role": "user", "content": user_message})
    
    trace = []
    MAX_STEPS = 5
    
    # Custom system prompt directing the agent's behavior
    system_prompt = (
        "You are an intelligent Exam Countdown Planner AI Agent. Your role is to help students plan their study topics leading up to an exam.\n"
        "You have access to the following tools:\n"
        "- `set_exam(date)`: Sets the exam date (YYYY-MM-DD) and computes the days remaining.\n"
        "- `allocate_topics(topics)`: Distributes a list of topics across remaining days.\n"
        "- `handle_missed_day(missed_day)`: Reshuffles the study plan when a day is missed.\n"
        "- `mark_day_completed(day)`: Locks a study day as completed so its topics won't be reshuffled.\n\n"
        "CRITICAL RULES:\n"
        "1. You are an agent, not just a chatbot. When you receive a request, you must reason step-by-step and determine which tool to call.\n"
        "2. If you need to set the exam date and allocate topics, call `set_exam` FIRST. In the next step, once you see the result of `set_exam`, call `allocate_topics` in the same run.\n"
        "3. When a user reports missing a day (e.g., 'I missed Day 3', 'I skipped Day 2', 'I was sick on Day 4'), you must use the `handle_missed_day` tool with the exact day label (e.g. 'Day 3 (YYYY-MM-DD)'). Check the session state to find the exact day label corresponding to the missed day.\n"
        "4. When a user reports completing a day, call `mark_day_completed` with the exact day label.\n"
        "5. Always reason briefly about what you are going to do before calling a tool. Explain your thought process in your thoughts, but let the tool do the heavy lifting.\n"
        "6. Do not mention session_id to the user. That is managed automatically by the system.\n"
        "7. VAGUE TOPICS / BROAD SUBJECTS BREAKDOWN:\n"
        "   - Category A: Super-Broad Subjects (e.g., 'Math', 'Science', 'History', 'Biology', 'Chemistry', 'Physics', 'Computer Science'): Do NOT call `allocate_topics` or automatically generate subtopics. These are too wide! Halt immediately and ask the user which specific topics, chapters, or eras they want to study within these subjects (e.g., for History: 'World War I', 'French Revolution'; for Chemistry: 'Organic Chemistry', 'Stoichiometry'). Propose examples and wait for their input.\n"
        "   - Category B: Manageable Topics (e.g., 'Algebra', 'Grammar', 'Rotational Motion', 'Organic Chemistry', 'World War I', 'Geometry'): These are specific enough to be auto-divided. Automatically divide each into 3 concrete, bite-sized study subtopics for mastery. For example:\n"
        "     * Algebra -> 'linear expressions', 'quadratic expressions', 'functions and graphs'\n"
        "     * Rotational Motion -> 'Moment of Inertia', 'Torque & Angular Acceleration', 'Conservation of Angular Momentum'\n"
        "     * Grammar -> 'parts of speech & sentence structure', 'active vs passive voice', 'tenses & agreement'\n"
        "     - Rule for Small Topics: If two subtopics are small, simple, or closely related, you should combine them into a single string (e.g., 'linear expressions & quadratic expressions') so the planner schedules them on the same day.\n"
        "     Compile the resulting subtopics list (combining grouped items) and call `allocate_topics`. In your final response, list the subtopics you generated and explain how they were structured."
    )
    
    for step in range(MAX_STEPS):
        # Build messages payload
        messages = [{"role": "system", "content": system_prompt}] + state["chat_history"]
        
        try:
            # Execute chat completion
            response = client.chat.completions.create(
                model="openai/gpt-oss-120b",
                messages=messages,
                tools=tools.TOOLS_SCHEMA,
                tool_choice="auto"
            )
        except Exception as e:
            error_msg = f"Groq API error: {str(e)}"
            trace.append({"step": step, "type": "error", "content": error_msg})
            state["chat_history"].append({"role": "assistant", "content": f"I encountered an error calling the AI model: {str(e)}"})
            break
            
        msg = response.choices[0].message
        
        # Log assistant reasoning if present
        if msg.content:
            trace.append({"step": step, "type": "assistant_thought", "content": msg.content})
            
        # Check if the model called any tools
        if not msg.tool_calls:
            state["chat_history"].append({"role": "assistant", "content": msg.content or "All tasks processed successfully."})
            trace.append({"step": step, "type": "final_answer", "content": msg.content or "All tasks processed successfully."})
            break
            
        # Serialize tool calls for state history
        tool_calls_list = []
        for tc in msg.tool_calls:
            tool_calls_list.append({
                "id": tc.id,
                "type": "function",
                "function": {
                    "name": tc.function.name,
                    "arguments": tc.function.arguments
                }
            })
            
        state["chat_history"].append({
            "role": "assistant",
            "content": msg.content,
            "tool_calls": tool_calls_list
        })
        
        # Dispatch each tool call
        for tc in msg.tool_calls:
            tool_name = tc.function.name
            args = json.loads(tc.function.arguments)
            
            trace.append({
                "step": step,
                "type": "tool_call",
                "tool": tool_name,
                "args": args
            })
            
            result = dispatch_tool(tool_name, session_id, args)
            
            trace.append({
                "step": step,
                "type": "tool_result",
                "tool": tool_name,
                "result": result
            })
            
            state["chat_history"].append({
                "role": "tool",
                "tool_call_id": tc.id,
                "name": tool_name,
                "content": json.dumps(result)
            })
            
    # Save session state updates
    memory.update_session(session_id, **state)
    
    # Resolve the final answer from trace
    final_answer = "Loop completed."
    for item in reversed(trace):
        if item["type"] in ("final_answer", "assistant_thought") and item["content"]:
            final_answer = item["content"]
            break
            
    return {
        "final_answer": final_answer,
        "trace": trace,
        "state": state
    }
