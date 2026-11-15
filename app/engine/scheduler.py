"""空闲时间计算引擎：占用矩阵与连续空闲块。"""
from __future__ import annotations

import datetime as dt
import math

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import Routine, Schedule

# 一天按半小时切分为 48 个格子：00:00-00:30 ... 23:30-24:00
SLOTS_PER_DAY = 48
SLOT_MINUTES = 30
DAYS_PER_WEEK = 7

# 这些状态的日程不占用时间；其余状态（pending / done / active 等）都视为占用
INACTIVE_STATUSES = {"cancelled", "canceled", "deleted"}

_TIME_FORMATS = ("%H:%M:%S.%f", "%H:%M:%S", "%H:%M")


def _parse_time(value: object) -> dt.time | None:
    """把数据库 / 字符串中的时间解析为 dt.time，解析失败返回 None。"""
    if isinstance(value, dt.datetime):
        return value.time()
    if isinstance(value, dt.time):
        return value
    if isinstance(value, str):
        text = value.strip()
        for fmt in _TIME_FORMATS:
            try:
                return dt.datetime.strptime(text, fmt).time()
            except ValueError:
                continue
    return None


def _slot_range(start: dt.time, end: dt.time) -> tuple[int, int]:
    """返回 [start_slot, end_slot) 的格子区间。

    - 非整点半点的时间向外取整，保证被日程覆盖的格子都被标记占用；
    - 结束时间不晚于开始时间视为跨天，只占用到当天 24:00。
    """
    start_total = start.hour * 60 + start.minute + (1 if start.second else 0)
    end_total = end.hour * 60 + end.minute + (1 if end.second else 0)

    start_slot = start_total // SLOT_MINUTES
    end_slot = math.ceil(end_total / SLOT_MINUTES)

    if end_slot <= start_slot:  # 跨天 -> 只算到 24:00
        end_slot = SLOTS_PER_DAY

    start_slot = max(0, min(start_slot, SLOTS_PER_DAY))
    end_slot = max(start_slot, min(end_slot, SLOTS_PER_DAY))
    return start_slot, end_slot


def _mark(occupied: list[bool], start: object, end: object) -> None:
    """把一个时间段写入某天的占用格子；时间解析失败时按空闲处理（跳过）。"""
    start_time = _parse_time(start)
    end_time = _parse_time(end)
    if start_time is None or end_time is None:
        return
    start_slot, end_slot = _slot_range(start_time, end_time)
    for i in range(start_slot, end_slot):
        occupied[i] = True


def build_occupancy(
    user_id: int,
    week_start_date: dt.date,
    db: Session | None = None,
) -> list[list[bool]]:
    """构建 7 天 × 48 格占用矩阵。

    合并以下来源：
    - 该周内 status 非 cancelled 的 schedules；
    - is_active 的 routines，按 weekday（0=周一 ... 6=周日）展开到该周每一天。

    返回 ``occupancy[day][slot]``，day=0 对应 week_start_date 当天，True 表示占用。
    """
    owns_session = db is None
    if db is None:
        db = SessionLocal()
    try:
        week_start = week_start_date
        week_end = week_start + dt.timedelta(days=DAYS_PER_WEEK - 1)
        occupancy = [[False] * SLOTS_PER_DAY for _ in range(DAYS_PER_WEEK)]

        schedules = db.scalars(
            select(Schedule).where(
                Schedule.user_id == user_id,
                Schedule.date >= week_start,
                Schedule.date <= week_end,
            )
        ).all()
        for schedule in schedules:
            status = (schedule.status or "").lower()
            if status in INACTIVE_STATUSES:
                continue
            day_index = (schedule.date - week_start).days
            if 0 <= day_index < DAYS_PER_WEEK:
                _mark(occupancy[day_index], schedule.start_time, schedule.end_time)

        routines = db.scalars(
            select(Routine).where(
                Routine.user_id == user_id,
                Routine.is_active.is_(True),
            )
        ).all()
        for routine in routines:
            for day_index in range(DAYS_PER_WEEK):
                if (week_start + dt.timedelta(days=day_index)).weekday() == routine.weekday:
                    _mark(occupancy[day_index], routine.start_time, routine.end_time)

        return occupancy
    finally:
        if owns_session:
            db.close()


def _normalize_min_minutes(min_minutes: object) -> int:
    """非法（非数字 / 非正数）时回退到默认 60 分钟。"""
    try:
        value = int(min_minutes)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return 60
    return value if value > 0 else 60


def _format_slot(slot: int) -> str:
    minutes = slot * SLOT_MINUTES
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def find_free_blocks(
    user_id: int,
    week_start_date: dt.date,
    min_minutes: int | str | None = 60,
    db: Session | None = None,
) -> list[dict[str, object]]:
    """找出该周所有连续空闲时长 >= min_minutes 的时间块。

    返回 ``[{date, start_time, end_time, duration_minutes}]``，按日期、开始时间升序。
    """
    threshold = _normalize_min_minutes(min_minutes)
    occupancy = build_occupancy(user_id, week_start_date, db=db)

    blocks: list[dict[str, object]] = []
    for day_index in range(DAYS_PER_WEEK):
        date = week_start_date + dt.timedelta(days=day_index)
        run_start: int | None = None
        # 末尾补一个占用哨兵，统一处理收尾逻辑
        for slot, occupied in enumerate([*occupancy[day_index], True]):
            if not occupied:
                if run_start is None:
                    run_start = slot
                continue
            if run_start is None:
                continue
            duration = (slot - run_start) * SLOT_MINUTES
            if duration >= threshold:
                blocks.append(
                    {
                        "date": date,
                        "start_time": _format_slot(run_start),
                        "end_time": _format_slot(slot),
                        "duration_minutes": duration,
                    }
                )
            run_start = None

    return blocks
