"""
Тести агента в LangSmith.

Два оцінювачі (evaluators):
  1. tool_check  — ПЕРЕВІРКА КОДОМ (детермінована, без LLM):
       • питання про ФРЕКС  -> агент ОБОВ'ЯЗКОВО викликав search_site;
       • стороннє питання   -> агент НЕ викликав жодного інструмента (одразу відмовив).
  2. llm_judge   — LLM-as-a-Judge: окрема модель-суддя (JUDGE_MODEL, за замовчуванням
       gpt-6.1-sol) читає питання, траєкторію і відповідь та вирішує, чи агент
       правильно відреагував (відповів по суті з сайту / відмовив на сторонню тему).

Запуск:
    python evals.py              # прогнати тести (датасет створиться автоматично)
    python evals.py --recreate   # перестворити датасет з прикладів нижче
Результати: smith.langchain.com -> Datasets & Experiments -> frex-agent-tests
"""

import os
import sys

from dotenv import load_dotenv
from langchain.chat_models import init_chat_model
from langsmith import Client, evaluate
from pydantic import BaseModel, Field

load_dotenv()

from agent import MODEL, final_answer, run, trajectory  # noqa: E402

DATASET = "frex-agent-tests"
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "openai:gpt-6.1-sol")

# ---------------------------------------------------------------------------
# Тестові сценарії
#   type = "faculty"   — питання про факультет (має шукати на сайті)
#   type = "off_topic" — стороннє питання (має відмовити, не виходячи за тему)
# ---------------------------------------------------------------------------
EXAMPLES = [
    {"question": "Коли був заснований ФРЕКС?", "type": "faculty"},
    {"question": "Хто декан факультету радіофізики, електроніки та комп'ютерних систем?", "type": "faculty"},
    {"question": "Які кафедри є на ФРЕКС?", "type": "faculty"},
    {"question": "Напиши вірш про осінь", "type": "off_topic"},
    {"question": "Яка столиця Франції?", "type": "off_topic"},
]

EXPECTED_BEHAVIOUR = {
    "faculty": "Агент має знайти інформацію на сайті rex.knu.ua (через пошук) і відповісти "
               "по суті, спираючись на знайдені сторінки, з посиланням на джерело. "
               "Якщо інформації на сайті немає — чесно сказати про це, а не вигадувати.",
    "off_topic": "Питання не стосується факультету. Агент має ввічливо відмовити і сказати, "
                 "що відповідає лише на питання про ФРЕКС, і НЕ відповідати по суті.",
}


def ensure_dataset(client: Client, recreate: bool = False) -> None:
    """Створює датасет у LangSmith, якщо його ще немає."""
    if client.has_dataset(dataset_name=DATASET):
        if not recreate:
            return
        client.delete_dataset(dataset_name=DATASET)

    ds = client.create_dataset(DATASET, description="Тести веб-агента ФРЕКС (диплом)")
    client.create_examples(
        dataset_id=ds.id,
        inputs=[{"question": e["question"]} for e in EXAMPLES],
        outputs=[{"type": e["type"], "expected": EXPECTED_BEHAVIOUR[e["type"]]} for e in EXAMPLES],
    )
    print(f"Створено датасет '{DATASET}' з {len(EXAMPLES)} прикладів")


# ---------------------------------------------------------------------------
# Ціль тестування: запускає агента і повертає відповідь + траєкторію
# ---------------------------------------------------------------------------
def target(inputs: dict) -> dict:
    state = run(inputs["question"])
    steps = trajectory(state)
    return {
        "answer": final_answer(state),
        "tools": [s["tool"] for s in steps],
        "trajectory": [
            {"tool": s["tool"], "args": s["args"], "result": s["result"][:1500]} for s in steps
        ],
    }


# ---------------------------------------------------------------------------
# Оцінювач 1: перевірка кодом — чи правильно агент використав інструменти
# ---------------------------------------------------------------------------
def tool_check(inputs: dict, outputs: dict, reference_outputs: dict) -> dict:
    tools = outputs.get("tools", [])
    if reference_outputs["type"] == "faculty":
        ok = "search_site" in tools
        comment = (f"search_site викликано (кроки: {tools})" if ok
                   else f"search_site НЕ викликано — агент відповів без пошуку (кроки: {tools})")
    else:
        ok = len(tools) == 0
        comment = ("Стороннє питання: інструменти не викликались — правильно" if ok
                   else f"Стороннє питання, але агент викликав інструменти: {tools}")
    return {"key": "tool_check", "score": int(ok), "comment": comment}


# ---------------------------------------------------------------------------
# Оцінювач 2: LLM-as-a-Judge
# ---------------------------------------------------------------------------
class Verdict(BaseModel):
    reasoning: str = Field(description="Коротке пояснення українською, чому таке рішення")
    correct: bool = Field(description="True, якщо агент відреагував правильно")


JUDGE_PROMPT = """Ти — суворий суддя, який оцінює роботу веб-агента факультету ФРЕКС КНУ.
Агент має відповідати лише на питання про факультет, використовуючи сайт rex.knu.ua,
а на сторонні питання — ввічливо відмовляти.

ПИТАННЯ КОРИСТУВАЧА:
{question}

ОЧІКУВАНА ПОВЕДІНКА:
{expected}

ТРАЄКТОРІЯ АГЕНТА (виклики інструментів і що вони повернули):
{trajectory}

ФІНАЛЬНА ВІДПОВІДЬ АГЕНТА:
{answer}

Оціни, чи агент відреагував правильно згідно з очікуваною поведінкою.
Для питань про факультет перевір, що відповідь спирається на дані з траєкторії,
а не вигадана. Для сторонніх питань — що агент відмовив і не відповів по суті."""

_judge = None


def llm_judge(inputs: dict, outputs: dict, reference_outputs: dict) -> dict:
    global _judge
    if _judge is None:
        _judge = init_chat_model(JUDGE_MODEL).with_structured_output(Verdict)

    traj = "\n".join(
        f"- {s['tool']}({s['args']}) -> {s['result'][:600]}" for s in outputs.get("trajectory", [])
    ) or "(інструменти не викликались)"

    verdict: Verdict = _judge.invoke(JUDGE_PROMPT.format(
        question=inputs["question"],
        expected=reference_outputs["expected"],
        trajectory=traj,
        answer=outputs.get("answer", ""),
    ))
    return {"key": "llm_judge", "score": int(verdict.correct), "comment": verdict.reasoning}


# ---------------------------------------------------------------------------
# Запуск
# ---------------------------------------------------------------------------
def run_tests(recreate: bool = False) -> list[dict]:
    """Проганяє агента по датасету і повертає рядки результатів (для консолі та UI)."""
    client = Client()
    ensure_dataset(client, recreate)

    results = evaluate(
        target,
        data=DATASET,
        evaluators=[tool_check, llm_judge],
        experiment_prefix=MODEL.split(":")[-1],
        metadata={"model": MODEL, "judge": JUDGE_MODEL},
        max_concurrency=2,
    )

    rows = []
    for r in results:
        ex, run_ = r["example"], r["run"]
        scores = {e.key: (e.score, e.comment) for e in r["evaluation_results"]["results"]}
        rows.append({
            "question": ex.inputs["question"],
            "type": ex.outputs["type"],
            "answer": (run_.outputs or {}).get("answer", "") if run_ else "",
            "tools": (run_.outputs or {}).get("tools", []) if run_ else [],
            "tool_check": scores.get("tool_check", (None, ""))[0],
            "tool_check_comment": scores.get("tool_check", (None, ""))[1],
            "llm_judge": scores.get("llm_judge", (None, ""))[0],
            "llm_judge_comment": scores.get("llm_judge", (None, ""))[1],
        })
    return rows


if __name__ == "__main__":
    rows = run_tests(recreate="--recreate" in sys.argv)
    print(f"\nАгент: {MODEL} | Суддя: {JUDGE_MODEL}\n")
    for i, r in enumerate(rows, 1):
        mark = lambda s: "OK " if s == 1 else "FAIL"  # noqa: E731
        print(f"{i}. [{r['type']}] {r['question']}")
        print(f"   tool_check: {mark(r['tool_check'])} — {r['tool_check_comment']}")
        print(f"   llm_judge:  {mark(r['llm_judge'])} — {r['llm_judge_comment']}")
    passed = sum(1 for r in rows if r["tool_check"] == 1 and r["llm_judge"] == 1)
    print(f"\nПройдено повністю: {passed}/{len(rows)}")
    print("Детально: smith.langchain.com -> Datasets & Experiments -> " + DATASET)
