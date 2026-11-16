"""调课通知识别（关键词规则解析）。

只解析文本并给出匹配线索，不修改任何数据；由 notices 路由结合用户日程
找到对应课程并保存解析结果，用户确认后才执行取消 / 调整时间。
"""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass

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
    "1": 0,
    "2": 1,
    "3": 2,
    "4": 3,
    "5": 4,
    "6": 5,
    "7": 6,
}
WEEKDAY_LABELS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

CANCEL_KEYWORDS = ("取消", "停课", "停上", "不上", "暂停")
CHANGE_KEYWORDS = (
    "改到",
    "改为",
    "改成",
    "调整至",
    "调整到",
    "换成",
    "换到",
    "调到",
    "移至",
    "移到",
)

WEEKDAY_RE = re.compile(r"(?:周|星期|礼拜)\s*([一二三四五六日天七1-7])")
TIME_RE = re.compile(r"(\d{1,2})\s*[:：]\s*(\d{2})")
TIME_RANGE_RE = re.compile(r"\s*(?:-|~|—|–|－|至|到)\s*(\d{1,2})\s*[:：]\s*(\d{2})")
SPLIT_RE = re.compile(r"[，,。；;！!？?\s]+")
TIME_MARKERS = ("上午", "下午", "晚上", "中午", "早上")
TITLE_TRIM_CHARS = " 的了在是有和与及、 「」『』【】[]()（）"


@dataclass
class ParsedNotice:
    """纯文本解析结果。"""

    action: str  # cancel / change / none
    weekday: int | None = None
    start_time: dt.time | None = None
    title_hint: str | None = None
    new_weekday: int | None = None
    new_start_time: dt.time | None = None
    new_end_time: dt.time | None = None


def _find_keyword(text: str) -> tuple[int, int, str] | None:
    """返回最早出现的动作关键词（位置、结束位置、动作）。"""
    best: tuple[int, int, str] | None = None
    for action, keywords in (("cancel", CANCEL_KEYWORDS), ("change", CHANGE_KEYWORDS)):
        for keyword in keywords:
            index = text.find(keyword)
            if index == -1:
                continue
            if best is None or index < best[0]:
                best = (index, index + len(keyword), action)
    return best


def _marker_between(segment: str, start: int, end: int) -> str:
    chunk = segment[start:end]
    for marker in TIME_MARKERS:
        if marker in chunk:
            return marker
    return ""


def _to_24_hour(hour: int, marker: str) -> int:
    if marker in ("下午", "晚上") and hour < 12:
        return hour + 12
    if marker == "中午" and hour < 11:
        return hour + 12
    if marker in ("上午", "早上") and hour == 12:
        return 0
    return hour


def _parse_time_at(
    segment: str, position: int
) -> tuple[dt.time | None, dt.time | None, tuple[int, int] | None]:
    """从 position 起找第一个时刻，并尝试解析紧跟的结束时刻。"""
    matched = TIME_RE.search(segment, position)
    if matched is None:
        return None, None, None

    marker = _marker_between(segment, position, matched.start())
    hour = _to_24_hour(int(matched.group(1)), marker)
    minute = int(matched.group(2))
    if hour > 23 or minute > 59:
        return None, None, None

    start = dt.time(hour, minute)
    end: dt.time | None = None
    end_position = matched.end()
    range_matched = TIME_RANGE_RE.match(segment, matched.end())
    if range_matched is not None:
        end_hour = _to_24_hour(int(range_matched.group(1)), marker)
        end_minute = int(range_matched.group(2))
        if end_hour <= 23 and end_minute <= 59:
            end = dt.time(end_hour, end_minute)
            end_position = range_matched.end()

    return start, end, (matched.start(), end_position)


def _extract_title(segment: str, span: tuple[int, int] | None) -> str | None:
    """从课程时间之外的文字里取课程名（通常是最后一个片段）。"""
    rest = segment
    if span is not None:
        rest = f"{segment[: span[0]]} {segment[span[1]:]}"

    tokens = [token for token in SPLIT_RE.split(rest) if token.strip()]
    if not tokens:
        return None

    title = tokens[-1].strip().strip(TITLE_TRIM_CHARS)
    if len(title) > 2 and title.endswith("课程"):
        title = title[:-2]
    if not title or title in {"课", "课程", "这节课", "该课"}:
        return None
    return title


def _extract_schedule_hint(segment: str) -> tuple[int | None, dt.time | None, str | None]:
    weekday_matched = WEEKDAY_RE.search(segment)
    weekday = WEEKDAY_CN.get(weekday_matched.group(1)) if weekday_matched else None
    search_from = weekday_matched.end() if weekday_matched else 0

    start, _end, span = _parse_time_at(segment, search_from)
    title = _extract_title(segment, span)
    return weekday, start, title


def parse_notice_text(raw_text: str) -> ParsedNotice:
    """解析通知文本，返回动作、原课程线索与新时间。"""
    text = raw_text.strip()
    keyword = _find_keyword(text)
    if keyword is None:
        return ParsedNotice(action="none")

    start_index, end_index, action = keyword
    before = text[:start_index]
    after = text[end_index:]

    if action == "cancel":
        # 「取消周三08:00的高等数学」：时间信息在关键词之后
        segment = f"{before} {after}"
        weekday, start_time, title = _extract_schedule_hint(segment)
        return ParsedNotice(
            action="cancel",
            weekday=weekday,
            start_time=start_time,
            title_hint=title,
        )

    # 「周三08:00的高等数学改到周五14:00-15:40」
    weekday, start_time, title = _extract_schedule_hint(before)

    new_weekday_matched = WEEKDAY_RE.search(after)
    new_weekday = (
        WEEKDAY_CN.get(new_weekday_matched.group(1)) if new_weekday_matched else None
    )
    new_start, new_end, _span = _parse_time_at(
        after, new_weekday_matched.end() if new_weekday_matched else 0
    )

    # 新时间信息完全缺失时无法自动调整
    if new_weekday is None and new_start is None:
        return ParsedNotice(action="none")

    return ParsedNotice(
        action="change",
        weekday=weekday,
        start_time=start_time,
        title_hint=title,
        new_weekday=new_weekday,
        new_start_time=new_start,
        new_end_time=new_end,
    )
