from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.identity import CurrentUser, get_current_user
from app.core.permissions import require
from app.db.session import get_db

__all__ = ["Session", "CurrentUser", "get_db", "get_current_user", "staff_user", "Depends"]


def staff_user(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
    require(user, "workpaper.view")
    return user
