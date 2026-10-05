"""لوحة المعلّم لمشروع فَهِم — قراءة فقط من Supabase."""

from collections import Counter
from datetime import datetime

import pandas as pd
import streamlit as st
from supabase import Client, create_client


st.set_page_config(
    page_title="فَهِم | لوحة المعلّم",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
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

st.markdown(
    """
    <style>
      .block-container {max-width: 1250px; padding-top: 1.4rem;}
      html, body, [class*="css"] {font-family: Arial, sans-serif;}
      .rtl {direction: rtl; text-align: right;}
      [data-testid="stMetricLabel"] {direction: rtl;}
      [data-testid="stMetricValue"] {direction: ltr;}
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource(show_spinner=False)
def get_client() -> Client:
    return create_client(st.secrets["SUPABASE_URL"], st.secrets["SUPABASE_KEY"])


@st.cache_data(ttl=60, show_spinner=False)
def load_data():
    client = get_client()
    students = client.table("students").select("id,student_code,classroom_id").execute().data or []
    attempts = (
        client.table("attempts")
        .select("id,student_id,assessment_code,correct_answers,total_questions,detected_patterns,started_at,completed_at")
        .order("completed_at", desc=True)
        .execute().data or []
    )
    responses = (
        client.table("responses")
        .select("attempt_id,question_id,selected_answer,correct_answer,is_correct,skill_id,misconception_code,evidence_weight")
        .execute().data or []
    )
    return students, attempts, responses


def parse_date(value):
    if not value:
        return "—"
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).strftime("%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return str(value)


def require_password():
    expected = st.secrets.get("TEACHER_PASSWORD", "")
    if not expected:
        st.error("أضف TEACHER_PASSWORD إلى ملف .streamlit/secrets.toml ثم أعد تشغيل اللوحة.")
        st.code('TEACHER_PASSWORD = "اكتب_كلمة_مرور_قوية_هنا"', language="toml")
        st.stop()
    if st.session_state.get("teacher_authenticated"):
        return
    st.markdown('<div class="rtl"><h2>🔐 دخول المعلّم</h2></div>', unsafe_allow_html=True)
    password = st.text_input("كلمة مرور لوحة المعلّم", type="password")
    if st.button("دخول", type="primary", use_container_width=True):
        if password == expected:
            st.session_state.teacher_authenticated = True
            st.rerun()
        else:
            st.error("كلمة المرور غير صحيحة.")
    st.stop()


require_password()

st.markdown('<div class="rtl"><h1>📊 فَهِم | لوحة المعلّم</h1></div>', unsafe_allow_html=True)
st.markdown('<div class="rtl">متابعة المحاولات وتحليل الأداء وأنماط الخطأ.</div>', unsafe_allow_html=True)

with st.sidebar:
    st.header("خيارات العرض")
    if st.button("تحديث البيانات", use_container_width=True):
        load_data.clear()
        st.rerun()
    if st.button("تسجيل الخروج", use_container_width=True):
        st.session_state.teacher_authenticated = False
        st.rerun()

try:
    students, attempts, responses = load_data()
except Exception as exc:
    st.error("تعذر تحميل بيانات اللوحة. تحقق من الاتصال وصلاحيات Supabase.")
    with st.expander("التفاصيل التقنية"):
        st.code(str(exc))
    st.stop()

student_codes = {row["id"]: row.get("student_code", "غير معروف") for row in students}
available_students = sorted(set(student_codes.values()))

with st.sidebar:
    selected_student = st.selectbox("الطالب", ["جميع الطلاب"] + available_students)
    assessment_codes = sorted({a.get("assessment_code", "") for a in attempts if a.get("assessment_code")})
    selected_assessment = st.selectbox("الاختبار", ["جميع الاختبارات"] + assessment_codes)

filtered_attempts = []
for attempt in attempts:
    code = student_codes.get(attempt.get("student_id"), "غير معروف")
    if selected_student != "جميع الطلاب" and code != selected_student:
        continue
    if selected_assessment != "جميع الاختبارات" and attempt.get("assessment_code") != selected_assessment:
        continue
    filtered_attempts.append(attempt)

attempt_ids = {a["id"] for a in filtered_attempts}
filtered_responses = [r for r in responses if r.get("attempt_id") in attempt_ids]

if not filtered_attempts:
    st.info("لا توجد محاولات مطابقة للاختيار الحالي.")
    st.stop()

scores = [100 * a["correct_answers"] / a["total_questions"] for a in filtered_attempts if a.get("total_questions")]
unique_students = {student_codes.get(a.get("student_id"), "غير معروف") for a in filtered_attempts}

c1, c2, c3, c4 = st.columns(4)
c1.metric("عدد الطلاب", len(unique_students))
c2.metric("عدد المحاولات", len(filtered_attempts))
c3.metric("متوسط الأداء", f"{sum(scores) / len(scores):.1f}%" if scores else "—")
c4.metric("إجابات محفوظة", len(filtered_responses))

st.markdown("### المحاولات")
attempt_rows = []
for a in filtered_attempts:
    total = a.get("total_questions") or 0
    correct = a.get("correct_answers") or 0
    attempt_rows.append({
        "الطالب": student_codes.get(a.get("student_id"), "غير معروف"),
        "الاختبار": a.get("assessment_code", "—"),
        "الصحيح": correct,
        "المجموع": total,
        "النسبة": round(100 * correct / total, 1) if total else 0,
        "أنماط الخطأ": "، ".join(a.get("detected_patterns") or []) or "—",
        "وقت الإكمال": parse_date(a.get("completed_at")),
        "معرّف المحاولة": a.get("id"),
    })
attempt_df = pd.DataFrame(attempt_rows)
st.dataframe(attempt_df, use_container_width=True, hide_index=True)

left, right = st.columns(2)
with left:
    st.markdown("### أكثر الأسئلة خطأً")
    wrong_questions = Counter(r.get("question_id") for r in filtered_responses if not r.get("is_correct"))
    wrong_df = pd.DataFrame([
        {"السؤال": qid, "عدد الأخطاء": count}
        for qid, count in wrong_questions.most_common()
    ])
    if wrong_df.empty:
        st.success("لا توجد إجابات خاطئة ضمن الاختيار الحالي.")
    else:
        st.bar_chart(wrong_df.set_index("السؤال"))
        st.dataframe(wrong_df, use_container_width=True, hide_index=True)

with right:
    st.markdown("### أنماط الخطأ الأكثر تكرارًا")
    pattern_counts = Counter(
        r.get("misconception_code") for r in filtered_responses
        if r.get("misconception_code")
    )
    pattern_df = pd.DataFrame([
        {
            "الرمز": code,
            "النمط": MISCONCEPTION_LABELS.get(code, code),
            "عدد الإشارات": count,
        }
        for code, count in pattern_counts.most_common()
    ])
    if pattern_df.empty:
        st.success("لا توجد أنماط خطأ مسجلة ضمن الاختيار الحالي.")
    else:
        st.bar_chart(pattern_df.set_index("الرمز")[["عدد الإشارات"]])
        st.dataframe(pattern_df, use_container_width=True, hide_index=True)

st.markdown("### تفاصيل محاولة واحدة")
labels = {
    row["معرّف المحاولة"]: (
        f'{row["الطالب"]} | {row["النسبة"]}% | {row["وقت الإكمال"]}'
    )
    for row in attempt_rows
}
selected_attempt_id = st.selectbox(
    "اختر محاولة",
    list(labels),
    format_func=lambda attempt_id: labels[attempt_id],
)
detail_rows = []
for r in responses:
    if r.get("attempt_id") != selected_attempt_id:
        continue
    code = r.get("misconception_code")
    detail_rows.append({
        "السؤال": r.get("question_id"),
        "إجابة الطالب": r.get("selected_answer"),
        "الإجابة الصحيحة": r.get("correct_answer"),
        "النتيجة": "✓" if r.get("is_correct") else "✗",
        "المهارة": r.get("skill_id") or "—",
        "نمط الخطأ": MISCONCEPTION_LABELS.get(code, code) if code else "—",
    })
st.dataframe(pd.DataFrame(detail_rows), use_container_width=True, hide_index=True)

csv_data = attempt_df.to_csv(index=False).encode("utf-8-sig")
st.download_button(
    "تنزيل ملخص المحاولات CSV",
    data=csv_data,
    file_name="fahim_attempts_report.csv",
    mime="text/csv",
    use_container_width=True,
)

st.caption("لوحة تجريبية؛ مؤشرات أنماط الخطأ تشخيصية أولية وليست تقديرات سيكومترية معايرة.")
