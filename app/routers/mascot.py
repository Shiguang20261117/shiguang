"""Mascot 路由：保存 mascot 昵称。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import User
from ..schemas import MascotNameUpdate, UserRead

router = APIRouter(prefix="/api/mascot", tags=["Mascot"])


@router.put("/name", response_model=UserRead)
def update_mascot_name(
    payload: MascotNameUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> User:
    current_user.mascot_name = payload.name
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return current_user
