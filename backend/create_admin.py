# creates a user or changes the password of an existing one; the user becomes an admin of the first
# laboratory if they are not a member of it yet (a user without a laboratory cannot do anything)
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
from laboratories import default_laboratory
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
            user = models.User(email=email, password_hash=hash_password(password))
            db.add(user)
            print(f"User {email} created.")
        db.flush()
        laboratory = default_laboratory(db)
        if not db.query(models.Membership).filter_by(user_id=user.id, laboratory_id=laboratory.id).first():
            db.add(models.Membership(user_id=user.id, laboratory_id=laboratory.id, role="admin"))
            print(f"{email} is now an admin of the laboratory '{laboratory.slug}'.")
        db.commit()
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
