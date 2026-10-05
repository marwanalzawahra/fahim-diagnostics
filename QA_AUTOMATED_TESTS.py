import json
import unittest
from pathlib import Path

from fahim_scoring_v2 import score_student
from fahim_storage import save_attempt_cloud


BASE = Path(__file__).parent
QUESTIONS = json.loads((BASE / "question_bank.json").read_text(encoding="utf-8"))
BANK = {q["id"]: q for q in QUESTIONS}


class Result:
    def __init__(self, data):
        self.data = data


class FakeTable:
    def __init__(self, client, name):
        self.client = client
        self.name = name
        self.action = None
        self.payload = None
        self.filter_value = None

    def upsert(self, payload, on_conflict=None):
        self.action, self.payload = "upsert", payload
        return self

    def insert(self, payload):
        self.action, self.payload = "insert", payload
        return self

    def delete(self):
        self.action = "delete"
        return self

    def eq(self, column, value):
        self.filter_value = (column, value)
        return self

    def execute(self):
        if self.name == "responses" and self.client.fail_responses:
            raise RuntimeError("simulated response failure")
        if self.action == "delete":
            self.client.deleted_attempts.append(self.filter_value[1])
            return Result([])
        self.client.saved.setdefault(self.name, []).append(self.payload)
        if self.name == "classrooms":
            return Result([{"id": "classroom-1", **self.payload}])
        if self.name == "students":
            return Result([{"id": "student-1", **self.payload}])
        if self.name == "attempts":
            return Result([{"id": "attempt-1", **self.payload}])
        return Result(self.payload if isinstance(self.payload, list) else [self.payload])


class FakeClient:
    def __init__(self, fail_responses=False):
        self.fail_responses = fail_responses
        self.saved = {}
        self.deleted_attempts = []

    def table(self, name):
        return FakeTable(self, name)


class FahimTests(unittest.TestCase):
    def test_all_correct_has_no_diagnosis(self):
        answers = {q["id"]: q["correct"] for q in QUESTIONS}
        report = score_student(BANK, answers)
        detected = [
            x for x in report["misconceptions"].values()
            if x["status"] in {"suspected", "high_confidence"}
        ]
        self.assertEqual(detected, [])

    def test_complete_attempt_is_saved_with_all_responses(self):
        answers = {q["id"]: q["correct"] for q in QUESTIONS}
        report = score_student(BANK, answers)
        client = FakeClient()
        attempt_id = save_attempt_cloud(
            client=client,
            questions=QUESTIONS,
            question_bank=BANK,
            student_code="S001",
            participant_id="ABC123",
            responses=answers,
            report=report,
        )
        self.assertEqual(attempt_id, "attempt-1")
        self.assertEqual(len(client.saved["responses"][0]), len(QUESTIONS))
        self.assertEqual(client.saved["attempts"][0]["correct_answers"], 24)

    def test_failed_response_save_rolls_back_attempt(self):
        answers = {q["id"]: q["correct"] for q in QUESTIONS}
        report = score_student(BANK, answers)
        client = FakeClient(fail_responses=True)
        with self.assertRaises(RuntimeError):
            save_attempt_cloud(
                client=client,
                questions=QUESTIONS,
                question_bank=BANK,
                student_code="S002",
                participant_id="DEF456",
                responses=answers,
                report=report,
            )
        self.assertEqual(client.deleted_attempts, ["attempt-1"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
