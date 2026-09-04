from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional

import firebase_admin
from firebase_admin import auth, db

from firebase_db import get_books, set_books, get_zones
from rag.chatbot import ask_library


# ============================================================
# FASTAPI APP
# ============================================================

app = FastAPI(
    title="Smart Library Assistant API",
    version="1.0"
)


# ============================================================
# CORS
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# DATA MODELS
# ============================================================

class BookData(BaseModel):
    title: str
    author: str
    subject: str
    available_copies: int = Field(ge=0)
    total_copies: int = Field(ge=0)
    rack: str


class SeatUpdate(BaseModel):
    occupied: int = Field(ge=0)


class AIQuestion(BaseModel):
    question: str
    conversation_history: Optional[list] = None


# ============================================================
# AUTHENTICATION
# ============================================================

def get_bearer_token(
    authorization: Optional[str]
):
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Authorization token required"
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization format"
        )

    token = authorization[len("Bearer "):].strip()

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Authentication token is empty"
        )

    return token


def verify_user(
    authorization: Optional[str] = Header(None)
):
    token = get_bearer_token(authorization)

    try:
        decoded_token = auth.verify_id_token(token)
        return decoded_token

    except Exception as error:
        print("USER AUTH ERROR:", error)

        raise HTTPException(
            status_code=401,
            detail="Invalid or expired authentication token"
        )


def verify_admin(
    authorization: Optional[str] = Header(None)
):
    user = verify_user(authorization)

    if user.get("admin", False) is not True:
        raise HTTPException(
            status_code=403,
            detail="Administrator access required"
        )

    return user


# ============================================================
# HOME
# ============================================================

@app.get("/")
def home():
    return {
        "message": "Smart Library Assistant API is running",
        "status": "online"
    }


# ============================================================
# BOOKS
# ============================================================

@app.get("/books")
def get_all_books():
    books = get_books()

    if books is None:
        return {}

    return books


# ============================================================
# ADD BOOK - ADMIN ONLY
# ============================================================

@app.post("/books/{book_id}")
def add_book(
    book_id: str,
    book: BookData,
    authorization: Optional[str] = Header(None)
):
    verify_admin(authorization)

    books = get_books() or {}

    if book_id in books:
        raise HTTPException(
            status_code=409,
            detail="Book already exists"
        )

    if book.total_copies < 1:
        raise HTTPException(
            status_code=400,
            detail="Total copies must be at least 1"
        )

    if book.available_copies > book.total_copies:
        raise HTTPException(
            status_code=400,
            detail="Available copies cannot exceed total copies"
        )

    books[book_id] = book.model_dump()

    set_books(books)

    return {
        "message": "Book added successfully",
        "book_id": book_id
    }


# ============================================================
# UPDATE BOOK - ADMIN ONLY
# ============================================================

@app.put("/books/{book_id}")
def update_book(
    book_id: str,
    book: BookData,
    authorization: Optional[str] = Header(None)
):
    verify_admin(authorization)

    books = get_books() or {}

    if book_id not in books:
        raise HTTPException(
            status_code=404,
            detail="Book not found"
        )

    if book.total_copies < 1:
        raise HTTPException(
            status_code=400,
            detail="Total copies must be at least 1"
        )

    if book.available_copies > book.total_copies:
        raise HTTPException(
            status_code=400,
            detail="Available copies cannot exceed total copies"
        )

    books[book_id] = book.model_dump()

    set_books(books)

    return {
        "message": "Book updated successfully",
        "book_id": book_id
    }


# ============================================================
# DELETE BOOK - ADMIN ONLY
# ============================================================

@app.delete("/books/{book_id}")
def delete_book(
    book_id: str,
    authorization: Optional[str] = Header(None)
):
    verify_admin(authorization)

    books = get_books() or {}

    if book_id not in books:
        raise HTTPException(
            status_code=404,
            detail="Book not found"
        )

    del books[book_id]

    set_books(books)

    return {
        "message": "Book deleted successfully",
        "book_id": book_id
    }


# ============================================================
# SEATS
# ============================================================

@app.get("/seats")
def get_all_seats():
    zones = get_zones()

    if zones is None:
        return {}

    return zones


# ============================================================
# ADMIN SEAT UPDATE
# ============================================================

@app.put("/seats/{zone_id}")
def update_seat(
    zone_id: str,
    seat: SeatUpdate,
    authorization: Optional[str] = Header(None)
):
    verify_admin(authorization)

    zones = get_zones() or {}

    if zone_id not in zones:
        raise HTTPException(
            status_code=404,
            detail="Zone not found"
        )

    total = int(zones[zone_id]["total"])

    if seat.occupied > total:
        raise HTTPException(
            status_code=400,
            detail="Occupied seats cannot exceed total seats"
        )

    zones[zone_id]["occupied"] = seat.occupied

    db.reference("zones").set(zones)

    return {
        "message": "Seat occupancy updated",
        "zone": zone_id,
        "occupied": seat.occupied,
        "available": total - seat.occupied
    }


# ============================================================
# STUDENT QR ENTRY
# ============================================================

@app.post("/student/entry")
def student_entry(
    zone_id: str,
    qr_student_id: str,
    authorization: Optional[str] = Header(None)
):
    user = verify_user(authorization)

    uid = user["uid"]

    # --------------------------------------------------------
    # VERIFY QR BELONGS TO LOGGED-IN STUDENT
    # --------------------------------------------------------

    expected_qr = "SMARTLIBRARY-STUDENT-" + uid

    if qr_student_id != expected_qr:
        raise HTTPException(
            status_code=403,
            detail="Invalid student QR code"
        )

    # --------------------------------------------------------
    # GET ZONES
    # --------------------------------------------------------

    zones = get_zones() or {}

    if zone_id not in zones:
        raise HTTPException(
            status_code=404,
            detail="Zone not found"
        )

    # --------------------------------------------------------
    # GET STUDENT RECORD
    # --------------------------------------------------------

    student_ref = db.reference(
        f"students/{uid}"
    )

    student = student_ref.get()

    # --------------------------------------------------------
    # PREVENT DUPLICATE ENTRY
    # --------------------------------------------------------

    if student and student.get("inside") is True:
        raise HTTPException(
            status_code=400,
            detail="Student is already inside the library"
        )

    # --------------------------------------------------------
    # CHECK CAPACITY
    # --------------------------------------------------------

    total = int(
        zones[zone_id]["total"]
    )

    occupied = int(
        zones[zone_id].get(
            "occupied",
            0
        )
    )

    if occupied >= total:
        raise HTTPException(
            status_code=400,
            detail="This zone is currently full"
        )

    # --------------------------------------------------------
    # INCREMENT OCCUPANCY
    # --------------------------------------------------------

    new_occupied = occupied + 1

    zones[zone_id]["occupied"] = new_occupied

    db.reference("zones").set(zones)

    # --------------------------------------------------------
    # SAVE STUDENT ENTRY
    # --------------------------------------------------------

    student_ref.set({
        "inside": True,
        "zone": zone_id,
        "email": user.get("email", "")
    })

    return {
        "message": "Student entry recorded successfully",
        "student": user.get("email", ""),
        "zone": zone_id,
        "occupied": new_occupied,
        "available": total - new_occupied
    }


# ============================================================
# STUDENT QR EXIT
# ============================================================

@app.post("/student/exit")
def student_exit(
    qr_student_id: str,
    authorization: Optional[str] = Header(None)
):
    user = verify_user(authorization)

    uid = user["uid"]

    # --------------------------------------------------------
    # VERIFY QR
    # --------------------------------------------------------

    expected_qr = "SMARTLIBRARY-STUDENT-" + uid

    if qr_student_id != expected_qr:
        raise HTTPException(
            status_code=403,
            detail="Invalid student QR code"
        )

    # --------------------------------------------------------
    # GET STUDENT RECORD
    # --------------------------------------------------------

    student_ref = db.reference(
        f"students/{uid}"
    )

    student = student_ref.get()

    if not student:
        raise HTTPException(
            status_code=400,
            detail="Student entry record not found"
        )

    # --------------------------------------------------------
    # PREVENT DUPLICATE EXIT
    # --------------------------------------------------------

    if student.get("inside") is not True:
        raise HTTPException(
            status_code=400,
            detail="Student is not currently inside the library"
        )

    zone_id = student.get("zone")

    # --------------------------------------------------------
    # GET ZONES
    # --------------------------------------------------------

    zones = get_zones() or {}

    if zone_id not in zones:
        raise HTTPException(
            status_code=400,
            detail="Student zone information is invalid"
        )

    # --------------------------------------------------------
    # DECREASE OCCUPANCY
    # --------------------------------------------------------

    occupied = int(
        zones[zone_id].get(
            "occupied",
            0
        )
    )

    if occupied <= 0:
        raise HTTPException(
            status_code=400,
            detail="Zone occupancy is already zero"
        )

    new_occupied = occupied - 1

    zones[zone_id]["occupied"] = new_occupied

    db.reference("zones").set(zones)

    # --------------------------------------------------------
    # UPDATE STUDENT STATUS
    # --------------------------------------------------------

    student_ref.update({
        "inside": False,
        "zone": None
    })

    total = int(
        zones[zone_id]["total"]
    )

    return {
        "message": "Student exit recorded successfully",
        "student": user.get("email", ""),
        "zone": zone_id,
        "occupied": new_occupied,
        "available": total - new_occupied
    }


# ============================================================
# AI ASSISTANT
# ============================================================

@app.post("/ask-ai")
def ask_ai(
    data: AIQuestion
):
    try:

        books_data = get_books() or {}

        zones_data = get_zones() or {}

        history = (
            data.conversation_history or []
        )

        answer = ask_library(
            data.question,
            books_data,
            zones_data,
            history
        )

        return {
            "answer": answer
        }

    except Exception as error:

        print(
            "AI ERROR:",
            error
        )

        raise HTTPException(
            status_code=500,
            detail="AI assistant error"
        )


# ============================================================
# RUN SERVER
# ============================================================

if __name__ == "__main__":

    import uvicorn

    uvicorn.run(
        "backend:app",
        host="127.0.0.1",
        port=8000,
        reload=True
    )