import os
from pathlib import Path

import pandas as pd
import firebase_admin
from firebase_admin import credentials, db
from dotenv import load_dotenv


# -----------------------------------
# LOAD ENVIRONMENT VARIABLES
# -----------------------------------

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

credential_file = os.getenv(
    "FIREBASE_CREDENTIALS",
    "firebase-service-account.json"
)

database_url = os.getenv("FIREBASE_DATABASE_URL")

credential_path = BASE_DIR / credential_file


# -----------------------------------
# FIREBASE INITIALIZATION
# -----------------------------------

try:
    firebase_admin.get_app()

except ValueError:

    if not database_url:
        raise ValueError(
            "FIREBASE_DATABASE_URL is missing from .env"
        )

    if not credential_path.exists():
        raise FileNotFoundError(
            f"Firebase credential file not found:\n{credential_path}"
        )

    cred = credentials.Certificate(
        str(credential_path)
    )

    firebase_admin.initialize_app(
        cred,
        {
            "databaseURL": database_url
        }
    )


# -----------------------------------
# SEAT FUNCTIONS
# -----------------------------------

def get_zones():
    """Get all library seat zones from Firebase."""
    return db.reference("zones").get()


def set_zones(zones):
    """Save seat zones to Firebase."""
    db.reference("zones").set(zones)


def initialize_zones():
    """Create initial seat data only if it doesn't exist."""

    ref = db.reference("zones")

    if ref.get() is not None:
        return

    zones = {
        "silent": {
            "name": "🤫 Silent Study Zone",
            "total": 30,
            "occupied": 0
        },
        "general": {
            "name": "📚 General Study Zone",
            "total": 40,
            "occupied": 0
        },
        "discussion": {
            "name": "💬 Discussion Zone",
            "total": 20,
            "occupied": 0
        }
    }

    ref.set(zones)

    print("✅ Seat data created in Firebase")


# -----------------------------------
# BOOK FUNCTIONS
# -----------------------------------

def get_books():
    """Get all books from Firebase."""
    return db.reference("books").get()


def set_books(books):
    """Save books to Firebase."""
    db.reference("books").set(books)


def initialize_books():
    """
    Import books from books.csv into Firebase
    only if books do not already exist.
    """

    ref = db.reference("books")

    # Don't overwrite existing Firebase books
    if ref.get() is not None:
        return

    csv_path = BASE_DIR / "books.csv"

    if not csv_path.exists():
        raise FileNotFoundError(
            f"books.csv not found:\n{csv_path}"
        )

    books_df = pd.read_csv(csv_path)

    books = {}

    for _, row in books_df.iterrows():

        book_id = str(row["book_id"]).strip()

        books[book_id] = {
            "title": str(row["title"]).strip(),
            "author": str(row["author"]).strip(),
            "subject": str(row["subject"]).strip(),
            "available_copies": int(row["available_copies"]),
            "total_copies": int(row["total_copies"]),
            "rack": str(row["rack"]).strip()
        }

    ref.set(books)

    print("✅ Book data created in Firebase")


# -----------------------------------
# INITIALIZE DATABASE
# -----------------------------------

initialize_zones()
initialize_books()