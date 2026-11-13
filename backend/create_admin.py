# creates a user or changes the password of an existing one. A new user becomes an admin of the first
# laboratory (a user without a laboratory cannot do anything). An existing user keeps the laboratories and
# roles they have: changing a forgotten password must not promote anyone
#
# usage (inside backend, with the virtual environment active):
#     python create_admin.py email@example.com
#     python create_admin.py email@example.com --superadmin
#
# --superadmin also makes the user a platform administrator, who can create laboratories (POST /labs).
# It never takes the flag away from someone who already has it
#
# the e-mail of the user is marked as confirmed (the person is at the server, so there is nothing to prove)
#
# the password is asked in the terminal and is not shown on screen
import getpass
import sys
from datetime import datetime, timezone

import models
from database import SessionLocal
from db_setup import initialize_database
from laboratories import default_laboratory
from security import MIN_PASSWORD_LENGTH, hash_password


def main() -> int:
    arguments = [a for a in sys.argv[1:] if a != "--superadmin"]
    make_superadmin = "--superadmin" in sys.argv[1:]
    if len(arguments) != 1 or "@" not in arguments[0]:
        print("Usage: python create_admin.py email@example.com [--superadmin]")
        return 1
    email = arguments[0].strip().lower()

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
        created = user is None
        if user:
            user.password_hash = hash_password(password)
            print(f"Password for {email} updated.")
        else:
            user = models.User(email=email, password_hash=hash_password(password))
            db.add(user)
            print(f"User {email} created.")
        # whoever can run this script on the server needs no e-mail to prove who they are; the original
        # date is kept when the address was already confirmed
        if user.email_verified_at is None:
            user.email_verified_at = datetime.now(timezone.utc).replace(tzinfo=None)
            print(f"The e-mail of {email} is marked as confirmed.")
        if make_superadmin and not user.is_superadmin:
            user.is_superadmin = True
            print(f"{email} is now a platform administrator.")
        db.flush()
        if created:
            laboratory = default_laboratory(db)
            db.add(models.Membership(user_id=user.id, laboratory_id=laboratory.id, role="admin"))
            print(f"{email} is now an admin of the laboratory '{laboratory.slug}'.")
        # the links already sent to set a password must not work after it was set here
        db.query(models.EmailConfirmation).filter(models.EmailConfirmation.user_id == user.id).delete()
        db.commit()
    finally:
        db.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
