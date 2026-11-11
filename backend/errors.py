from typing import Optional

from fastapi import HTTPException


# errors are sent as {"detail": {"code": ..., "params": {...}}}; the site turns the code into a message
# in its own language. Exported file contents stay in Portuguese: they are shown to the site's users
def api_error(status_code: int, code: str, headers: Optional[dict] = None, **params) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "params": params}, headers=headers)
