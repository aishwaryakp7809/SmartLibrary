import os
import json
from pathlib import Path

import pandas as pd
import firebase_admin
from firebase_admin import credentials, db
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

database_url = os.getenv("FIREBASE_DATABASE_URL")

if not database_url:
    raise ValueError(
        "FIREBASE_DATABASE_URL is missing from environment variables."
    )

# ---------------------------------------------------------
# Firebase credentials
# ---------------------------------------------------------

firebase_credentials_json = os.getenv("FIREBASE_CREDENTIALS_JSON")

if firebase_credentials_json:
    # Render / cloud deployment
    try:
        credential_data = json.loads(firebase_credentials_json)
        cred = credentials.Certificate(credential_data)
    except Exception as error:
        raise ValueError(
            f"Invalid FIREBASE_CREDENTIALS_JSON: {error}"
        )

else:
    # Local development
    credential_file = os.getenv(
        "FIREBASE_CREDENTIALS",
        "firebase-service-account.json"
    )

    credential_path = BASE_DIR / credential_file

    if not credential_path.exists():
        raise FileNotFoundError(
            f"Firebase credential file not found:\n{credential_path}"
        )

    cred = credentials.Certificate(str(credential_path))


# ---------------------------------------------------------
# Initialize Firebase
# ---------------------------------------------------------

try:
    firebase_admin.get_app()
except ValueError:
    firebase_admin.initialize_app(
        cred,
        {
            "databaseURL": database_url
        }
    )


# ---------------------------------------------------------
# Seat / Zone functions
# ---------------------------------------------------------

def get_zones():
    return db.reference("zones").get()


def set_zones(zones):
    db.reference("zones").set(zones)


def initialize_zones():
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


# ---------------------------------------------------------
# Book functions
# ---------------------------------------------------------

def get_books():
    return db.reference("books").get()


def set_books(books):
    db.reference("books").set(books)


def initialize_books():
    ref = db.reference("books")

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

        # CSV uses "id" as the book ID
        book_id = str(row["id"]).strip()

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


# ---------------------------------------------------------
# Initialize existing data
# ---------------------------------------------------------

initialize_zones()
initialize_books()