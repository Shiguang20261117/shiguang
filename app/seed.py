"""演示数据种子脚本。

仅在用户表为空时执行，保证首次部署 / 评委打开时即可看到完整效果：
- 演示账号：demo / Shiguang2026
- 当前周的一周课表
- 一门考试
- 一个跑步任务
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import Exam, Schedule, Task, User
from .security import hash_password

DEMO_USERNAME = "demo"
DEMO_PASSWORD = "Shiguang2026"
DEMO_EMAIL = "demo@shiguang.local"

# (weekday, 课程名, 开始时间, 结束时间, 地点)，weekday: 0=周一 ... 6=周日
DEMO_COURSES: list[tuple[int, str, str, str, str]] = [
    (0, "高等数学", "08:00", "09:40", "教学楼 A101"),
    (0, "大学英语", "10:00", "11:40", "外语楼 B203"),
    (1, "数据结构", "08:00", "09:40", "计算机楼 C305"),
    (1, "线性代数", "14:00", "15:40", "教学楼 A208"),
    (2, "计算机网络", "10:00", "11:40", "计算机楼 C302"),
    (2, "操作系统", "14:00", "15:40", "计算机楼 C401"),
    (3, "体育（篮球）", "08:00", "09:40", "体育馆"),
    (3, "数据库原理", "14:00", "15:40", "计算机楼 C305"),
    (4, "软件工程", "08:00", "09:40", "计算机楼 C210"),
    (4, "马克思主义基本原理", "10:00", "11:40", "教学楼 A102"),
]


def _parse_time(value: str) -> dt.time:
    hour, minute = value.split(":")
    return dt.time(int(hour), int(minute))


def seed_demo_data(db: Session) -> bool:
    """用户表为空时写入演示数据，返回是否实际执行了种子。"""
    if db.scalar(select(User).limit(1)) is not None:
        return False

    demo_user = User(
        username=DEMO_USERNAME,
        email=DEMO_EMAIL,
        hashed_password=hash_password(DEMO_PASSWORD),
        mascot_name="小光",
    )
    db.add(demo_user)
    db.flush()

    today = dt.date.today()
    week_start = today - dt.timedelta(days=today.weekday())

    # 一周课表：落在当前周的周一至周五
    for weekday, title, start, end, location in DEMO_COURSES:
        db.add(
            Schedule(
                user_id=demo_user.id,
                title=title,
                date=week_start + dt.timedelta(days=weekday),
                start_time=_parse_time(start),
                end_time=_parse_time(end),
                location=location,
                description="演示课表",
                category="general",
                source="manual",
            )
        )

    # 一门考试：10 天后，可在考试页生成复习计划
    db.add(
        Exam(
            user_id=demo_user.id,
            title="高等数学",
            subject="高等数学",
            exam_date=today + dt.timedelta(days=10),
            difficulty=4,
            location="教学楼 A101",
            notes="演示数据：可在考试页一键生成复习计划",
        )
    )

    # 一个跑步任务：目标本周 3 次、每次 30 分钟，可在任务页生成排期
    db.add(
        Task(
            user_id=demo_user.id,
            title="本周跑步",
            week_start=week_start,
            target_count=3,
            duration_min=30,
        )
    )

    db.commit()
    return True
