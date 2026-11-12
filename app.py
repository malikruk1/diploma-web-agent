"""
Вебінтерфейс агента у формі чату (Streamlit).

Запуск: ui.bat   або   streamlit run app.py
Відкриється в браузері: http://localhost:8501
"""

import json

import streamlit as st

st.set_page_config(page_title="Веб-агент ФРЕКС", page_icon="🔎", layout="centered")

import importlib  # noqa: E402

import agent as _agent  # noqa: E402

# Перечитуємо agent.py, щоб зміни в ньому підхоплювались без перезапуску сайту
_agent = importlib.reload(_agent)
final_answer, run, trajectory = _agent.final_answer, _agent.run, _agent.trajectory

# Ховаємо службове меню Streamlit (Deploy, ⋮)
st.markdown("<style>[data-testid='stToolbar'], [data-testid='stDecoration'], #MainMenu {display: none;}</style>",
            unsafe_allow_html=True)

st.title("Веб-агент ФРЕКС")

# Історія чату: [{"role": "user"/"assistant", "content": str, "steps": [...]}]
if "chat" not in st.session_state:
    st.session_state.chat = []


def show_steps(steps: list[dict]) -> None:
    """Траєкторія під відповіддю агента (розгортається)."""
    title = f"Траєкторія: викликів інструментів — {len(steps)}"
    with st.expander(title):
        if not steps:
            st.write("Інструменти не викликались (агент відповів одразу).")
        for i, s in enumerate(steps, 1):
            st.markdown(f"**{i}. {s['tool']}**(`{json.dumps(s['args'], ensure_ascii=False)}`)")
            st.text(s["result"][:3000])


# Показуємо всі попередні повідомлення
for m in st.session_state.chat:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        if m["role"] == "assistant":
            show_steps(m.get("steps", []))

# Кнопки-приклади, поки чат порожній
question = None
if not st.session_state.chat:
    st.caption("Приклади питань:")
    cols = st.columns(3)
    for col, ex in zip(cols, ["Коли був заснований ФРЕКС?", "Які кафедри є на ФРЕКС?", "Напиши вірш про осінь"]):
        if col.button(ex, use_container_width=True):
            question = ex

typed = st.chat_input("Напишіть питання про факультет...")
question = typed or question

if question:
    # Історія для агента — лише тексти попередніх питань і відповідей
    history = [{"role": m["role"], "content": m["content"]} for m in st.session_state.chat]
    st.session_state.chat.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Агент працює: шукає і читає сторінки сайту..."):
            try:
                state = run(question, history)
                answer, steps = final_answer(state), trajectory(state)
            except Exception as e:
                answer, steps = f"Помилка: {e}", []
        st.markdown(answer)
        show_steps(steps)
    st.session_state.chat.append({"role": "assistant", "content": answer, "steps": steps})

# ---------------------------------------------------------------------------
# Бокова панель: очистити чат і запустити тести (результати — у LangSmith)
# ---------------------------------------------------------------------------
with st.sidebar:
    if st.button("Новий чат", use_container_width=True):
        st.session_state.chat = []
        st.rerun()

    st.divider()
    if st.button("Запустити тести в LangSmith", use_container_width=True):
        from evals import DATASET, LAST_EXPERIMENT, run_tests

        with st.spinner("Тести виконуються (1–3 хвилини)..."):
            try:
                run_tests()
            except Exception as e:
                st.error(f"Помилка: {e}")
                st.stop()
        st.session_state.tests_url = LAST_EXPERIMENT.get("url") or ""
        st.session_state.tests_done = True

    if st.session_state.get("tests_done"):
        st.success("Тести завершено.")
        if st.session_state.get("tests_url"):
            st.link_button("Відкрити результати в LangSmith", st.session_state.tests_url,
                           use_container_width=True)
        else:
            st.write("Результати: LangSmith → Datasets & Experiments → frex-agent-tests.")
