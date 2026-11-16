"""周计划导出：把一周的日程渲染成 PNG 图片。

布局参考前端周视图：顶部日期范围标题，7 列时间格（06:00-24:00），
固定日常作为浅灰背景块，复习计划绿色、运动排程蓝色，其余按标题散列配色。
"""
from __future__ import annotations

import datetime as dt
import io
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Depends, Query, Response
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import Routine, Schedule, User

router = APIRouter(prefix="/api/export", tags=["导出"])

WEEKDAY_LABELS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]

# 时间格范围与尺寸（像素）
START_HOUR = 6
END_HOUR = 24
HOUR_HEIGHT = 46
TIME_AXIS_WIDTH = 58
DAY_WIDTH = 152
MARGIN = 24
TITLE_HEIGHT = 62
HEADER_HEIGHT = 50
FOOTER_HEIGHT = 46

BOARD_WIDTH = TIME_AXIS_WIDTH + DAY_WIDTH * 7
CANVAS_WIDTH = MARGIN * 2 + BOARD_WIDTH
GRID_HEIGHT = (END_HOUR - START_HOUR) * HOUR_HEIGHT

COLOR_BG = "#FFFDFA"
COLOR_BORDER = "#EAE2D8"
COLOR_BORDER_SOFT = "#F1EAE1"
COLOR_TEXT = "#3A2E24"
COLOR_TEXT_2 = "#6F6357"
COLOR_TEXT_3 = "#A79C90"
COLOR_TODAY = "#FFF7EF"
COLOR_HEADER_BG = "#FFF9F2"

# 分类配色：复习=绿色，运动=蓝色
CATEGORY_COLORS = {
    "study": {"bg": "#E8F3EC", "border": "#9EC9AE", "text": "#2F6446"},
    "sport": {"bg": "#E6EFFB", "border": "#9DBCE8", "text": "#2F4D7F"},
}
ROUTINE_COLORS = {"bg": "#EEEAE3", "border": "#D9D2C8", "text": "#7A736A"}

# 其他日程的暖色系循环
OTHER_PALETTE = [
    {"bg": "#FFF0E2", "border": "#F0B183", "text": "#8A4A20"},
    {"bg": "#E8F3EC", "border": "#9EC9AE", "text": "#2F6446"},
    {"bg": "#E9EEFB", "border": "#A8B8E8", "text": "#34497F"},
    {"bg": "#FDEEF1", "border": "#EEB3C0", "text": "#8D3B4F"},
    {"bg": "#F3EDFB", "border": "#C1ADE4", "text": "#553F80"},
    {"bg": "#FDF6DC", "border": "#E0C878", "text": "#7A6220"},
]

FONT_REGULAR_CANDIDATES = [
    r"C:\Windows\Fonts\msyh.ttc",  # 微软雅黑
    r"C:\Windows\Fonts\simhei.ttf",  # 黑体
    "/System/Library/Fonts/PingFang.ttc",
    "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
]
FONT_BOLD_CANDIDATES = [
    r"C:\Windows\Fonts\msyhbd.ttc",
    *FONT_REGULAR_CANDIDATES,
]


@lru_cache(maxsize=None)
def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    """优先使用系统中文字体，找不到时降级为 Pillow 默认字体。"""
    candidates = FONT_BOLD_CANDIDATES if bold else FONT_REGULAR_CANDIDATES
    for path in candidates:
        if not Path(path).exists():
            continue
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow < 10.1 不支持 size 参数
        return ImageFont.load_default()


def _to_minutes(value: object) -> int:
    if isinstance(value, dt.time):
        return value.hour * 60 + value.minute
    hours, minutes = str(value).split(":")[:2]
    return int(hours) * 60 + int(minutes)


def _text_width(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.FreeTypeFont) -> float:
    return draw.textlength(text, font=font)


def _ellipsize(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    max_width: float,
) -> str:
    """按像素宽度截断文本并补省略号。"""
    if max_width <= 0:
        return ""
    if _text_width(draw, text, font) <= max_width:
        return text

    ellipsis = "…"
    low, high = 0, len(text)
    while low < high:
        mid = (low + high + 1) // 2
        if _text_width(draw, text[:mid] + ellipsis, font=font) <= max_width:
            low = mid
        else:
            high = mid - 1
    return text[:low] + ellipsis if low else ""


def _color_of(title: str, category: str) -> dict[str, str]:
    if category in CATEGORY_COLORS:
        return CATEGORY_COLORS[category]
    digest = 0
    for char in title:
        digest = (digest * 31 + ord(char)) % 9973
    return OTHER_PALETTE[digest % len(OTHER_PALETTE)]


def _layout_day(events: list[dict[str, object]]) -> list[dict[str, object]]:
    """同一天内重叠的日程分列排布，避免互相遮挡。"""
    ordered = sorted(events, key=lambda item: (item["start"], item["end"]))  # type: ignore[arg-type]
    clusters: list[dict[str, object]] = []
    for event in ordered:
        for cluster in clusters:
            if event["start"] < cluster["end"]:  # type: ignore[operator]
                cluster["items"].append(event)  # type: ignore[union-attr]
                cluster["end"] = max(cluster["end"], event["end"])  # type: ignore[type-var]
                break
        else:
            clusters.append({"end": event["end"], "items": [event]})

    laid_out: list[dict[str, object]] = []
    for cluster in clusters:
        columns: list[list[dict[str, object]]] = []
        for event in cluster["items"]:  # type: ignore[union-attr]
            for column in columns:
                if column[-1]["end"] <= event["start"]:
                    column.append(event)
                    break
            else:
                columns.append([event])
        for index, column in enumerate(columns):
            for event in column:
                laid_out.append(
                    {**event, "column_index": index, "column_count": len(columns)}
                )
    return laid_out


def _build_day_data(
    start: dt.date, schedules: list[Schedule], routines: list[Routine]
) -> list[dict[str, object]]:
    days: list[dict[str, object]] = []
    for offset in range(7):
        day = start + dt.timedelta(days=offset)
        days.append(
            {
                "date": day,
                "weekday_label": WEEKDAY_LABELS[offset],
                "routines": [],
                "events": [],
            }
        )

    by_date = {day["date"]: day for day in days}

    for routine in routines:
        day = by_date.get(start + dt.timedelta(days=routine.weekday))
        if day is None:
            continue
        day["routines"].append(  # type: ignore[union-attr]
            {
                "title": routine.title,
                "start": _to_minutes(routine.start_time),
                "end": _to_minutes(routine.end_time),
            }
        )

    for schedule in schedules:
        day = by_date.get(schedule.date)
        if day is None:
            continue
        day["events"].append(  # type: ignore[union-attr]
            {
                "title": schedule.title,
                "start": _to_minutes(schedule.start_time),
                "end": _to_minutes(schedule.end_time),
                "category": schedule.category or "general",
            }
        )

    for day in days:
        day["routines"].sort(key=lambda item: item["start"])  # type: ignore[union-attr]
        day["events"] = _layout_day(day["events"])  # type: ignore[arg-type]
    return days


def _draw_legend(draw: ImageDraw.ImageDraw, right: int, y: int) -> None:
    label_font = _font(11)
    items = [
        ("复习", CATEGORY_COLORS["study"]),
        ("运动", CATEGORY_COLORS["sport"]),
        ("固定日常", ROUTINE_COLORS),
    ]
    widths = [16 + 6 + _text_width(draw, label, label_font) for label, _ in items]
    x = right - sum(widths) - 24 * (len(items) - 1)
    for (label, colors), width in zip(items, widths):
        draw.rounded_rectangle(
            [x, y + 2, x + 14, y + 14],
            radius=4,
            fill=colors["bg"],
            outline=colors["border"],
        )
        draw.text((x + 20, y), label, font=label_font, fill=COLOR_TEXT_2)
        x += width + 24


def _render_week_png(
    start: dt.date,
    days: list[dict[str, object]],
    generated_at: dt.datetime,
) -> bytes:
    grid_top = MARGIN + TITLE_HEIGHT + HEADER_HEIGHT
    grid_bottom = grid_top + GRID_HEIGHT
    board_bottom = grid_bottom
    canvas_height = grid_bottom + FOOTER_HEIGHT + MARGIN

    image = Image.new("RGB", (CANVAS_WIDTH, canvas_height), COLOR_BG)
    draw = ImageDraw.Draw(image)

    end = start + dt.timedelta(days=6)
    title_font = _font(24, bold=True)
    subtitle_font = _font(12)
    weekday_font = _font(13, bold=True)
    date_font = _font(12)
    axis_font = _font(11)
    event_title_font = _font(12, bold=True)
    event_time_font = _font(10)
    routine_title_font = _font(11, bold=True)
    routine_time_font = _font(10)
    footer_font = _font(10)

    # 标题
    title = f"{start.year}年{start.month}月{start.day}日 - {end.year}年{end.month}月{end.day}日"
    draw.text((MARGIN, MARGIN - 2), title, font=title_font, fill=COLOR_TEXT)

    total = sum(len(day["events"]) for day in days)  # type: ignore[arg-type]
    subtitle = f"拾光 · 周计划　共 {total} 项日程"
    draw.text((MARGIN, MARGIN + 36), subtitle, font=subtitle_font, fill=COLOR_TEXT_2)
    _draw_legend(draw, MARGIN + BOARD_WIDTH, MARGIN + 34)

    # 周视图面板
    draw.rounded_rectangle(
        [MARGIN, MARGIN + TITLE_HEIGHT, MARGIN + BOARD_WIDTH, board_bottom],
        radius=10,
        fill=COLOR_BG,
        outline=COLOR_BORDER,
    )
    draw.rounded_rectangle(
        [MARGIN, MARGIN + TITLE_HEIGHT, MARGIN + BOARD_WIDTH, MARGIN + TITLE_HEIGHT + HEADER_HEIGHT],
        radius=10,
        fill=COLOR_HEADER_BG,
    )
    # 抹平表头下方的圆角，让表头与时间格无缝衔接
    draw.rectangle(
        [MARGIN + 1, MARGIN + TITLE_HEIGHT + HEADER_HEIGHT - 10, MARGIN + BOARD_WIDTH - 1, MARGIN + TITLE_HEIGHT + HEADER_HEIGHT],
        fill=COLOR_HEADER_BG,
    )
    draw.line(
        [(MARGIN, MARGIN + TITLE_HEIGHT + HEADER_HEIGHT), (MARGIN + BOARD_WIDTH, MARGIN + TITLE_HEIGHT + HEADER_HEIGHT)],
        fill=COLOR_BORDER,
    )

    today = dt.date.today()
    grid_left = MARGIN + TIME_AXIS_WIDTH

    # 今日列高亮
    for index, day in enumerate(days):
        if day["date"] == today:
            draw.rectangle(
                [
                    grid_left + index * DAY_WIDTH + 1,
                    MARGIN + TITLE_HEIGHT + HEADER_HEIGHT,
                    grid_left + (index + 1) * DAY_WIDTH - 1,
                    grid_bottom,
                ],
                fill=COLOR_TODAY,
            )

    # 表头：星期 + 日期
    header_top = MARGIN + TITLE_HEIGHT
    for index, day in enumerate(days):
        column_left = grid_left + index * DAY_WIDTH
        column_center = column_left + DAY_WIDTH / 2
        name_color = "#C2622C" if day["date"] == today else COLOR_TEXT_2
        date_color = "#C2622C" if day["date"] == today else COLOR_TEXT_3
        name = str(day["weekday_label"])
        date_text = f"{day['date'].month}/{day['date'].day}"
        draw.text(
            (column_center - _text_width(draw, name, weekday_font) / 2, header_top + 9),
            name,
            font=weekday_font,
            fill=name_color,
        )
        draw.text(
            (column_center - _text_width(draw, date_text, date_font) / 2, header_top + 28),
            date_text,
            font=date_font,
            fill=date_color,
        )

    # 网格线
    for hour in range(START_HOUR, END_HOUR + 1):
        y = grid_top + (hour - START_HOUR) * HOUR_HEIGHT
        draw.line([(MARGIN + 1, y), (MARGIN + BOARD_WIDTH - 1, y)], fill=COLOR_BORDER_SOFT)
        if hour < END_HOUR:
            label = f"{hour:02d}:00"
            draw.text(
                (MARGIN + TIME_AXIS_WIDTH - 8 - _text_width(draw, label, axis_font), y - 7),
                label,
                font=axis_font,
                fill=COLOR_TEXT_3,
            )

    for index in range(8):
        x = grid_left + index * DAY_WIDTH
        draw.line(
            [(x, MARGIN + TITLE_HEIGHT), (x, board_bottom)],
            fill=COLOR_BORDER_SOFT if 0 < index < 7 else COLOR_BORDER,
        )
    draw.line(
        [(MARGIN + TIME_AXIS_WIDTH, MARGIN + TITLE_HEIGHT), (MARGIN + TIME_AXIS_WIDTH, board_bottom)],
        fill=COLOR_BORDER,
    )

    def clamp(minutes: int) -> int:
        return max(START_HOUR * 60, min(END_HOUR * 60, minutes))

    def y_of(minutes: int) -> int:
        return int(grid_top + (minutes - START_HOUR * 60) / 60 * HOUR_HEIGHT)

    # 逐列绘制：固定日常在下层，日程在上层
    for index, day in enumerate(days):
        column_left = grid_left + index * DAY_WIDTH

        for routine in day["routines"]:  # type: ignore[union-attr]
            start_min = clamp(int(routine["start"]))
            end_min = clamp(int(routine["end"]))
            if end_min <= start_min:
                continue
            y0, y1 = y_of(start_min), y_of(end_min)
            height = max(y1 - y0 - 3, 22)
            x0 = column_left + 3
            x1 = column_left + DAY_WIDTH - 3
            draw.rounded_rectangle(
                [x0, y0, x1, y0 + height],
                radius=6,
                fill=ROUTINE_COLORS["bg"],
                outline=ROUTINE_COLORS["border"],
            )
            title = _ellipsize(draw, str(routine["title"]), routine_title_font, x1 - x0 - 12)
            draw.text((x0 + 6, y0 + 4), title, font=routine_title_font, fill=ROUTINE_COLORS["text"])
            if height >= 34:
                time_text = f"{int(routine['start']) // 60:02d}:{int(routine['start']) % 60:02d}"
                time_text += f"-{int(routine['end']) // 60:02d}:{int(routine['end']) % 60:02d}"
                draw.text((x0 + 6, y0 + 19), time_text, font=routine_time_font, fill=ROUTINE_COLORS["text"])

        for event in day["events"]:  # type: ignore[union-attr]
            start_min = clamp(int(event["start"]))
            end_min = clamp(int(event["end"]))
            if end_min <= start_min:
                continue
            y0, y1 = y_of(start_min), y_of(end_min)
            height = max(y1 - y0 - 4, 26)

            column_count = int(event["column_count"])
            column_index = int(event["column_index"])
            slot_width = (DAY_WIDTH - 4) / column_count
            x0 = column_left + 2 + column_index * slot_width
            x1 = x0 + slot_width - 2

            palette = _color_of(str(event["title"]), str(event["category"]))
            draw.rounded_rectangle(
                [x0, y0, x1, y0 + height],
                radius=6,
                fill=palette["bg"],
                outline=palette["border"],
            )

            text_width = max(x1 - x0 - 10, 0)
            title = _ellipsize(draw, str(event["title"]), event_title_font, text_width)
            if title:
                draw.text((x0 + 5, y0 + 4), title, font=event_title_font, fill=palette["text"])
            if height >= 32 and text_width > 10:
                time_text = f"{int(event['start']) // 60:02d}:{int(event['start']) % 60:02d}"
                time_text += f"-{int(event['end']) // 60:02d}:{int(event['end']) % 60:02d}"
                time_text = _ellipsize(draw, time_text, event_time_font, text_width)
                draw.text((x0 + 5, y0 + 20), time_text, font=event_time_font, fill=palette["text"])

    # 底部署名与生成时间
    footer = f"由拾光生成 · 生成时间 {generated_at.strftime('%Y-%m-%d %H:%M')}"
    draw.text(
        ((CANVAS_WIDTH - _text_width(draw, footer, footer_font)) / 2, grid_bottom + 16),
        footer,
        font=footer_font,
        fill=COLOR_TEXT_3,
    )

    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


@router.get(
    "/week.png",
    response_class=Response,
    responses={200: {"content": {"image/png": {}}}},
    summary="导出周计划图片",
)
def export_week_png(
    start_date: dt.date | None = Query(
        default=None, description="目标周的任意一天（含），默认本周；会归一到周一"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    anchor = start_date or dt.date.today()
    start = anchor - dt.timedelta(days=anchor.weekday())
    end = start + dt.timedelta(days=6)

    schedules = list(
        db.scalars(
            select(Schedule)
            .where(
                Schedule.user_id == current_user.id,
                Schedule.date >= start,
                Schedule.date <= end,
            )
            .order_by(Schedule.date, Schedule.start_time)
        ).all()
    )
    routines = list(
        db.scalars(
            select(Routine).where(
                Routine.user_id == current_user.id,
                Routine.is_active.is_(True),
            )
        ).all()
    )

    days = _build_day_data(start, schedules, routines)
    content = _render_week_png(start, days, dt.datetime.now())

    filename = f"shiguang-week-{start.isoformat()}.png"
    return Response(
        content=content,
        media_type="image/png",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Cache-Control": "no-store",
        },
    )
