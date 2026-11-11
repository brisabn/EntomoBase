import os
import secrets

# --- JWT security settings ---
ALGORITHM = "HS256"


# the key comes from the environment; without it the API only starts in development mode (ENTOMOBASE_ENV=dev),
# with a random key that changes on every start and invalidates previous logins
def load_secret_key() -> str:
    key = os.getenv("SECRET_KEY")
    if key:
        return key
    if os.getenv("ENTOMOBASE_ENV") == "dev":
        print("WARNING: SECRET_KEY is not set; using a temporary key (dev mode).")
        return secrets.token_urlsafe(32)
    raise RuntimeError(
        "SECRET_KEY is not set. Set the SECRET_KEY environment variable, "
        "or use ENTOMOBASE_ENV=dev only in development."
    )


SECRET_KEY = load_secret_key()
