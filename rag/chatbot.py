import os
from pathlib import Path

import faiss
import numpy as np
import streamlit as st

from dotenv import load_dotenv
from openai import OpenAI
from sentence_transformers import SentenceTransformer


# ============================================================
# PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


# ============================================================
# OPENROUTER
# ============================================================

api_key = os.getenv("OPENROUTER_API_KEY")

if not api_key:

    raise ValueError(
        "OPENROUTER_API_KEY is missing from .env"
    )


client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=api_key
)


# ============================================================
# LIBRARY RULES
# ============================================================

rules_file = BASE_DIR / "library_rules.txt"

if not rules_file.exists():

    raise FileNotFoundError(
        f"library_rules.txt not found:\n{rules_file}"
    )


with open(
    rules_file,
    "r",
    encoding="utf-8"
) as file:

    text = file.read()


# Split rules into useful chunks
chunks = [
    chunk.strip()
    for chunk in text.split("\n\n")
    if chunk.strip()
]


# ============================================================
# EMBEDDING MODEL
# ============================================================

@st.cache_resource
def load_embedding_model():

    return SentenceTransformer(
        "all-MiniLM-L6-v2"
    )


embedding_model = load_embedding_model()


# ============================================================
# CREATE FAISS INDEX
# ============================================================

embeddings = embedding_model.encode(
    chunks,
    convert_to_numpy=True,
    show_progress_bar=False
)


if embeddings.ndim == 1:

    embeddings = embeddings.reshape(
        1,
        -1
    )


dimension = embeddings.shape[1]


index = faiss.IndexFlatL2(
    dimension
)


index.add(
    embeddings.astype(
        np.float32
    )
)


# ============================================================
# HELPER: SEARCH LIBRARY RULES
# ============================================================

def search_rules(question):

    question_embedding = embedding_model.encode(
        [question],
        convert_to_numpy=True,
        show_progress_bar=False
    )


    k = min(
        5,
        len(chunks)
    )


    distances, indices = index.search(
        question_embedding.astype(
            np.float32
        ),
        k
    )


    relevant_chunks = []


    for i in indices[0]:

        if 0 <= i < len(chunks):

            relevant_chunks.append(
                chunks[i]
            )


    return "\n\n".join(
        relevant_chunks
    )


# ============================================================
# MAIN AI FUNCTION
# ============================================================

def ask_library(
    question,
    books_data=None,
    zones_data=None,
    conversation_history=None
):

    """
    Smart Library Assistant.

    Uses:

    1. Library rules
    2. Current Firebase book data
    3. Current Firebase seat data
    4. Previous conversation

    This allows the AI to understand follow-up questions.
    """


    question = question.strip()


    if not question:

        return (
            "Please enter a library-related question. "
            "I'm here to help! 😊"
        )


    # ========================================================
    # RULES CONTEXT
    # ========================================================

    rules_context = search_rules(
        question
    )


    # ========================================================
    # BOOK CONTEXT
    # ========================================================

    book_context = ""


    if books_data:

        book_lines = []


        total_available = 0

        total_copies = 0


        for book_id, book in books_data.items():

            available = int(
                book.get(
                    "available_copies",
                    0
                )
            )


            total = int(
                book.get(
                    "total_copies",
                    0
                )
            )


            total_available += available

            total_copies += total


            book_lines.append(

                f"""
Book ID: {book_id}
Title: {book.get('title', 'Unknown')}
Author: {book.get('author', 'Unknown')}
Subject: {book.get('subject', 'Unknown')}
Available Copies: {available}
Total Copies: {total}
Rack: {book.get('rack', 'Unknown')}
""".strip()

            )


        book_context = f"""

CURRENT BOOK AVAILABILITY

Total available copies:
{total_available}

Total copies in library:
{total_copies}

Book details:

{chr(10).join(book_lines)}

"""


    # ========================================================
    # SEAT CONTEXT
    # ========================================================

    seat_context = ""


    if zones_data:

        seat_lines = []


        total_seats = 0

        total_occupied = 0

        total_available_seats = 0


        for zone_id, zone in zones_data.items():

            total = int(
                zone.get(
                    "total",
                    0
                )
            )


            occupied = int(
                zone.get(
                    "occupied",
                    0
                )
            )


            available = max(
                total - occupied,
                0
            )


            total_seats += total

            total_occupied += occupied

            total_available_seats += available


            seat_lines.append(

                f"""
Zone ID: {zone_id}
Zone Name: {zone.get('name', zone_id)}
Total Seats: {total}
Occupied: {occupied}
Available: {available}
""".strip()

            )


        seat_context = f"""

CURRENT SEAT AVAILABILITY

Total seats:
{total_seats}

Occupied seats:
{total_occupied}

Available seats:
{total_available_seats}

Zone details:

{chr(10).join(seat_lines)}

"""


    # ========================================================
    # CONVERSATION HISTORY
    # ========================================================

    conversation_context = ""


    if conversation_history:

        history_lines = []


        # Keep the most recent conversations
        recent_history = conversation_history[-10:]


        for item in recent_history:

            user_question = str(
                item.get(
                    "question",
                    ""
                )
            )


            ai_answer = str(
                item.get(
                    "answer",
                    ""
                )
            )


            history_lines.append(

                f"""
Student:
{user_question}

SmartLibrary AI:
{ai_answer}
""".strip()

            )


        conversation_context = """

PREVIOUS CONVERSATION

The following messages are from the current
conversation.

Use them to understand follow-up questions.

Do not treat old availability information as
current availability. Always use CURRENT BOOK
AVAILABILITY and CURRENT SEAT AVAILABILITY for
current numbers.

""" + "\n\n".join(
            history_lines
        )


    # ========================================================
    # AI PROMPT
    # ========================================================

    prompt = f"""

You are the SmartLibrary AI Assistant.

You help students with ANY reasonable question
about their library.

You have access to:

1. Library rules
2. Current book availability
3. Current seat availability
4. Previous conversation


==================================================
IMPORTANT BEHAVIOUR
==================================================

Understand natural language.

The student does NOT need to use exact words.

For example:

"Is Python available?"

"Do you have Python?"

"Can I get the Python book?"

"Are there any copies of Python?"

These can all refer to the same book availability.


==================================================
FOLLOW-UP QUESTIONS
==================================================

IMPORTANT:

Understand short follow-up messages using
the previous conversation.

Examples:

Student:
Is Python Programming available?

AI:
Yes, 5 copies are available.

Student:
yes

The word "yes" is NOT an empty question.

Understand that the student is continuing
the previous conversation.

Give a useful response based on the previous
conversation.

Other examples:

"where is it?"

"how many?"

"can I borrow it?"

"what about that one?"

"is it available?"

"and the DBMS book?"

"what about seats?"

Use previous conversation to understand
what the student means.


==================================================
CURRENT DATA HAS PRIORITY
==================================================

For current book availability:

ALWAYS use CURRENT BOOK AVAILABILITY.

For current seat availability:

ALWAYS use CURRENT SEAT AVAILABILITY.

Never use an old number from conversation history
when a current number is available.


==================================================
BOOK QUESTIONS
==================================================

If the student asks about a specific book,
use the available data.

Give useful details such as:

- Title
- Author
- Subject
- Available copies
- Total copies
- Rack


==================================================
SEAT QUESTIONS
==================================================

For seat questions, use the live seat data.

You can answer:

- Total available seats
- Occupied seats
- Available seats
- Specific zone availability
- Which zone has more available seats
- Whether a zone is full


==================================================
LIBRARY RULE QUESTIONS
==================================================

Use the library rules for questions about:

- Library timings
- Borrowing limits
- Borrowing period
- Renewal
- Late return
- Study zones
- Membership
- College ID requirements


==================================================
COMBINED QUESTIONS
==================================================

You can combine information.

For example:

"Can I borrow Python and study in the silent zone?"

Answer using both:

- Book information
- Borrowing rules
- Silent zone information


==================================================
GENERAL LIBRARY QUESTIONS
==================================================

Try your best to answer any reasonable
library-related question using the information
provided.

Do NOT require the student to phrase the question
in a specific way.


==================================================
UNKNOWN INFORMATION
==================================================

Never invent library information.

If a specific detail is not available in the
provided library data, clearly say that the
information is not currently available.


==================================================
NON-LIBRARY QUESTIONS
==================================================

If the question is completely unrelated to the
library, politely say:

"I'm the SmartLibrary AI Assistant, so I can
help with library-related questions such as
books, seats, timings, borrowing and library
rules."


==================================================
RESPONSE STYLE
==================================================

Be:

- Helpful
- Friendly
- Clear
- Concise
- Student-friendly

Use simple language.

Do not unnecessarily repeat the entire database.

==================================================

LIBRARY RULES:

{rules_context}


{book_context}


{seat_context}


{conversation_context}


==================================================
CURRENT STUDENT QUESTION
==================================================

{question}


==================================================
ANSWER
==================================================

"""


    # ========================================================
    # CALL OPENROUTER
    # ========================================================

    response = client.chat.completions.create(

        model="openrouter/free",

        messages=[
            {
                "role": "user",
                "content": prompt
            }
        ]

    )


    answer = response.choices[
        0
    ].message.content


    return answer