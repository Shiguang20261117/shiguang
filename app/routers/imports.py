"""课表文本导入。

每行格式：``星期几 HH:MM-HH:MM 课程名 [地点]``
- 星期支持 周一 / 星期一 / 礼拜一 / 周1 / 一 / Mon / Monday 等写法
- 方括号内为可选地点，支持 [ ] 与 【 】
- 每条课程按周重复，默认覆盖当前日期起 20 周（整个学期）
- 单行解析或创建失败只记录到 errors，不影响其他行
"""
from __future__ import annotations

import datetime as dt
import logging
import re

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import User
from ..schemas import TimetableImportError, TimetableImportRequest, TimetableImportResult
from .series import create_series_with_schedules

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/import", tags=["导入"])

# 默认导入 20 周
DEFAULT_WEEKS = 20
MAX_TEXT_FIELD_LENGTH = 200

WEEKDAY_CN = {
    "一": 0,
    "二": 1,
    "三": 2,
    "四": 3,
    "五": 4,
    "六": 5,
    "日": 6,
    "天": 6,
    "七": 6,
}
WEEKDAY_EN = {
    "mon": 0,
    "monday": 0,
    "tue": 1,
    "tues": 1,
    "tuesday": 1,
    "wed": 2,
    "weds": 2,
    "wednesday": 2,
    "thu": 3,
    "thur": 3,
    "thurs": 3,
    "thursday": 3,
    "fri": 4,
    "friday": 4,
    "sat": 5,
    "saturday": 5,
    "sun": 6,
    "sunday": 6,
}
WEEKDAY_PREFIXES = ("星期", "礼拜", "禮拜", "周")

# 星期 + 时间段 + 剩余内容（课程名与可选地点）
LINE_RE = re.compile(
    r"^(?P<weekday>\S+)\s+"
    r"(?P<start>\d{1,2}\s*[:：]\s*\d{2})\s*"
    r"[-~—–－至到]\s*"
    r"(?P<end>\d{1,2}\s*[:：]\s*\d{2})\s*"
    r"(?P<rest>.+)$"
)
LOCATION_RE = re.compile(r"[\[【](?P<location>[^\]】]+)[\]】]\s*$")
TIME_RE = re.compile(r"^(\d{1,2})\s*[:：]\s*(\d{2})$")

FORMAT_HINT = "格式不正确，应为「周一 08:00-09:30 课程名 [地点]」"


def _parse_weekday(token: str) -> int | None:
    text = token.strip().lower().rstrip(".")
    for prefix in WEEKDAY_PREFIXES:
        if text.startswith(prefix):
            text = text[len(prefix) :]
            break

    if text in WEEKDAY_EN:
        return WEEKDAY_EN[text]
    if text in WEEKDAY_CN:
        return WEEKDAY_CN[text]
    if text.isdigit():
        number = int(text)
        if 1 <= number <= 7:
            # 1=周一 ... 7=周日
            return number - 1
    return None


def _parse_time(value: str) -> dt.time:
    matched = TIME_RE.match(value)
    if matched is None:
        raise ValueError(f"时间「{value}」格式不正确")
    hour, minute = int(matched.group(1)), int(matched.group(2))
    try:
        return dt.time(hour=hour, minute=minute)
    except ValueError as exc:
        raise ValueError(f"时间「{value}」不是有效时刻") from exc


def _parse_line(line: str) -> dict[str, object]:
    matched = LINE_RE.match(line)
    if matched is None:
        raise ValueError(FORMAT_HINT)

    weekday_token = matched.group("weekday")
    weekday = _parse_weekday(weekday_token)
    if weekday is None:
        raise ValueError(f"无法识别星期写法「{weekday_token}」")

    start_time = _parse_time(matched.group("start"))
    end_time = _parse_time(matched.group("end"))
    if end_time <= start_time:
        raise ValueError("结束时间必须晚于开始时间")

    rest = matched.group("rest").strip()
    location: str | None = None
    location_matched = LOCATION_RE.search(rest)
    if location_matched is not None:
        location = location_matched.group("location").strip() or None
        rest = rest[: location_matched.start()].strip()

    title = rest.strip()
    if not title:
        raise ValueError("缺少课程名")
    if len(title) > MAX_TEXT_FIELD_LENGTH:
        raise ValueError("课程名过长（最多 200 字）")
    if location is not None and len(location) > MAX_TEXT_FIELD_LENGTH:
        raise ValueError("地点过长（最多 200 字）")

    return {
        "title": title,
        "weekday": weekday,
        "start_time": start_time,
        "end_time": end_time,
        "location": location,
    }


@router.post("/timetable", response_model=TimetableImportResult)
def import_timetable(
    payload: TimetableImportRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> TimetableImportResult:
    start_date = dt.date.today()
    end_date = start_date + dt.timedelta(weeks=DEFAULT_WEEKS) - dt.timedelta(days=1)

    created = 0
    errors: list[TimetableImportError] = []

    for line_number, raw_line in enumerate(payload.text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue

        try:
            entry = _parse_line(line)
        except ValueError as exc:
            errors.append(
                TimetableImportError(line=line_number, content=line, reason=str(exc))
            )
            continue

        try:
            create_series_with_schedules(
                db,
                user_id=current_user.id,
                start_date=start_date,
                end_date=end_date,
                **entry,
            )
            db.commit()
            created += 1
        except Exception:
            db.rollback()
            logger.exception("导入课表第 %s 行失败：%s", line_number, line)
            errors.append(
                TimetableImportError(
                    line=line_number,
                    content=line,
                    reason="创建日程失败，请稍后重试",
                )
            )

    return TimetableImportResult(created=created, errors=errors)
