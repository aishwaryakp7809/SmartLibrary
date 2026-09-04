import firebase_admin
from firebase_admin import credentials
from firebase_admin import auth
from dotenv import load_dotenv

import os
from pathlib import Path


load_dotenv()

BASE_DIR = Path(__file__).resolve().parent

credential_file = os.getenv(
    "FIREBASE_CREDENTIALS",
    "firebase-service-account.json"
)

credential_path = BASE_DIR / credential_file


if not firebase_admin._apps:

    cred = credentials.Certificate(
        str(credential_path)
    )

    firebase_admin.initialize_app(
        cred
    )


admin_email = input(
    "Enter the ADMIN email you created in Firebase: "
).strip()


try:

    user = auth.get_user_by_email(
        admin_email
    )


    auth.set_custom_user_claims(
        user.uid,
        {
            "admin": True
        }
    )


    print()
    print("✅ Administrator role assigned!")
    print()
    print("Email:", admin_email)
    print("Role: Administrator")


except Exception as e:

    print()
    print("❌ Error:")
    print(e)