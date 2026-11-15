"""单条日程 schedules 的增删改查。"""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Schedule, ScheduleSeries, User
from ..schemas import (
    ScheduleCreate,
    ScheduleRead,
    ScheduleUpdate,
    apply_updates,
)

router = APIRouter(prefix="/api/schedules", tags=["日程"])


def _get_owned_schedule(schedule_id: int, user: User, db: Session) -> Schedule:
    schedule = db.get(Schedule, schedule_id)
    if schedule is None or schedule.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="日程不存在")
    return schedule


def _ensure_series_owned(series_id: int | None, user: User, db: Session) -> None:
    if series_id is None:
        return
    series = db.get(ScheduleSeries, series_id)
    if series is None or series.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="周期系列不存在")


@router.get("", response_model=list[ScheduleRead])
def list_schedules(
    start_date: dt.date | None = Query(default=None, description="起始日期（含）"),
    end_date: dt.date | None = Query(default=None, description="结束日期（含）"),
    series_id: int | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Schedule]:
    stmt = select(Schedule).where(Schedule.user_id == current_user.id)
    if start_date is not None:
        stmt = stmt.where(Schedule.date >= start_date)
    if end_date is not None:
        stmt = stmt.where(Schedule.date <= end_date)
    if series_id is not None:
        stmt = stmt.where(Schedule.series_id == series_id)
    if status_filter is not None:
        stmt = stmt.where(Schedule.status == status_filter)
    stmt = stmt.order_by(Schedule.date, Schedule.start_time)
    return list(db.scalars(stmt).all())


@router.post("", response_model=ScheduleRead, status_code=status.HTTP_201_CREATED)
def create_schedule(
    payload: ScheduleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Schedule:
    _ensure_series_owned(payload.series_id, current_user, db)
    schedule = Schedule(user_id=current_user.id, **payload.model_dump())
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return schedule


@router.get("/{schedule_id}", response_model=ScheduleRead)
def get_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Schedule:
    return _get_owned_schedule(schedule_id, current_user, db)


@router.put("/{schedule_id}", response_model=ScheduleRead)
@router.patch("/{schedule_id}", response_model=ScheduleRead)
def update_schedule(
    schedule_id: int,
    payload: ScheduleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Schedule:
    schedule = _get_owned_schedule(schedule_id, current_user, db)
    data = payload.model_dump(exclude_unset=True)

    start = data.get("start_time", schedule.start_time)
    end = data.get("end_time", schedule.end_time)
    if start >= end:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail="结束时间必须晚于开始时间"
        )

    if "series_id" in data:
        _ensure_series_owned(data["series_id"], current_user, db)

    apply_updates(schedule, data)
    db.commit()
    db.refresh(schedule)
    return schedule


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    schedule = _get_owned_schedule(schedule_id, current_user, db)
    db.delete(schedule)
    db.commit()
