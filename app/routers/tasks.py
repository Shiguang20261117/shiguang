"""任务排程：把「本周做 N 次，每次 M 分钟」的目标分配到空闲时间块。"""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..deps import get_current_user
from ..engine.scheduler import find_free_blocks
from ..models import Schedule, Task, TaskSlot, User
from ..schemas import TaskCreate, TaskRead, TaskScheduleResult

router = APIRouter(prefix="/api/tasks", tags=["任务"])

# 22:00 之后不再安排任务；跨越 22:00 的空闲块会被裁剪
LATEST_END = 22 * 60
# 周视图从 06:00 开始展示，凌晨的空闲块从 06:00 起算，避免生成不可见的日程
EARLIEST_START = 6 * 60


def _get_owned_task(task_id: int, user: User, db: Session) -> Task:
    task = db.get(Task, task_id)
    if task is None or task.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="任务不存在")
    return task


def _to_minutes(value: object) -> int:
    hours, minutes = str(value).split(":")[:2]
    return int(hours) * 60 + int(minutes)


def _to_time(minutes: int) -> dt.time:
    return dt.time(minutes // 60, minutes % 60)


def _candidate_blocks(task: Task, db: Session) -> list[dict[str, object]]:
    """获取目标周内时长足够、且落在 06:00-22:00 之间的空闲块。"""
    blocks = find_free_blocks(
        task.user_id, task.week_start, min_minutes=task.duration_min, db=db
    )
    candidates: list[dict[str, object]] = []
    for block in blocks:
        start = max(_to_minutes(block["start_time"]), EARLIEST_START)
        end = min(_to_minutes(block["end_time"]), LATEST_END)
        if start >= LATEST_END or end - start < task.duration_min:
            continue
        candidates.append(
            {"date": block["date"], "start": start, "end": end}
        )
    candidates.sort(key=lambda item: (item["date"], item["start"]))
    return candidates


def _pick_spread(
    candidates: list[dict[str, object]], count: int
) -> list[dict[str, object]]:
    """贪心分散：先排最早的块，之后每轮选与已选时间间隔最大的块。"""
    remaining = list(candidates)
    if not remaining or count <= 0:
        return []

    selected = [remaining.pop(0)]
    while remaining and len(selected) < count:
        best_index = 0
        best_key: tuple[float, int, int] | None = None
        for index, block in enumerate(remaining):
            point = dt.datetime.combine(
                block["date"], _to_time(int(block["start"]))
            )
            distance = min(
                abs(
                    (
                        point
                        - dt.datetime.combine(
                            chosen["date"], _to_time(int(chosen["start"]))
                        )
                    ).total_seconds()
                )
                for chosen in selected
            )
            # 间距相同时优先更早的日期 / 时间，保证结果稳定
            key = (distance, -block["date"].toordinal(), -int(block["start"]))
            if best_key is None or key > best_key:
                best_key = key
                best_index = index
        selected.append(remaining.pop(best_index))

    return selected


@router.get("", response_model=list[TaskRead])
def list_tasks(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Task]:
    stmt = (
        select(Task)
        .options(selectinload(Task.slots))
        .where(Task.user_id == current_user.id)
        .order_by(Task.week_start.desc(), Task.id.desc())
    )
    return list(db.scalars(stmt).all())


@router.post("", response_model=TaskRead, status_code=status.HTTP_201_CREATED)
def create_task(
    payload: TaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Task:
    task = Task(user_id=current_user.id, **payload.model_dump())
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


@router.post("/{task_id}/schedule", response_model=TaskScheduleResult)
def schedule_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    task = _get_owned_task(task_id, current_user, db)

    # 重复排期：先清理该任务的旧槽位，以及槽位对应的模板日程
    old_slots = list(
        db.scalars(select(TaskSlot).where(TaskSlot.task_id == task.id)).all()
    )
    old_schedule_ids = [slot.schedule_id for slot in old_slots if slot.schedule_id]
    for slot in old_slots:
        db.delete(slot)
    if old_schedule_ids:
        old_schedules = db.scalars(
            select(Schedule).where(
                Schedule.id.in_(old_schedule_ids),
                Schedule.user_id == current_user.id,
            )
        ).all()
        for old_schedule in old_schedules:
            db.delete(old_schedule)
    db.flush()

    chosen = _pick_spread(_candidate_blocks(task, db), task.target_count)
    chosen.sort(key=lambda item: (item["date"], item["start"]))

    created_slots: list[TaskSlot] = []
    for block in chosen:
        start_minutes = int(block["start"])
        end_minutes = start_minutes + task.duration_min
        schedule = Schedule(
            user_id=current_user.id,
            title=task.title,
            date=block["date"],
            start_time=_to_time(start_minutes),
            end_time=_to_time(end_minutes),
            status="pending",
            category="sport",
            source="template",
        )
        db.add(schedule)
        db.flush()

        slot = TaskSlot(
            task_id=task.id,
            date=block["date"],
            start_time=_to_time(start_minutes),
            end_time=_to_time(end_minutes),
            status="scheduled",
            schedule_id=schedule.id,
        )
        db.add(slot)
        created_slots.append(slot)

    task.status = "scheduled"
    db.commit()
    for slot in created_slots:
        db.refresh(slot)

    scheduled_count = len(created_slots)
    return {
        "scheduled_count": scheduled_count,
        "shortage": max(0, task.target_count - scheduled_count),
        "slots": created_slots,
    }
