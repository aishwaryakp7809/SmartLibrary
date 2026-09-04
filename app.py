import streamlit as st
import pandas as pd

from firebase_db import get_zones, get_books, db
from rag.chatbot import ask_library


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Smart Library Assistant",
    page_icon="📚",
    layout="wide"
)


# ============================================================
# TITLE
# ============================================================

st.title("📚 Smart Library Assistant")

st.write(
    "Your AI-powered library management system"
)

st.divider()


# ============================================================
# LIVE LIBRARY DASHBOARD
# ============================================================

@st.fragment(run_every="3s")
def live_library_dashboard():

    # --------------------------------------------------------
    # GET LIVE FIREBASE DATA
    # --------------------------------------------------------

    books_data = get_books()
    zones_data = get_zones()


    # ========================================================
    # BOOK AVAILABILITY
    # ========================================================

    st.header("📖 Book Availability")

    if books_data:

        books_list = []

        for book_id, book in books_data.items():

            books_list.append(
                {
                    "book_id": book_id,
                    "title": book.get("title", ""),
                    "author": book.get("author", ""),
                    "subject": book.get("subject", ""),
                    "available_copies": int(
                        book.get("available_copies", 0)
                    ),
                    "total_copies": int(
                        book.get("total_copies", 0)
                    ),
                    "rack": book.get("rack", "")
                }
            )

        books = pd.DataFrame(books_list)


        # ----------------------------------------------------
        # BOOK STATISTICS
        # ----------------------------------------------------

        total_titles = len(books)

        total_copies = int(
            books["total_copies"].sum()
        )

        available_copies = int(
            books["available_copies"].sum()
        )

        borrowed_copies = (
            total_copies - available_copies
        )


        col1, col2, col3 = st.columns(3)

        with col1:

            st.metric(
                "📚 Book Titles",
                total_titles
            )

        with col2:

            st.metric(
                "✅ Available Copies",
                available_copies
            )

        with col3:

            st.metric(
                "📕 Borrowed Copies",
                borrowed_copies
            )


        # ----------------------------------------------------
        # SEARCH BOOKS
        # ----------------------------------------------------

        st.subheader("🔍 Search Books")

        search = st.text_input(
            "Search by title, author or subject",
            placeholder="Example: Python",
            key="book_search"
        )


        if search.strip():

            search_text = search.strip()

            mask = books.astype(str).apply(
                lambda column: column.str.contains(
                    search_text,
                    case=False,
                    na=False
                )
            )

            results = books[
                mask.any(axis=1)
            ]

        else:

            results = books


        st.dataframe(
            results,
            width="stretch",
            hide_index=True
        )


        # ----------------------------------------------------
        # BORROW / RETURN
        # ----------------------------------------------------

        st.subheader(
            "📚 Borrow or Return a Book"
        )


        if not results.empty:

            book_options = {}

            for _, row in results.iterrows():

                label = (
                    str(row["book_id"])
                    + " - "
                    + str(row["title"])
                )

                book_options[label] = (
                    row["book_id"]
                )


            selected_label = st.selectbox(
                "Select a book",
                list(book_options.keys()),
                key="selected_book"
            )


            selected_book = book_options[
                selected_label
            ]


            selected_row = results[
                results["book_id"] == selected_book
            ].iloc[0]


            st.write(
                "**"
                + str(selected_row["title"])
                + "**"
            )

            st.write(
                "Available copies: **"
                + str(
                    selected_row["available_copies"]
                )
                + " / "
                + str(
                    selected_row["total_copies"]
                )
                + "**"
            )


            col1, col2 = st.columns(2)


            # ------------------------------------------------
            # BORROW
            # ------------------------------------------------

            with col1:

                if st.button(
                    "📕 Borrow Book",
                    key="borrow_book",
                    use_container_width=True
                ):

                    ref = db.reference(
                        "books/"
                        + str(selected_book)
                    )

                    current_book = ref.get()


                    if current_book is None:

                        st.error(
                            "Book not found."
                        )

                    else:

                        available = int(
                            current_book.get(
                                "available_copies",
                                0
                            )
                        )


                        if available > 0:

                            ref.update(
                                {
                                    "available_copies":
                                    available - 1
                                }
                            )

                            st.success(
                                "✅ Book borrowed successfully!"
                            )

                        else:

                            st.warning(
                                "❌ No copies available."
                            )


            # ------------------------------------------------
            # RETURN
            # ------------------------------------------------

            with col2:

                if st.button(
                    "↩️ Return Book",
                    key="return_book",
                    use_container_width=True
                ):

                    ref = db.reference(
                        "books/"
                        + str(selected_book)
                    )

                    current_book = ref.get()


                    if current_book is None:

                        st.error(
                            "Book not found."
                        )

                    else:

                        available = int(
                            current_book.get(
                                "available_copies",
                                0
                            )
                        )

                        total = int(
                            current_book.get(
                                "total_copies",
                                0
                            )
                        )


                        if available < total:

                            ref.update(
                                {
                                    "available_copies":
                                    available + 1
                                }
                            )

                            st.success(
                                "✅ Book returned successfully!"
                            )

                        else:

                            st.info(
                                "All copies are already available."
                            )

        else:

            st.warning(
                "No books found."
            )

    else:

        st.warning(
            "Book data is not available."
        )


    # ========================================================
    # SEAT AVAILABILITY
    # ========================================================

    st.divider()

    st.header(
        "🪑 Library Seat Availability"
    )


    if zones_data:

        for zone_id, zone in zones_data.items():

            name = zone.get(
                "name",
                zone_id
            )

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

            available = (
                total - occupied
            )


            st.subheader(name)


            col1, col2, col3 = st.columns(3)


            with col1:

                st.metric(
                    "Total Seats",
                    total
                )


            with col2:

                st.metric(
                    "Occupied",
                    occupied
                )


            with col3:

                st.metric(
                    "Available",
                    available
                )


            if total > 0:

                st.progress(
                    min(
                        occupied / total,
                        1.0
                    )
                )


            col1, col2 = st.columns(2)


            # ------------------------------------------------
            # OCCUPY SEAT
            # ------------------------------------------------

            with col1:

                if st.button(
                    "➕ Occupy Seat",
                    key="occupy_" + str(zone_id),
                    use_container_width=True
                ):

                    if occupied < total:

                        ref = db.reference(
                            "zones/"
                            + str(zone_id)
                            + "/occupied"
                        )

                        ref.set(
                            occupied + 1
                        )

                        st.success(
                            "✅ Seat occupied!"
                        )

                    else:

                        st.warning(
                            "❌ No seats available."
                        )


            # ------------------------------------------------
            # RELEASE SEAT
            # ------------------------------------------------

            with col2:

                if st.button(
                    "➖ Release Seat",
                    key="release_" + str(zone_id),
                    use_container_width=True
                ):

                    if occupied > 0:

                        ref = db.reference(
                            "zones/"
                            + str(zone_id)
                            + "/occupied"
                        )

                        ref.set(
                            occupied - 1
                        )

                        st.success(
                            "✅ Seat released!"
                        )

                    else:

                        st.warning(
                            "❌ No occupied seats."
                        )

    else:

        st.warning(
            "Seat data is not available."
        )


# Run live dashboard
live_library_dashboard()


# ============================================================
# AI LIBRARY ASSISTANT
# ============================================================

st.divider()

st.header(
    "🤖 AI Library Assistant"
)

st.write(
    "Ask about books, seats, library timings, "
    "borrowing rules, study zones and more."
)


# ============================================================
# AI SESSION STATE
# ============================================================

if "chat_history" not in st.session_state:

    st.session_state.chat_history = []


# ============================================================
# CHAT INPUT
# ============================================================

question = st.text_input(
    "Ask me anything about the library",
    placeholder="Example: How many books are available?",
    key="ai_question"
)


# ============================================================
# ASK BUTTON
# ============================================================

if st.button(
    "🤖 Ask Assistant",
    type="primary"
):

    clean_question = question.strip()


    if not clean_question:

        st.warning(
            "Please enter a question."
        )

    else:

        # Get latest Firebase data ONLY when
        # the user actually asks a question.

        current_books = get_books()
        current_zones = get_zones()


        with st.spinner(
            "🤖 Thinking..."
        ):

            try:

                answer = ask_library(
                    clean_question,
                    current_books,
                    current_zones
                )


                # Save conversation

                st.session_state.chat_history.append(
                    {
                        "question":
                        clean_question,

                        "answer":
                        answer
                    }
                )


            except Exception as e:

                st.error(
                    "❌ AI Assistant error"
                )

                st.code(
                    str(e)
                )


# ============================================================
# CHAT HISTORY
# ============================================================

if st.session_state.chat_history:

    st.subheader(
        "💬 Conversation"
    )


    for chat in reversed(
        st.session_state.chat_history
    ):

        st.markdown(
            "**You:** "
            + chat["question"]
        )

        st.success(
            chat["answer"]
        )

        st.divider()