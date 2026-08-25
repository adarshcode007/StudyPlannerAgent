import os
os.environ["TODAY_OVERRIDE"] = "2026-08-24"

from app import memory, tools

def run_tests():
    session_id = "test_session"
    
    print("=== Testing set_exam ===")
    res = tools.set_exam(session_id, "2026-09-15")
    print(res)
    assert res["days_left"] == 22, f"Expected 22 days left, got {res['days_left']}"
    
    state = memory.get_session(session_id)
    assert state["exam_date"] == "2026-09-15"
    assert state["days_left"] == 22
    print("set_exam OK.")
    
    print("\n=== Testing allocate_topics ===")
    topics = ["Algebra", "Chemistry", "History", "Biology", "Grammar"]
    res = tools.allocate_topics(session_id, topics)
    plan = res["day_plan"]
    
    # We should have 22 days.
    assert len(plan) == 22, f"Expected 22 days, got {len(plan)}"
    
    # Check allocation
    # 5 topics across 22 days.
    # Tomorrow is Day 1 (2026-08-25).
    # Day 1: Algebra, Day 2: Chemistry, Day 3: History, Day 4: Biology, Day 5: Grammar.
    # Day 6 to 22 should be "Review / buffer" because topics ran out before days did.
    # [Revise] tasks are added 3 and 7 days after the core topic day.
    assert plan["Day 1 (2026-08-25)"] == ["Algebra"]
    assert plan["Day 2 (2026-08-26)"] == ["Chemistry"]
    assert plan["Day 3 (2026-08-27)"] == ["History"]
    assert plan["Day 4 (2026-08-28)"] == ["Biology", "[Revise] Algebra"]
    assert plan["Day 5 (2026-08-29)"] == ["Grammar", "[Revise] Chemistry"]
    assert plan["Day 6 (2026-08-30)"] == ["[Revise] History"]
    print("allocate_topics OK.")
    
    print("\n=== Testing mark_day_completed ===")
    # Mark Day 1 completed
    tools.mark_day_completed(session_id, "Day 1 (2026-08-25)")
    state = memory.get_session(session_id)
    assert "Day 1 (2026-08-25)" in state["completed_days"]
    print("mark_day_completed OK.")
    
    print("\n=== Testing handle_missed_day (Reshuffle) ===")
    # Today is overridden to 2026-08-24. But let's say tomorrow we miss Day 2 (which is 2026-08-26).
    # Topics to reshuffle: Chemistry (from Day 2), History (Day 3), Biology (Day 4), Grammar (Day 5).
    # Note: Day 1 (Algebra) is completed, so it won't be touched.
    # Remaining days: Day 2 is missed. So remaining days are Day 3 to Day 22 (20 days).
    res = tools.handle_missed_day(session_id, "Day 2 (2026-08-26)")
    new_plan = res["day_plan"]
    
    # Day 1 should remain completed with Algebra
    assert new_plan["Day 1 (2026-08-25)"] == ["Algebra"]
    
    # Day 2 should be marked missed
    assert new_plan["Day 2 (2026-08-26)"] == ["Missed"]
    
    # Chemistry, History, Biology, Grammar should be allocated starting Day 3.
    # 4 topics over 20 days (Day 3 to Day 22).
    # Day 3: Chemistry, Day 4: History, Day 5: Biology, Day 6: Grammar.
    # Revision tasks are automatically added 3 and 7 days after they are studied in remaining_days.
    assert new_plan["Day 3 (2026-08-27)"] == ["Chemistry"]
    assert new_plan["Day 4 (2026-08-28)"] == ["History"]
    assert new_plan["Day 5 (2026-08-29)"] == ["Biology"]
    assert new_plan["Day 6 (2026-08-30)"] == ["Grammar", "[Revise] Chemistry"]
    assert new_plan["Day 7 (2026-08-31)"] == ["[Revise] History"]
    
    print("handle_missed_day OK.")
    
    print("\n=== Testing short schedule (more topics than days) ===")
    # Reset session for test 2
    session_id2 = "test_session_2"
    tools.set_exam(session_id2, "2026-08-26") # 2 days left
    res = tools.allocate_topics(session_id2, ["T1", "T2", "T3", "T4", "T5", "T6"])
    plan2 = res["day_plan"]
    # Day 1: T1, T3, T5
    # Day 2: T2, T4, T6
    assert plan2["Day 1 (2026-08-25)"] == ["T1", "T3", "T5"]
    assert plan2["Day 2 (2026-08-26)"] == ["T2", "T4", "T6"]
    print("Short schedule allocation OK.")
    
    print("\nALL LOGIC TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    run_tests()
