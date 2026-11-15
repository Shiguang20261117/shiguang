"""周期日程系列 schedule_series 的批量创建与查询。

接口约定：
- POST /api/series 接收 weekday（0=周一 ... 6=周日，与 Python date.weekday() 一致），
  在 [start_date, end_date] 闭区间内找出所有符合 weekday 的日期，批量生成 schedules，
  并统一关联到新建的 series_id。
- 同一时间段重复调用会各自生成一个系列，不做去重（需求未要求）。
"""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Schedule, ScheduleSeries, User
from ..schemas import SeriesCreate, SeriesCreateResult, SeriesRead, SeriesUpdate

router = APIRouter(prefix="/api/series", tags=["周期日程"])


@router.get("", response_model=list[SeriesRead])
def list_series(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[SeriesRead]:
    rows = db.execute(
        select(ScheduleSeries, func.count(Schedule.id))
        .outerjoin(Schedule, Schedule.series_id == ScheduleSeries.id)
        .where(ScheduleSeries.user_id == current_user.id)
        .group_by(ScheduleSeries.id)
        .order_by(ScheduleSeries.start_date.desc(), ScheduleSeries.id.desc())
    ).all()

    result: list[SeriesRead] = []
    for series, schedule_count in rows:
        item = SeriesRead.model_validate(series)
        item.schedule_count = schedule_count
        result.append(item)
    return result


@router.post("", response_model=SeriesCreateResult, status_code=status.HTTP_201_CREATED)
def create_series(
    payload: SeriesCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SeriesCreateResult:
    series = ScheduleSeries(user_id=current_user.id, **payload.model_dump())
    db.add(series)
    db.flush()  # 先拿到 series.id，供生成的 schedules 关联

    schedules: list[Schedule] = []
    current_date = payload.start_date
    one_day = dt.timedelta(days=1)
    while current_date <= payload.end_date:
        if current_date.weekday() == payload.weekday:
            schedules.append(
                Schedule(
                    user_id=current_user.id,
                    series_id=series.id,
                    title=payload.title,
                    date=current_date,
                    start_time=payload.start_time,
                    end_time=payload.end_time,
                    status="pending",
                )
            )
        current_date += one_day

    db.add_all(schedules)
    db.commit()
    db.refresh(series)

    series_read = SeriesRead.model_validate(series)
    series_read.schedule_count = len(schedules)
    return SeriesCreateResult(series=series_read, created_count=len(schedules))


@router.patch("/{series_id}", response_model=SeriesRead)
def update_series(
    series_id: int,
    payload: SeriesUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SeriesRead:
    series = db.get(ScheduleSeries, series_id)
    if series is None or series.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="周期系列不存在")

    data = payload.model_dump(exclude_unset=True)
    start = data.get("start_time", series.start_time)
    end = data.get("end_time", series.end_time)
    if start >= end:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail="结束时间必须晚于开始时间"
        )

    series_fields = {
        key: value for key, value in data.items() if key in {"title", "start_time", "end_time"}
    }
    for key, value in series_fields.items():
        setattr(series, key, value)

    # 地点、备注在 series 表没有对应字段，统一同步到该系列的所有日程
    schedule_fields = {
        key: value
        for key, value in data.items()
        if key in {"title", "start_time", "end_time", "location", "description"}
    }
    if schedule_fields:
        db.execute(
            update(Schedule)
            .where(Schedule.series_id == series.id, Schedule.user_id == current_user.id)
            .values(**schedule_fields)
        )

    db.commit()
    db.refresh(series)

    schedule_count = db.scalar(
        select(func.count(Schedule.id)).where(Schedule.series_id == series.id)
    )
    result = SeriesRead.model_validate(series)
    result.schedule_count = schedule_count or 0
    return result


@router.delete("/{series_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_series(
    series_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    series = db.get(ScheduleSeries, series_id)
    if series is None or series.user_id != current_user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="周期系列不存在")

    # 先删除该系列生成的所有日程，再删除系列本身
    db.execute(delete(Schedule).where(Schedule.series_id == series.id))
    db.delete(series)
    db.commit()
