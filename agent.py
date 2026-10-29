"""
Етап 1: простий пошуковий веб-агент.

Модель обирається в .env (змінна MODEL):
  - groq:meta-llama/llama-4-scout-17b-16e-instruct  — безкоштовно, хмара Groq (потрібен GROQ_API_KEY)
  - openai:gpt-6-luna                               — дуже дешево, хмара OpenAI (потрібен OPENAI_API_KEY)
  - ollama:qwen3.5:9b                                — безкоштовно, локально на твоєму ПК (Ollama)
  - anthropic:claude-sonnet-5-5                      — платно (потрібен ANTHROPIC_API_KEY)

Агент відповідає на питання про сайт факультету (rex.knu.ua).
Інструменти:
  - search_site  — пошук сторінок сайту через пошукову систему (site:rex.knu.ua)
  - fetch_page   — завантаження сторінки: заголовок, текст і посилання

Запуск:
    python agent.py "Хто завідувач кафедри комп'ютерної інженерії?"
"""

import os
import sys
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.tools import tool

load_dotenv()  # підтягує MODEL, ключі і LANGSMITH_* з файлу .env

# ---------------------------------------------------------------------------
# Налаштування
# ---------------------------------------------------------------------------
SITE_DOMAIN = "rex.knu.ua"
MODEL = os.getenv("MODEL", "groq:meta-llama/llama-4-scout-17b-16e-instruct")
MAX_PAGE_CHARS = 3000                   # скільки тексту сторінки віддаємо моделі
MAX_LINKS = 40                          # скільки посилань зі сторінки показуємо
HEADERS = {"User-Agent": "Mozilla/5.0 (diploma-web-agent; student project)"}


def _is_allowed(url: str) -> bool:
    """Агент може ходити лише по сайту факультету."""
    host = urlparse(url).netloc.lower()
    return host == SITE_DOMAIN or host.endswith("." + SITE_DOMAIN)


# ---------------------------------------------------------------------------
# Інструменти (tools). Docstring — це опис, який бачить модель,
# тому він важливий: саме за ним модель вирішує, коли викликати інструмент.
# ---------------------------------------------------------------------------
@tool
def search_site(query: str) -> str:
    """Шукає сторінки на сайті факультету rex.knu.ua за ключовими словами.
    Повертає список результатів: заголовок, URL і короткий фрагмент.
    Використовуй, коли не знаєш, на якій сторінці потрібна інформація."""
    try:
        from ddgs import DDGS
        results = DDGS().text(f"site:{SITE_DOMAIN} {query}", max_results=6)
    except Exception as e:  # пошуковик іноді обмежує запити
        return f"Помилка пошуку: {e}. Спробуй fetch_page з головної сторінки https://{SITE_DOMAIN}/"

    if not results:
        return "Нічого не знайдено. Спробуй інші ключові слова або почни з головної сторінки."

    lines = []
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r.get('title')}\n   URL: {r.get('href')}\n   {r.get('body')}")
    return "\n".join(lines)


@tool
def fetch_page(url: str) -> str:
    """Завантажує сторінку сайту rex.knu.ua і повертає її заголовок,
    основний текст і список посилань (текст -> URL).
    Використовуй, щоб прочитати вміст сторінки або перейти далі за посиланнями."""
    if not _is_allowed(url):
        return f"Відмовлено: дозволено відкривати лише сторінки {SITE_DOMAIN}."

    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except requests.RequestException as e:
        return f"Не вдалося завантажити {url}: {e}"

    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()

    title = soup.title.get_text(strip=True) if soup.title else "(без заголовка)"
    text = " ".join(soup.get_text(separator=" ").split())[:MAX_PAGE_CHARS]

    links, seen = [], set()
    for a in soup.find_all("a", href=True):
        href = urljoin(url, a["href"]).split("#")[0]
        label = a.get_text(strip=True)
        if label and _is_allowed(href) and href not in seen:
            seen.add(href)
            links.append(f"- {label[:80]} -> {href}")
        if len(links) >= MAX_LINKS:
            break

    return f"ЗАГОЛОВОК: {title}\nURL: {url}\n\nТЕКСТ:\n{text}\n\nПОСИЛАННЯ:\n" + "\n".join(links)


# ---------------------------------------------------------------------------
# Агент
# ---------------------------------------------------------------------------
SYSTEM_PROMPT = f"""Ти — веб-агент, який відповідає на питання про факультет радіофізики,
електроніки та комп'ютерних систем КНУ, використовуючи лише сайт https://{SITE_DOMAIN}/.

Правила:
1. Не відповідай з власних знань — спершу знайди інформацію на сайті.
2. Якщо не знаєш потрібної сторінки, використай search_site або почни з головної сторінки.
3. Читай сторінки через fetch_page і переходь за посиланнями, якщо потрібно.
4. Відповідай українською, коротко і точно. В кінці вкажи URL сторінки-джерела.
5. Якщо інформацію не знайдено, чесно скажи про це.
"""

agent = create_agent(
    model=MODEL,
    tools=[search_site, fetch_page],
    system_prompt=SYSTEM_PROMPT,
)


def run(question: str) -> dict:
    """Запускає агента і повертає фінальний стан (усі повідомлення)."""
    return agent.invoke(
        {"messages": [{"role": "user", "content": question}]},
        config={"recursion_limit": 25},  # захист від нескінченного циклу
    )


def print_trajectory(state: dict) -> None:
    """Друкує траєкторію: які інструменти і з якими аргументами викликав агент."""
    print("\n=== ТРАЄКТОРІЯ ===")
    step = 0
    for msg in state["messages"]:
        for call in getattr(msg, "tool_calls", None) or []:
            step += 1
            print(f"{step}. {call['name']}({call['args']})")
    print(f"Усього викликів інструментів: {step}")

    print("\n=== ВІДПОВІДЬ ===")
    final = state["messages"][-1].content
    if isinstance(final, list):  # деякі моделі повертають список блоків
        final = "".join(b.get("text", "") for b in final if isinstance(b, dict))
    print(final)


if __name__ == "__main__":
    q = " ".join(sys.argv[1:]) or "Хто завідувач кафедри комп'ютерної інженерії?"
    print(f"МОДЕЛЬ: {MODEL}")
    print(f"ПИТАННЯ: {q}")
    print_trajectory(run(q))
