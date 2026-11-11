# creates a user or changes the password of an existing one
#
# usage (inside backend, with the virtual environment active):
#     python create_admin.py email@example.com
#
# the password is asked in the terminal and is not shown on screen
import getpass
import sys

import models
from database import SessionLocal
from db_setup import initialize_database
from security import MIN_PASSWORD_LENGTH, hash_password


def main() -> int:
    if len(sys.argv) != 2 or "@" not in sys.argv[1]:
        print("Usage: python create_admin.py email@example.com")
        return 1
    email = sys.argv[1].strip().lower()

    password = getpass.getpass("Password: ")
    if len(password) < MIN_PASSWORD_LENGTH:
        print(f"The password must have at least {MIN_PASSWORD_LENGTH} characters.")
        return 1
    if getpass.getpass("Repeat the password: ") != password:
        print("The passwords do not match.")
        return 1

    # prepares the database without starting the API, so it does not need SECRET_KEY
    initialize_database()
    db = SessionLocal()
    try:
        user = db.query(models.User).filter(models.User.email == email).first()
        if user:
            user.password_hash = hash_password(password)
            print(f"Password for {email} updated.")
        else:
            db.add(models.User(email=email, password_hash=hash_password(password)))
            print(f"User {email} created.")
        db.commit()
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
