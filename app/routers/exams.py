"""考试录入与复习计划生成。"""
from __future__ import annotations

import datetime as dt

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..engine.scheduler import find_free_blocks
from ..models import Exam, Schedule, User
from ..schemas import ExamCreate, ExamRead, StudyPlanRead

router = APIRouter(prefix="/api/exams", tags=["考试"])

# 难度 -> (提前天数, 每日复习分钟数)
PLAN_RULES = {
    "hard": (14, 120),  # 难度 >= 4 星
    "medium": (7, 90),  # 难度 == 3 星
    "easy": (3, 60),  # 难度 <= 2 星
}

LUNCH_START = 12 * 60
LUNCH_END = 14 * 60
MORNING_START = 8 * 60
MORNING_END = 12 * 60
EVENING_START = 18 * 60
EVENING_END = 22 * 60


def _get_owned_exam(exam_id: int, user: User, db: Session) -> Exam:
    exam = db.get(Exam, exam_id)
    if exam is None or exam.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="考试不存在")
    return exam


def _plan_rule(difficulty: int) -> tuple[int, int]:
    if difficulty >= 4:
        return PLAN_RULES["hard"]
    if difficulty == 3:
        return PLAN_RULES["medium"]
    return PLAN_RULES["easy"]


def _to_minutes(text: str) -> int:
    hours, minutes = text.split(":")
    return int(hours) * 60 + int(minutes)


def _format_minutes(minutes: int) -> str:
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def _split_around_lunch(start: int, end: int) -> list[tuple[int, int]]:
    """把空闲区间按 12:00-14:00 午休切开，返回可安排复习的子区间。"""
    if end <= LUNCH_START or start >= LUNCH_END:
        return [(start, end)]
    parts: list[tuple[int, int]] = []
    if start < LUNCH_START:
        parts.append((start, LUNCH_START))
    if end > LUNCH_END:
        parts.append((LUNCH_END, end))
    return parts


def _pick_window(ranges: list[tuple[int, int]], need: int) -> tuple[int, int] | None:
    """在空闲子区间里挑出一段 need 分钟，优先上午、其次晚上、最后兜底。"""
    candidates: list[tuple[int, int]] = []
    for start, end in ranges:
        morning_start, morning_end = max(start, MORNING_START), min(end, MORNING_END)
        if morning_end - morning_start >= need:
            candidates.append((0, morning_start))
        evening_start, evening_end = max(start, EVENING_START), min(end, EVENING_END)
        if evening_end - evening_start >= need:
            candidates.append((1, evening_start))
        if end - start >= need:
            candidates.append((2, start))
    if not candidates:
        return None
    _, chosen_start = min(candidates)
    return chosen_start, chosen_start + need


def _find_study_window(
    user_id: int, day: dt.date, need: int, db: Session
) -> tuple[int, int] | None:
    blocks = find_free_blocks(user_id, day, min_minutes=need, db=db)
    ranges: list[tuple[int, int]] = []
    for block in blocks:
        if block["date"] != day:
            continue
        start = _to_minutes(str(block["start_time"]))
        end = _to_minutes(str(block["end_time"]))
        ranges.extend(_split_around_lunch(start, end))
    ranges.sort()
    return _pick_window(ranges, need)


@router.get("", response_model=list[ExamRead])
def list_exams(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[Exam]:
    stmt = (
        select(Exam)
        .where(Exam.user_id == current_user.id)
        .order_by(Exam.exam_date, Exam.id)
    )
    return list(db.scalars(stmt).all())


@router.post("", response_model=ExamRead, status_code=status.HTTP_201_CREATED)
def create_exam(
    payload: ExamCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Exam:
    exam = Exam(
        user_id=current_user.id,
        # title 为旧表结构的必填字段，与科目保持一致
        title=payload.subject,
        subject=payload.subject,
        exam_date=payload.exam_date,
        difficulty=payload.difficulty,
    )
    db.add(exam)
    db.commit()
    db.refresh(exam)
    return exam


@router.post("/{exam_id}/plan", response_model=StudyPlanRead)
def generate_study_plan(
    exam_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> dict[str, object]:
    exam = _get_owned_exam(exam_id, current_user, db)
    days_before, minutes_per_day = _plan_rule(exam.difficulty)
    subject = exam.subject or exam.title

    # 重复生成：先清理该考试之前生成的模板日程
    old_schedules = db.scalars(
        select(Schedule).where(
            Schedule.user_id == current_user.id,
            Schedule.exam_id == exam.id,
            Schedule.source == "template",
        )
    ).all()
    for old in old_schedules:
        db.delete(old)
    db.flush()

    created: list[Schedule] = []
    skipped_days: list[dt.date] = []

    for index in range(days_before):
        day = exam.exam_date - dt.timedelta(days=days_before - index)
        window = _find_study_window(current_user.id, day, minutes_per_day, db)
        if window is None:
            skipped_days.append(day)
            continue

        start_minutes, end_minutes = window
        schedule = Schedule(
            user_id=current_user.id,
            title=f"复习{subject} 第{index + 1}天",
            date=day,
            start_time=dt.time(start_minutes // 60, start_minutes % 60),
            end_time=dt.time(end_minutes // 60, end_minutes % 60),
            status="pending",
            category="study",
            source="template",
            exam_id=exam.id,
        )
        db.add(schedule)
        created.append(schedule)

    db.commit()
    for schedule in created:
        db.refresh(schedule)

    return {"created": created, "skipped_days": skipped_days}
