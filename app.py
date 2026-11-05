"""
Простий вебінтерфейс для агента (Streamlit).

Запуск: ui.bat   або   streamlit run app.py
Відкриється в браузері: http://localhost:8501
"""

import json

import streamlit as st

st.set_page_config(page_title="Веб-агент ФРЕКС", page_icon="🔎", layout="wide")

from agent import final_answer, run, trajectory  # noqa: E402

# Ховаємо службове меню Streamlit (Deploy, ⋮)
st.markdown("<style>[data-testid='stToolbar'], [data-testid='stDecoration'], #MainMenu {display: none;}</style>",
            unsafe_allow_html=True)

st.title("Веб-агент ФРЕКС")

# ---------------------------------------------------------------------------
# Питання -> відповідь + траєкторія.
# Тести (tool_check, llm_judge) — у LangSmith: tests.bat -> Datasets & Experiments.
# ---------------------------------------------------------------------------
examples = ["Коли був заснований ФРЕКС?", "Які кафедри є на ФРЕКС?", "Напиши вірш про осінь"]
pick = st.selectbox("Приклад питання", ["(своє питання)"] + examples)
question = st.text_input(
    "Питання", value="" if pick == "(своє питання)" else pick,
    placeholder="Наприклад: Хто завідувач кафедри комп'ютерної інженерії?",
)

if st.button("Запитати", type="primary", disabled=not question.strip()):
    with st.spinner("Агент працює: шукає і читає сторінки сайту..."):
        try:
            state = run(question.strip())
        except Exception as e:
            st.error(f"Помилка: {e}")
            st.stop()

    steps = trajectory(state)
    left, right = st.columns([3, 2])

    with left:
        st.subheader("Відповідь")
        st.markdown(final_answer(state))

    with right:
        st.subheader("Траєкторія")
        if not steps:
            st.info("Інструменти не викликались (агент відповів одразу).")
        for i, s in enumerate(steps, 1):
            with st.expander(f"{i}. {s['tool']}({json.dumps(s['args'], ensure_ascii=False)})"):
                st.text(s["result"][:3000])
        st.metric("Викликів інструментів", len(steps))
