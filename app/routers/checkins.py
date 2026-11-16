"""打卡 checkins：打卡记录与统计。"""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Checkin, Routine, Schedule, User
from ..schemas import CheckinCreate, CheckinRead, CheckinStats

router = APIRouter(prefix="/api/checkins", tags=["打卡"])

ONE_DAY = dt.timedelta(days=1)


def _ensure_target_owned(
    target_type: str, target_id: int, user: User, db: Session
) -> None:
    if target_type == "schedule":
        target = db.get(Schedule, target_id)
        label = "日程"
    else:
        target = db.get(Routine, target_id)
        label = "固定日常"
    if target is None or target.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=f"{label}不存在")


@router.get("", response_model=list[CheckinRead])
def list_checkins(
    start_date: dt.date | None = Query(default=None, description="起始日期（含）"),
    end_date: dt.date | None = Query(default=None, description="结束日期（含）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Checkin]:
    stmt = select(Checkin).where(Checkin.user_id == current_user.id)
    if start_date is not None:
        stmt = stmt.where(Checkin.date >= start_date)
    if end_date is not None:
        stmt = stmt.where(Checkin.date <= end_date)
    stmt = stmt.order_by(Checkin.date, Checkin.id)
    return list(db.scalars(stmt).all())


@router.post("", response_model=CheckinRead, status_code=status.HTTP_201_CREATED)
def create_checkin(
    payload: CheckinCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Checkin:
    _ensure_target_owned(payload.target_type, payload.target_id, current_user, db)

    today = dt.date.today()
    exists = db.scalar(
        select(Checkin.id).where(
            Checkin.user_id == current_user.id,
            Checkin.target_type == payload.target_type,
            Checkin.target_id == payload.target_id,
            Checkin.date == today,
        )
    )
    if exists is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="今天已经打过卡了")

    checkin = Checkin(
        user_id=current_user.id,
        target_type=payload.target_type,
        target_id=payload.target_id,
        date=today,
    )
    db.add(checkin)
    try:
        db.commit()
    except IntegrityError:
        # 并发重复提交时由唯一索引兜底
        db.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="今天已经打过卡了"
        ) from None
    db.refresh(checkin)
    return checkin


def _streak_days(checkin_dates: set[dt.date], today: dt.date) -> int:
    """连续打卡天数：截止到今天；今天还没打卡时从昨天开始算。"""
    cursor = today if today in checkin_dates else today - ONE_DAY
    days = 0
    while cursor in checkin_dates:
        days += 1
        cursor -= ONE_DAY
    return days


@router.get("/stats", response_model=CheckinStats)
def checkin_stats(
    days: int = Query(default=7, ge=1, le=90),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CheckinStats:
    today = dt.date.today()
    start = today - dt.timedelta(days=days - 1)
    now = dt.datetime.now()

    checkins = list(
        db.scalars(
            select(Checkin).where(
                Checkin.user_id == current_user.id,
                Checkin.date >= start,
                Checkin.date <= today,
            )
        ).all()
    )
    checkin_dates = {item.date for item in checkins}
    checked_schedule_ids = {
        item.target_id for item in checkins if item.target_type == "schedule"
    }

    # 近 N 天已到结束时间、应完成的日程
    schedules = list(
        db.scalars(
            select(Schedule).where(
                Schedule.user_id == current_user.id,
                Schedule.date >= start,
                Schedule.date <= today,
            )
        ).all()
    )
    due_ids = [
        schedule.id
        for schedule in schedules
        if dt.datetime.combine(schedule.date, schedule.end_time) <= now
    ]
    completed = sum(1 for schedule_id in due_ids if schedule_id in checked_schedule_ids)
    # 没有应完成日程时视为 100%，避免空数据被判定为「低落」
    completion_rate = (
        round(completed / len(due_ids) * 100, 1) if due_ids else 100.0
    )

    if completion_rate >= 80:
        mascot = "happy"
    elif completion_rate >= 40:
        mascot = "normal"
    else:
        mascot = "sad"

    return CheckinStats(
        days=days,
        total=len(checkins),
        streak_days=_streak_days(checkin_dates, today),
        completion_rate=completion_rate,
        mascot=mascot,
    )
