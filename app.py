"""
Простий вебінтерфейс для агента (Streamlit).

Запуск: ui.bat   або   streamlit run app.py
Відкриється в браузері: http://localhost:8501
"""

import json

import streamlit as st

st.set_page_config(page_title="Веб-агент ФРЕКС", page_icon="🔎", layout="wide")

from agent import MODEL, final_answer, run, trajectory  # noqa: E402

st.title("Веб-агент ФРЕКС")
st.caption(
    f"Дипломна робота: автоматизоване оцінювання веб-агентів · модель агента: `{MODEL}` · "
    "джерело: rex.knu.ua"
)

tab_ask, tab_tests = st.tabs(["Запитати агента", "Тести (LangSmith)"])

# ---------------------------------------------------------------------------
# Вкладка 1: питання -> відповідь + траєкторія
# ---------------------------------------------------------------------------
with tab_ask:
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

        st.caption("Повний трейс цього запуску — на smith.langchain.com, проєкт diploma-web-agent.")

# ---------------------------------------------------------------------------
# Вкладка 2: тести (tool_check + LLM-as-a-Judge)
# ---------------------------------------------------------------------------
with tab_tests:
    st.markdown(
        "**Два тести на кожне питання датасету:**\n"
        "- **tool_check** (перевірка кодом): на питання про ФРЕКС агент обов'язково викликав "
        "`search_site`; на стороннє питання — не викликав інструментів і відмовив.\n"
        "- **llm_judge** (LLM-as-a-Judge): окрема модель-суддя оцінює, чи агент правильно відреагував."
    )

    if st.button("Запустити тести", type="primary"):
        from evals import DATASET, JUDGE_MODEL, run_tests

        with st.spinner("Проганяю агента по датасету і оцінюю (1–2 хвилини)..."):
            try:
                rows = run_tests()
            except Exception as e:
                st.error(f"Помилка: {e}")
                st.stop()

        passed = sum(1 for r in rows if r["tool_check"] == 1 and r["llm_judge"] == 1)
        c1, c2, c3 = st.columns(3)
        c1.metric("Пройдено повністю", f"{passed}/{len(rows)}")
        c2.metric("tool_check", f"{sum(r['tool_check'] == 1 for r in rows)}/{len(rows)}")
        c3.metric("llm_judge", f"{sum(r['llm_judge'] == 1 for r in rows)}/{len(rows)}")

        mark = lambda s: "✅" if s == 1 else "❌"  # noqa: E731
        st.dataframe(
            [{
                "Питання": r["question"],
                "Тип": "про ФРЕКС" if r["type"] == "faculty" else "стороннє",
                "Інструменти": ", ".join(r["tools"]) or "—",
                "tool_check": mark(r["tool_check"]),
                "llm_judge": mark(r["llm_judge"]),
            } for r in rows],
            use_container_width=True, hide_index=True,
        )

        st.subheader("Деталі")
        for r in rows:
            with st.expander(f"{mark(r['tool_check'])}{mark(r['llm_judge'])}  {r['question']}"):
                st.markdown(f"**Відповідь агента:**\n\n{r['answer']}")
                st.markdown(f"**tool_check:** {r['tool_check_comment']}")
                st.markdown(f"**llm_judge** (`{JUDGE_MODEL}`): {r['llm_judge_comment']}")

        st.caption(f"Експеримент збережено в LangSmith: Datasets & Experiments → {DATASET}")
