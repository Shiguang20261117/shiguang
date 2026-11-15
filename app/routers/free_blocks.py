"""空闲时间块查询接口。"""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..engine.scheduler import find_free_blocks
from ..models import User

router = APIRouter(prefix="/api/free-blocks", tags=["空闲时间"])


class FreeBlockRead(BaseModel):
    date: dt.date
    start_time: str
    end_time: str
    duration_minutes: int


@router.get("", response_model=list[FreeBlockRead])
def list_free_blocks(
    start_date: dt.date = Query(description="一周的起始日期（含），返回其后 7 天"),
    min_minutes: str | None = Query(default=None, description="最小空闲时长（分钟），非法时使用 60"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[dict[str, object]]:
    return find_free_blocks(
        current_user.id, start_date, min_minutes=min_minutes, db=db
    )
