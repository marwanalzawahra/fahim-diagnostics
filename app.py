
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import streamlit as st
from supabase import Client, create_client
from fahim_scoring_v2 import score_student
from fahim_storage import save_attempt_cloud

st.set_page_config(
    page_title="فَهِم | Fahim Diagnostics",
    page_icon="🧠",
    layout="centered",
    initial_sidebar_state="collapsed",
)

MISCONCEPTION_LABELS = {
    "M01": "إسقاط الجذر x = 0 بعد التحليل",
    "M03": "خلط في إشارة أو صيغة مجموع/فرق المكعبين",
    "M04": "التوقف عند المتغير البديل وعدم الرجوع إلى x",
    "M05": "نسيان الجذر السالب عند أخذ الجذر التربيعي",
    "M07": "قبول حل يحقق معادلة واحدة فقط من النظام",
    "M08": "سوء تفسير عدد الحلول أو المميّز",
    "M09": "خطأ في مساواة أو طرح معادلتي النظام",
    "M10": "التوقف عند قيمة x وعدم تكوين زوج مرتب",
    "M11": "خطأ في الجذر أو قيمة القوة",
    "M12": "فقدان أحد فروع الحل",
    "M14": "التعامل مع الجذر التكعيبي كأنه يعطي ±",
    "M15": "عكس ترتيب الزوج المرتب (x, y)",
}

REMEDIATION = {
    "M01": "أعد تطبيق خاصية الضرب الصفري على كل عامل على حدة، وتأكد من فحص العامل الذي يعطي x = 0.",
    "M03": "راجع صيغتي مجموع المكعبين وفرق المكعبين، مع الانتباه إلى إشارة الحد الأوسط.",
    "M04": "بعد إيجاد u، لا تتوقف: أعد التعويض بالعلاقة الأصلية بين u و x ثم أكمل الحل.",
    "M05": "عندما تصل إلى x² = a حيث a > 0، تذكّر أن هناك حلين حقيقيين: x = ±√a.",
    "M07": "الزوج المرتب لا يكون حلًا للنظام إلا إذا حقق المعادلتين معًا.",
    "M08": "اربط قيمة المميّز بعدد الجذور الحقيقية، ثم اربط ذلك بعدد نقاط التقاطع.",
    "M09": "عند كون المعادلتين على صورة y = f(x) و y = g(x)، ساوِ f(x) و g(x) ثم بسّط بعناية.",
    "M10": "قيمة x وحدها ليست حلًا لنظام بمتغيرين؛ استرجع y واكتب الحل على صورة (x, y).",
    "M11": "راجع قوانين القوى والجذور قبل متابعة خطوات التحليل.",
    "M12": "تتبّع كل فرع ناتج عن التحليل أو الجذر ولا تتوقف بعد أول حل.",
    "M14": "الجذر التكعيبي لعدد حقيقي يعطي قيمة حقيقية واحدة، وليس ± مثل الجذر التربيعي.",
    "M15": "ثبّت ترتيب الزوج المرتب دائمًا: (x, y)، وليس (y, x).",
}

SKILL_LABELS = {
    "E02":"استخراج العامل المشترك",
    "E03":"خاصية الضرب الصفري",
    "E05":"فرق مربعين",
    "E06":"مجموع/فرق مكعبين",
    "E07":"التعرف إلى الصورة التربيعية",
    "E08":"التعويض بمتغير بديل",
    "E09":"الرجوع من المتغير البديل إلى x",
    "LQ01":"عزل متغير من المعادلة الخطية",
    "LQ02":"التعويض في النظام الخطي–التربيعي",
    "LQ03":"حل المعادلة الناتجة",
    "LQ04":"استرجاع المتغير الثاني والتحقق",
    "QQ01":"اختزال النظام التربيعي–التربيعي",
    "QQ02":"إيجاد جميع الأزواج المرتبة",
    "SYS01":"تفسير عدد حلول النظام",
}

STATUS_AR = {
    "mastered":"متقن",
    "developing":"قيد التطور",
    "at_risk":"يحتاج مراجعة",
    "insufficient_evidence":"أدلة غير كافية",
    "high_confidence":"احتمال مرتفع",
    "suspected":"مشتبه به",
}

st.markdown(
    """
    <style>
      .block-container {max-width: 820px; padding-top: 1.8rem;}
      html, body, [class*="css"] {font-family: Arial, sans-serif;}
      .brand {text-align:center; margin-bottom:0;}
      .subtitle {text-align:center; direction:rtl; color:#666; margin-bottom:1.2rem;}
      .rtl {direction:rtl; text-align:right;}
      .section-chip {
          direction:rtl; text-align:right; background:#f7f7f9;
          border-radius:10px; padding:9px 12px; margin:8px 0 18px 0;
          font-weight:600;
      }
      .small-note {direction:rtl; text-align:right; color:#666; font-size:.88rem;}
      [data-testid="stMetricValue"] {direction:ltr;}
      [data-testid="stMetricLabel"] {direction:rtl;}
    </style>
    """,
    unsafe_allow_html=True,
)

base = Path(__file__).parent
questions = json.loads((base / "question_bank.json").read_text(encoding="utf-8"))
question_bank = {q["id"]: q for q in questions}

defaults = {
    "stage":"intro",
    "current":0,
    "answers":{},
    "student_code":"",
    "report":None,
    "participant_id":uuid4().hex[:8].upper(),
    "test_started_at":None,
    "save_status":None,
}
for k,v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

def reset_test():
    st.session_state.stage = "intro"
    st.session_state.current = 0
    st.session_state.answers = {}
    st.session_state.report = None
    st.session_state.participant_id = uuid4().hex[:8].upper()
    st.session_state.test_started_at = None
    st.session_state.save_status = None

def save_pilot_result_local(student_code, responses, report):
    path = base / "pilot_results.csv"
    exists = path.exists()
    correct = sum(
        1 for qid, ans in responses.items()
        if ans == question_bank[qid]["correct"]
    )
    detected = [
        m for m, info in report["misconceptions"].items()
        if info["status"] in {"suspected","high_confidence"}
    ]
    wrong_ids = [
        qid for qid, ans in responses.items()
        if ans != question_bank[qid]["correct"]
    ]
    with path.open("a", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        if not exists:
            w.writerow([
                "timestamp","student_code","correct","total",
                "wrong_question_ids","detected_misconceptions","responses_json"
            ])
        w.writerow([
            datetime.now().isoformat(timespec="seconds"),
            student_code or "ANON",
            correct,
            len(questions),
            "|".join(wrong_ids),
            "|".join(sorted(detected)),
            json.dumps(responses, ensure_ascii=False),
        ])

@st.cache_resource(show_spinner=False)
def get_supabase_client() -> Client:
    """Create one server-side Supabase client without exposing its secret."""
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

def save_pilot_result_cloud(student_code, responses, report):
    """Save one complete attempt and its item-level evidence to Supabase."""
    client = get_supabase_client()
    return save_attempt_cloud(
        client=client,
        questions=questions,
        question_bank=question_bank,
        student_code=student_code,
        participant_id=st.session_state.participant_id,
        responses=responses,
        report=report,
        started_at=st.session_state.test_started_at,
    )

def save_pilot_result(student_code, responses, report):
    """Always keep a local backup, then attempt the secure cloud save."""
    save_pilot_result_local(student_code, responses, report)
    try:
        attempt_id = save_pilot_result_cloud(student_code, responses, report)
        return {
            "cloud_saved": True,
            "message": "تم حفظ المحاولة بأمان في قاعدة البيانات.",
            "attempt_id": attempt_id,
        }
    except Exception as exc:
        return {
            "cloud_saved": False,
            "message": (
                "حُفظت المحاولة محليًا، لكن تعذر إرسالها إلى قاعدة البيانات. "
                "تحقق من الإنترنت وإعدادات Supabase."
            ),
            "technical_error": str(exc),
        }

st.markdown('<div class="brand"><h1>🧠 فَهِم | Fahim</h1></div>', unsafe_allow_html=True)
st.markdown(
    '<div class="subtitle">تشخيص ذكي للفجوات وأنماط الخطأ في الرياضيات</div>',
    unsafe_allow_html=True
)

if st.session_state.stage == "intro":
    st.markdown("### النسخة التجريبية V0.3")
    st.markdown(
        """
        <div class="rtl">
        اختبار تشخيصي من <b>24 سؤالًا</b>. الهدف ليس إعطاء درجة فقط،
        بل تحديد نمط الخطأ المتكرر والمهارة التي تحتاج تدخلاً.
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.info("استخدم رمز طالب مجهول مثل S001، ولا تدخل الاسم الحقيقي.")
    code = st.text_input("رمز الطالب (اختياري)", value=st.session_state.student_code, placeholder="مثال: S001")
    st.session_state.student_code = code.strip()
    st.caption("MVP تجريبي؛ الأوزان والعتبات لم تُعاير سيكومتريًا بعد.")
    if st.button("ابدأ الاختبار", use_container_width=True, type="primary"):
        st.session_state.test_started_at = datetime.now(timezone.utc).isoformat()
        st.session_state.stage = "test"
        st.rerun()

elif st.session_state.stage == "test":
    total = len(questions)
    # Keep the index valid even if navigation restores an old session state.
    idx = max(0, min(st.session_state.current, total - 1))
    st.session_state.current = idx
    q = questions[idx]

    st.progress((idx + 1) / total, text=f"السؤال {idx + 1} من {total}")
    st.markdown(f'<div class="section-chip">{q["section"]}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="rtl"><h3>{q["title"]}</h3></div>', unsafe_allow_html=True)
    st.latex(q["latex"])

    opts = ["A","B","C","D"]
    previous = st.session_state.answers.get(q["id"])
    index = opts.index(previous) if previous in opts else None

    selected = st.radio(
        "اختر الإجابة",
        opts,
        index=index,
        format_func=lambda key: f"{key})  {q['options'][key]}",
        key=f"radio_{q['id']}",
    )

    c1,c2 = st.columns(2)
    with c1:
        if st.button("السابق", use_container_width=True, disabled=(idx == 0)):
            if selected:
                st.session_state.answers[q["id"]] = selected
            st.session_state.current = max(0, st.session_state.current - 1)
            st.rerun()

    with c2:
        last = idx == total - 1
        if st.button("إنهاء وتحليل" if last else "التالي", use_container_width=True, type="primary"):
            if not selected:
                st.warning("اختر إجابة قبل المتابعة.")
            else:
                st.session_state.answers[q["id"]] = selected
                if last:
                    report = score_student(question_bank, st.session_state.answers)
                    st.session_state.report = report
                    st.session_state.save_status = save_pilot_result(
                        st.session_state.student_code,
                        st.session_state.answers,
                        report,
                    )
                    st.session_state.stage = "report"
                else:
                    st.session_state.current = min(total - 1, st.session_state.current + 1)
                st.rerun()

    st.caption(f"السؤال {idx+1}/{total} · الإجابات المحفوظة: {len(st.session_state.answers)}")

elif st.session_state.stage == "report":
    responses = st.session_state.answers
    report = st.session_state.report or score_student(question_bank, responses)

    correct = sum(1 for qid, ans in responses.items() if ans == question_bank[qid]["correct"])
    pct = 100 * correct / len(questions)
    wrong_ids = [
        qid for qid, ans in responses.items()
        if ans != question_bank[qid]["correct"]
    ]

    st.success("اكتمل التحليل.")
    save_status = st.session_state.save_status
    if save_status:
        if save_status.get("cloud_saved"):
            st.success(save_status["message"], icon="☁️")
        else:
            st.warning(save_status["message"], icon="⚠️")
    c1,c2 = st.columns(2)
    c1.metric("الإجابات الصحيحة", f"{correct}/{len(questions)}")
    c2.metric("النسبة", f"{pct:.1f}%")

    student_tab, teacher_tab = st.tabs(["تقرير الطالب","تقرير المعلم"])

    with student_tab:
        st.markdown("### ماذا تتقن جيدًا؟")
        mastered = [
            (s,info) for s,info in report["skills"].items()
            if info["status"] == "mastered"
        ]
        if mastered:
            for s,info in sorted(mastered, key=lambda z:z[1]["score"], reverse=True)[:5]:
                st.write(f"✅ **{SKILL_LABELS.get(s,s)}** — {info['score']*100:.0f}%")
        else:
            st.info("لا توجد أدلة كافية بعد لتحديد مهارات متقنة بثقة.")

        st.markdown("### ما الذي نعالجه أولًا؟")
        if not report["next_interventions"]:
            st.info("لا توجد أولوية علاجية موثوقة بما يكفي في هذه المحاولة.")
        else:
            for rank,item in enumerate(report["next_interventions"],1):
                code = item["code"]
                if item["type"] == "misconception":
                    st.warning(
                        f"**{rank}. {MISCONCEPTION_LABELS.get(code,code)}**\n\n"
                        f"{REMEDIATION.get(code,'')}"
                    )
                else:
                    st.warning(f"**{rank}. راجع مهارة: {SKILL_LABELS.get(code,code)}**")

        detected = [
            (m,info) for m,info in report["misconceptions"].items()
            if info["status"] in {"suspected","high_confidence"}
        ]
        if detected:
            st.markdown("### أنماط خطأ متكررة")
            for m,info in sorted(detected, key=lambda z:z[1]["score"], reverse=True):
                st.write(
                    f"• **{MISCONCEPTION_LABELS.get(m,m)}** — "
                    f"{STATUS_AR.get(info['status'],info['status'])} · "
                    f"{info['evidence_items']} أدلة مستقلة"
                )

    with teacher_tab:
        st.markdown("### ملخص المحاولة")
        st.write(f"**الأسئلة الخاطئة:** {', '.join(wrong_ids) if wrong_ids else 'لا يوجد'}")

        st.markdown("### مصدر كل إشارة تشخيصية")
        evidence_rows = []
        for m,info in report["misconceptions"].items():
            for ev in info.get("evidence_details", []):
                qid = ev["question_id"]
                evidence_rows.append({
                    "السؤال": qid,
                    "إجابة الطالب": ev["answer"],
                    "الإجابة الصحيحة": question_bank[qid]["correct"],
                    "النمط": MISCONCEPTION_LABELS.get(m,m),
                    "الرمز": m,
                    "وزن الدليل": ev["weight"],
                })
        if evidence_rows:
            st.dataframe(evidence_rows, use_container_width=True, hide_index=True)
        else:
            st.info("لا توجد إشارات إلى أنماط خطأ محددة من الاختيارات الخاطئة.")

        st.markdown("### ملف المهارات")
        skill_rows = []
        for code,info in sorted(report["skills"].items()):
            explanation = ""
            if info["interpretation"] == "specific_pattern_detected":
                explanation = "مفسَّر جزئيًا بنمط خطأ محدد: " + ", ".join(info["explained_by"])
            else:
                explanation = "إشارة مهارية عامة"
            skill_rows.append({
                "المهارة": SKILL_LABELS.get(code,code),
                "الدقة": f"{info['score']*100:.0f}%",
                "الحالة": STATUS_AR.get(info["status"],info["status"]),
                "عدد الأدلة": info["evidence_items"],
                "التفسير": explanation,
            })
        st.dataframe(skill_rows, use_container_width=True, hide_index=True)

        st.markdown("### تحليل جميع البنود")
        rows = []
        for q in questions:
            ans = responses.get(q["id"])
            signal = ""
            if ans != q["correct"]:
                d = q.get("distractors",{}).get(ans)
                if d:
                    signal = d["misconception"]
            rows.append({
                "السؤال":q["id"],
                "إجابة الطالب":ans,
                "الصحيح":q["correct"],
                "النتيجة":"✓" if ans == q["correct"] else "✗",
                "الإشارة":signal,
            })
        st.dataframe(rows, use_container_width=True, hide_index=True)

        st.caption(
            "هذه النتائج لأغراض التجربة الأولية فقط. لا ينبغي التعامل مع مؤشر نمط الخطأ "
            "كاحتمال إحصائي معاير قبل التحقق منه باستخدام بيانات حقيقية."
        )

    st.divider()
    if st.button("بدء محاولة جديدة", use_container_width=True):
        reset_test()
        st.rerun()
