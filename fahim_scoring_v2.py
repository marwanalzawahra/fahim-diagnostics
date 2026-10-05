
from collections import defaultdict

SKILL_THRESHOLDS = {"mastered": 0.80, "developing": 0.60}
MISCONCEPTION_THRESHOLDS = {"high": 0.58, "suspected": 0.40}

def clamp(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))

def score_student(question_bank, responses):
    skill_num = defaultdict(float)
    skill_den = defaultdict(float)
    skill_items = defaultdict(set)
    skill_correct_items = defaultdict(set)
    skill_wrong_patterns = defaultdict(lambda: defaultdict(float))

    m_pos = defaultdict(float)
    m_neg = defaultdict(float)
    m_items = defaultdict(set)
    m_targeted = defaultdict(set)
    m_evidence_details = defaultdict(list)

    for qid, meta in question_bank.items():
        if qid not in responses:
            continue

        ans = responses[qid]
        is_correct = ans == meta["correct"]
        distractor = None if is_correct else meta.get("distractors", {}).get(ans)

        # Skill evidence
        for skill, weight in meta.get("skills", {}).items():
            skill_den[skill] += weight
            skill_items[skill].add(qid)
            if is_correct:
                skill_num[skill] += weight
                skill_correct_items[skill].add(qid)
            elif distractor:
                m = distractor["misconception"]
                skill_wrong_patterns[skill][m] += weight

        # Misconception targeting / counter-evidence
        for m in meta.get("targets", []):
            m_targeted[m].add(qid)
            if is_correct:
                m_neg[m] += 0.35

        # Positive evidence
        if distractor:
            m = distractor["misconception"]
            w = float(distractor.get("weight", 1.0))
            m_pos[m] += w
            m_items[m].add(qid)
            m_evidence_details[m].append({"question_id": qid, "answer": ans, "weight": w})

    # Preliminary misconception classification
    misconceptions = {}
    all_m = set(m_targeted) | set(m_pos) | set(m_neg)

    for m in all_m:
        pos = m_pos[m]
        neg = m_neg[m]
        evidence_count = len(m_items[m])
        targeted_count = len(m_targeted[m])

        # Conservative heuristic: repetition matters more than a single strong distractor.
        raw = pos / (pos + neg + 0.80) if (pos + neg) > 0 else 0.0
        repetition = min(1.0, evidence_count / 3.0)
        score = raw * (0.55 + 0.45 * repetition)

        if evidence_count >= 3 and score >= MISCONCEPTION_THRESHOLDS["high"]:
            status = "high_confidence"
        elif evidence_count >= 2 and score >= MISCONCEPTION_THRESHOLDS["suspected"]:
            status = "suspected"
        else:
            status = "insufficient_evidence"

        misconceptions[m] = {
            "score": round(score, 3),
            "status": status,
            "positive_evidence": round(pos, 2),
            "counter_evidence": round(neg, 2),
            "evidence_items": evidence_count,
            "targeted_items": targeted_count,
            "evidence_details": m_evidence_details[m],
        }

    detected = {
        m for m, info in misconceptions.items()
        if info["status"] in {"suspected", "high_confidence"}
    }

    # Skill classification, with interpretation layer:
    # if low accuracy is largely explained by a detected specific misconception,
    # do not label it as a broad weakness in intervention planning.
    skills = {}
    for skill, den in skill_den.items():
        accuracy = skill_num[skill] / den if den else 0.0
        n = len(skill_items[skill])

        if n < 2:
            status = "insufficient_evidence"
        elif accuracy >= SKILL_THRESHOLDS["mastered"]:
            status = "mastered"
        elif accuracy >= SKILL_THRESHOLDS["developing"]:
            status = "developing"
        else:
            status = "at_risk"

        explained = []
        for m, wt in skill_wrong_patterns[skill].items():
            if m in detected and wt > 0:
                explained.append(m)

        interpretation = (
            "specific_pattern_detected"
            if status == "at_risk" and explained
            else "broad_skill_signal"
        )

        skills[skill] = {
            "score": round(accuracy, 3),
            "status": status,
            "evidence_items": n,
            "correct_items": len(skill_correct_items[skill]),
            "confidence": round(clamp(n / 3.0), 3),
            "interpretation": interpretation,
            "explained_by": sorted(explained),
        }

    # Intervention planning
    interventions = []

    # Specific misconceptions have priority because they are more actionable.
    for m, info in misconceptions.items():
        if info["status"] in {"high_confidence", "suspected"}:
            priority = info["score"] + (
                1.50 if info["status"] == "high_confidence" else 1.20
            )
            interventions.append({
                "type": "misconception",
                "code": m,
                "priority": round(priority, 3),
            })

    # Broad skill interventions only when not already explained by a specific pattern.
    for skill, info in skills.items():
        if (
            info["status"] == "at_risk"
            and info["confidence"] >= 0.667
            and info["interpretation"] == "broad_skill_signal"
        ):
            interventions.append({
                "type": "skill",
                "code": skill,
                "priority": round(1.0 - info["score"], 3),
            })

    interventions.sort(key=lambda x: x["priority"], reverse=True)

    return {
        "skills": skills,
        "misconceptions": misconceptions,
        "next_interventions": interventions[:3],
    }
