# Fahim Diagnostics

Diagnostic mathematics assessment system with misconception detection, skill profiling, teacher reporting, and Supabase-backed attempt tracking.

## Overview

Fahim is an experimental diagnostic assessment system designed to go beyond raw test scores.

Instead of only reporting correct and incorrect answers, the system analyzes student responses to identify:

- Skill strengths and weaknesses
- Repeated mathematical misconceptions
- Evidence behind each diagnostic signal
- Priority interventions for follow-up
- Teacher-level attempt summaries and reports

The current prototype focuses on diagnostic mathematics assessment.

## Key Features

- 24-question diagnostic assessment
- Skill-level scoring
- Misconception detection
- Evidence-weighted diagnostic reasoning
- Student report
- Teacher report
- Teacher dashboard
- Supabase-backed attempt storage
- Local fallback storage
- Automated QA tests
- Rollback handling for incomplete cloud writes

## Diagnostic Logic

The system distinguishes between:

- Broad skill weaknesses
- Specific misconception patterns
- Insufficient evidence

Misconception detection requires repeated evidence rather than relying on a single incorrect answer.

The scoring engine also uses counter-evidence from correct responses to reduce false diagnostic conclusions.

## Teacher Dashboard

The teacher dashboard provides:

- Student and attempt summaries
- Performance overview
- Frequently occurring misconceptions
- Question-level response analysis
- Attempt-level details
- CSV export support

## Technology

- Python
- Streamlit
- Supabase
- JSON-based question bank
- Automated Python tests

## Project Structure

- `app.py` — student assessment interface
- `teacher_dashboard.py` — teacher-facing dashboard
- `fahim_scoring_v2.py` — diagnostic scoring engine
- `fahim_storage.py` — Supabase persistence layer
- `question_bank.json` — assessment items and diagnostic metadata
- `QA_AUTOMATED_TESTS.py` — automated scoring and persistence tests
- `QA_SUPABASE_CONNECTION.py` — safe Supabase connectivity test

## Important Limitations

Fahim is currently an experimental MVP.

The diagnostic weights, thresholds, and misconception scores have not yet been psychometrically calibrated on a large real-world student dataset.

Diagnostic outputs should therefore be interpreted as decision-support signals rather than validated educational diagnoses.

## Privacy and Security

Secrets are not stored in the repository.

The application expects Supabase credentials to be provided through:

`.streamlit/secrets.toml`

That file is excluded from version control.

Student-facing usage should rely on anonymous or pseudonymous student codes rather than real names.

## Status

Current version: **V0.5**

The project is under active development as an applied AI and educational diagnostics prototype.

## Author

Marwan Al Zawahra

Computer Vision Research Engineer | Applied AI | Reliable AI Systems
