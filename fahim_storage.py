"""Persistence helpers for Fahim.

This module contains no Streamlit UI code, which makes cloud saving testable.
"""

from datetime import datetime, timezone


def save_attempt_cloud(
    *, client, questions, question_bank, student_code, participant_id,
    responses, report, started_at=None
):
    code = (student_code or f"ANON_{participant_id}").upper()

    classroom_result = (
        client.table("classrooms")
        .upsert(
            {"name": "Fahim Pilot", "access_code": "PILOT"},
            on_conflict="access_code",
        )
        .execute()
    )
    if not classroom_result.data:
        raise RuntimeError("تعذر إنشاء الصف التجريبي أو قراءته.")
    classroom_id = classroom_result.data[0]["id"]

    student_result = (
        client.table("students")
        .upsert(
            {"classroom_id": classroom_id, "student_code": code},
            on_conflict="classroom_id,student_code",
        )
        .execute()
    )
    if not student_result.data:
        raise RuntimeError("تعذر إنشاء سجل الطالب أو قراءته.")
    student_id = student_result.data[0]["id"]

    correct = sum(
        1 for qid, answer in responses.items()
        if answer == question_bank[qid]["correct"]
    )
    detected = sorted(
        code for code, info in report["misconceptions"].items()
        if info["status"] in {"suspected", "high_confidence"}
    )
    now = datetime.now(timezone.utc).isoformat()

    attempt_result = client.table("attempts").insert({
        "student_id": student_id,
        "assessment_code": "FHM_V03",
        "correct_answers": correct,
        "total_questions": len(questions),
        "detected_patterns": detected,
        "student_report": {
            "next_interventions": report.get("next_interventions", []),
        },
        "teacher_report": report,
        "started_at": started_at or now,
        "completed_at": now,
    }).execute()
    if not attempt_result.data:
        raise RuntimeError("تعذر إنشاء سجل المحاولة.")
    attempt_id = attempt_result.data[0]["id"]

    rows = []
    for q in questions:
        qid = q["id"]
        answer = responses.get(qid)
        if answer is None:
            continue
        correct_answer = q["correct"]
        distractor = (
            None if answer == correct_answer
            else q.get("distractors", {}).get(answer)
        )
        rows.append({
            "attempt_id": attempt_id,
            "question_id": qid,
            "selected_answer": answer,
            "correct_answer": correct_answer,
            "is_correct": answer == correct_answer,
            "skill_id": ",".join(sorted(q.get("skills", {}).keys())) or None,
            "misconception_code": (
                distractor.get("misconception") if distractor else None
            ),
            "evidence_weight": (
                float(distractor.get("weight", 1.0)) if distractor else 1.0
            ),
        })

    try:
        if rows:
            client.table("responses").insert(rows).execute()
    except Exception:
        # Avoid leaving an incomplete attempt; child rows cascade on deletion.
        client.table("attempts").delete().eq("id", attempt_id).execute()
        raise

    return attempt_id
