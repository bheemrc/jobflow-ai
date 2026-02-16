"""Extract authenticated user ID from X-User-Id header.

Also provides a contextvars-based current_user_id for use in LangChain tools
that can't receive user_id as a parameter.
"""

from contextvars import ContextVar

from fastapi import HTTPException, Request

# Set before graph execution, read by tools during execution
current_user_id: ContextVar[str] = ContextVar("current_user_id", default="")


def get_user_id(request: Request) -> str:
    """FastAPI dependency: extract X-User-Id header or raise 401."""
    user_id = request.headers.get("X-User-Id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Missing X-User-Id header")
    return user_id
