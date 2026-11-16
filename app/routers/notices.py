"""调课通知：解析文本、确认执行、丢弃。

解析只保存结果，不修改日程；用户确认后才会取消课程或调整时间。
"""
from __future__ import annotations

import datetime as dt
import json

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..engine.notice_parser import WEEKDAY_LABELS, ParsedNotice, parse_notice_text
from ..models import Notice, Schedule, User
from ..schemas import (
    NoticeConfirmResult,
    NoticeParseRequest,
    NoticeParseResult,
    NoticeStatusResult,
    ScheduleRead,
)

router = APIRouter(prefix="/api/notices", tags=["调课通知"])


def _same_time(left: dt.time, right: dt.time) -> bool:
    return left.hour == right.hour and left.minute == right.minute


def _titles_match(hint: str, title: str) -> bool:
    left = "".join(hint.split())
    right = "".join((title or "").split())
    return bool(left and right and (left in right or right in left))


def _pick_schedule(
    schedules: list[Schedule], parsed: ParsedNotice, today: dt.date
) -> tuple[Schedule, bool, bool, bool] | None:
    """在用户日程中找最可能的课程，返回（课程、标题命中、星期命中、时间命中）。"""
    if parsed.weekday is None and parsed.title_hint is None:
        return None

    best: tuple[tuple[int, int, int], Schedule, bool, bool, bool] | None = None
    for schedule in schedules:
        title_ok = parsed.title_hint is not None and _titles_match(
            parsed.title_hint, schedule.title
        )
        weekday_ok = (
            parsed.weekday is not None and schedule.date.weekday() == parsed.weekday
        )
        time_ok = parsed.start_time is not None and _same_time(
            schedule.start_time, parsed.start_time
        )

        if not (title_ok or weekday_ok):
            continue

        score = 5 * title_ok + 2 * weekday_ok + 2 * time_ok
        delta = (schedule.date - today).days
        # 同分时优先未来最近的课程
        key = (score, 1 if delta >= 0 else 0, -abs(delta))
        if best is None or key > best[0]:
            best = (key, schedule, title_ok, weekday_ok, time_ok)

    if best is None:
        return None
    _, schedule, title_ok, weekday_ok, time_ok = best
    return schedule, title_ok, weekday_ok, time_ok


def _confidence(
    parsed: ParsedNotice,
    schedules: list[Schedule],
    schedule: Schedule,
    title_ok: bool,
    weekday_ok: bool,
    time_ok: bool,
) -> str:
    if not (weekday_ok and time_ok):
        return "低"
    if title_ok:
        return "高"
    if parsed.title_hint is not None:
        return "低"
    # 没给出课程名时，只有该时段唯一一门课才算可靠
    slot_titles = {
        item.title
        for item in schedules
        if item.date.weekday() == schedule.date.weekday()
        and _same_time(item.start_time, schedule.start_time)
    }
    return "高" if len(slot_titles) == 1 else "低"


def _format_new_time(parsed: ParsedNotice) -> str | None:
    parts: list[str] = []
    if parsed.new_weekday is not None:
        parts.append(WEEKDAY_LABELS[parsed.new_weekday])
    if parsed.new_start_time is not None:
        text = parsed.new_start_time.strftime("%H:%M")
        if parsed.new_end_time is not None:
            text += f"-{parsed.new_end_time.strftime('%H:%M')}"
        parts.append(text)
    return "".join(parts) or None


def _message_for(action: str, schedule: Schedule, new_time: str | None) -> str:
    weekday = WEEKDAY_LABELS[schedule.date.weekday()]
    start = schedule.start_time.strftime("%H:%M")
    if action == "cancel":
        return f"检测到：{weekday}{start}的「{schedule.title}」需要取消，确认吗？"
    return f"检测到：{weekday}{start}的「{schedule.title}」改为{new_time}，确认吗？"


def _load_owned_notice(notice_id: int, user: User, db: Session) -> Notice:
    notice = db.get(Notice, notice_id)
    if notice is None or notice.user_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="通知不存在")
    return notice


def _parse_stored_time(value: str | None) -> dt.time | None:
    if not value:
        return None
    return dt.time.fromisoformat(value)


@router.post("/parse", response_model=NoticeParseResult)
def parse_notice(
    payload: NoticeParseRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NoticeParseResult:
    parsed = parse_notice_text(payload.text)
    today = dt.date.today()
    schedules = list(
        db.scalars(select(Schedule).where(Schedule.user_id == current_user.id))
    )

    action = parsed.action
    matched: Schedule | None = None
    confidence = "低"
    new_time: str | None = None
    message = "未能识别调课信息，请手动处理。"

    if action != "none":
        picked = _pick_schedule(schedules, parsed, today)
        if picked is None:
            action = "none"
            message = "未能匹配到对应课程，请手动处理。"
        else:
            matched, title_ok, weekday_ok, time_ok = picked
            confidence = _confidence(
                parsed, schedules, matched, title_ok, weekday_ok, time_ok
            )
            if action == "change":
                new_time = _format_new_time(parsed)
                if new_time is None:
                    action = "none"
                    matched = None
                    message = "未能识别新的上课时间，请手动处理。"
                else:
                    message = _message_for(action, matched, new_time)
            else:
                message = _message_for(action, matched, None)

    payload_json = {
        "action": action,
        "matched_schedule_id": matched.id if matched else None,
        "new_weekday": parsed.new_weekday,
        "new_start_time": (
            parsed.new_start_time.strftime("%H:%M:%S") if parsed.new_start_time else None
        ),
        "new_end_time": (
            parsed.new_end_time.strftime("%H:%M:%S") if parsed.new_end_time else None
        ),
        "new_time": new_time,
        "confidence": confidence,
        "message": message,
    }

    notice = Notice(
        user_id=current_user.id,
        raw_text=payload.text,
        parsed_json=json.dumps(payload_json, ensure_ascii=False),
        status="pending",
    )
    db.add(notice)
    db.commit()
    db.refresh(notice)

    return NoticeParseResult(
        id=notice.id,
        action=action,
        matched_schedule=ScheduleRead.model_validate(matched) if matched else None,
        new_time=new_time,
        confidence=confidence,
        message=message,
    )


@router.post("/{notice_id}/confirm", response_model=NoticeConfirmResult)
def confirm_notice(
    notice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NoticeConfirmResult:
    notice = _load_owned_notice(notice_id, current_user, db)
    if notice.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, detail="该通知已处理")

    data = json.loads(notice.parsed_json or "{}")
    action = data.get("action")
    if action not in ("cancel", "change"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="解析结果为空，请手动处理"
        )

    schedule_id = data.get("matched_schedule_id")
    if not isinstance(schedule_id, int):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, detail="解析结果缺少对应课程，请手动处理"
        )
    schedule = db.get(Schedule, schedule_id)
    if schedule is None or schedule.user_id != current_user.id:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="对应课程不存在，可能已被删除"
        )

    if action == "cancel":
        title = schedule.title
        db.delete(schedule)
        notice.status = "confirmed"
        db.commit()
        return NoticeConfirmResult(
            action="cancel",
            status="confirmed",
            message=f"已取消「{title}」",
            schedule=None,
        )

    new_start = _parse_stored_time(data.get("new_start_time")) or schedule.start_time
    new_end = _parse_stored_time(data.get("new_end_time"))
    if new_end is None:
        duration = dt.datetime.combine(dt.date.today(), schedule.end_time) - dt.datetime.combine(
            dt.date.today(), schedule.start_time
        )
        new_end = (
            dt.datetime.combine(dt.date.today(), new_start) + duration
        ).time()
    if new_start >= new_end:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY, detail="结束时间必须晚于开始时间"
        )

    new_weekday = data.get("new_weekday")
    new_date = schedule.date
    if isinstance(new_weekday, int):
        new_date = schedule.date - dt.timedelta(
            days=schedule.date.weekday()
        ) + dt.timedelta(days=new_weekday)

    schedule.date = new_date
    schedule.start_time = new_start
    schedule.end_time = new_end
    notice.status = "confirmed"
    db.commit()
    db.refresh(schedule)

    return NoticeConfirmResult(
        action="change",
        status="confirmed",
        message=f"已调整「{schedule.title}」到{data.get('new_time') or new_date}",
        schedule=ScheduleRead.model_validate(schedule),
    )


@router.post("/{notice_id}/discard", response_model=NoticeStatusResult)
def discard_notice(
    notice_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NoticeStatusResult:
    notice = _load_owned_notice(notice_id, current_user, db)
    if notice.status != "pending":
        raise HTTPException(status.HTTP_409_CONFLICT, detail="该通知已处理")

    notice.status = "discarded"
    db.commit()
    return NoticeStatusResult(status="discarded", message="已丢弃该通知")
