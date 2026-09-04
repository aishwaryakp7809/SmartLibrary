import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
RULES_FILE = BASE_DIR / "library_rules.txt"


def load_library_rules():
    if not RULES_FILE.exists():
        return "No library rules file was found."

    try:
        return RULES_FILE.read_text(encoding="utf-8")
    except Exception:
        return "Unable to read library rules."


def format_books(books):
    if not books:
        return "No book data is currently available."

    lines = []

    for book_id, book in books.items():
        title = book.get("title", "Unknown")
        author = book.get("author", "Unknown")
        subject = book.get("subject", "Unknown")
        available = book.get("available_copies", 0)
        total = book.get("total_copies", 0)
        rack = book.get("rack", "Unknown")

        lines.append(
            f"- ID: {book_id} | "
            f"Title: {title} | "
            f"Author: {author} | "
            f"Subject: {subject} | "
            f"Available: {available}/{total} | "
            f"Rack: {rack}"
        )

    return "\n".join(lines)


def format_seats(zones):
    if not zones:
        return "No seat data is currently available."

    lines = []

    for zone_id, zone in zones.items():
        name = zone.get("name", zone_id)
        total = int(zone.get("total", 0))
        occupied = int(zone.get("occupied", 0))
        available = max(total - occupied, 0)

        lines.append(
            f"- {name} | "
            f"Total: {total} | "
            f"Occupied: {occupied} | "
            f"Available: {available}"
        )

    return "\n".join(lines)


def format_history(history):
    if not history:
        return "No previous conversation."

    recent = history[-10:]
    lines = []

    for item in recent:
        if not isinstance(item, dict):
            continue

        question = item.get("question") or item.get("user") or ""
        answer = item.get("answer") or item.get("assistant") or ""

        if question:
            lines.append(f"Student: {question}")

        if answer:
            lines.append(f"Assistant: {answer}")

    return "\n".join(lines) if lines else "No previous conversation."


def ask_library(question, books_data=None, zones_data=None, conversation_history=None):

    api_key = os.getenv("OPENROUTER_API_KEY")

    if not api_key:
        return "AI assistant is temporarily unavailable because the OpenRouter API key is not configured."

    books_data = books_data or {}
    zones_data = zones_data or {}
    conversation_history = conversation_history or []

    rules = load_library_rules()
    books_text = format_books(books_data)
    seats_text = format_seats(zones_data)
    history_text = format_history(conversation_history)

    system_prompt = f"""
You are SmartLibrary AI Assistant.

You are an AI assistant for a college library website.

Your job is to answer student questions clearly, accurately and politely.

IMPORTANT:
1. Use the library rules below for library-policy questions.
2. Use the CURRENT BOOK DATA for book availability questions.
3. Use the CURRENT SEAT DATA for seat availability questions.
4. Never invent book availability, seat availability, rack numbers or library rules.
5. If a requested book is unavailable, clearly say that it is currently unavailable.
6. If the student asks a follow-up question such as:
   "What about that one?"
   "Where is it?"
   "Is it available?"
   use the conversation history to understand what they mean.
7. Current Firebase data is more important than old conversation information.
8. If the question is unrelated to the library, politely say that you mainly help with SmartLibrary services.
9. Keep answers concise and easy for students to understand.
10. You can use emojis when appropriate, but don't overuse them.

LIBRARY RULES:
{rules}

CURRENT BOOK DATA FROM FIREBASE:
{books_text}

CURRENT SEAT DATA FROM FIREBASE:
{seats_text}

RECENT CONVERSATION:
{history_text}
"""

    try:
        client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key
        )

        response = client.chat.completions.create(
            model="openrouter/free",
            messages=[
                {
                    "role": "system",
                    "content": system_prompt
                },
                {
                    "role": "user",
                    "content": question
                }
            ],
            temperature=0.2,
            max_tokens=500
        )

        answer = response.choices[0].message.content

        if not answer:
            return "Sorry, I couldn't generate an answer right now."

        return answer.strip()

    except Exception as error:
        print("OPENROUTER ERROR:", error)
        return "Sorry, the AI assistant is temporarily unavailable. Please try again."