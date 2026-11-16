"""数据库 ORM 模型。

约定 / 假设（需求未明确的部分）：
- weekday 统一使用 Python ``date.weekday()`` 的约定：0=周一 ... 6=周日。
  前端 JavaScript 的 ``getDay()`` 是 0=周日，接入时需自行转换。
- 时间字段均为不带时区的本地时间（SQLite 中存 TIME / DATETIME）。
- 所有业务表都通过 ``user_id`` 归属到用户，路由层按当前登录用户隔离数据。
- schedules.status：pending / done / cancelled，默认 pending。
- tasks.status：pending / scheduled，创建时为 pending，生成排期后为 scheduled。
- task_slots.status：scheduled / done / missed，默认 scheduled。
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    email: Mapped[str | None] = mapped_column(String(120), unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )


class Routine(Base):
    """作息模板（每天/每周固定时间段的习惯）。"""

    __tablename__ = "routines"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=周一
    start_time: Mapped[dt.time] = mapped_column(Time, nullable=False)
    end_time: Mapped[dt.time] = mapped_column(Time, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ScheduleSeries(Base):
    """周期日程系列：记录批量生成的规则，便于整体查询/删除。"""

    __tablename__ = "schedule_series"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=周一
    start_time: Mapped[dt.time] = mapped_column(Time, nullable=False)
    end_time: Mapped[dt.time] = mapped_column(Time, nullable=False)
    start_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    end_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    schedules: Mapped[list[Schedule]] = relationship(
        back_populates="series", cascade="all, delete-orphan"
    )


class Schedule(Base):
    """单条日程（某一天的具体安排）。"""

    __tablename__ = "schedules"
    __table_args__ = (
        Index("ix_schedules_user_date", "user_id", "date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    series_id: Mapped[int | None] = mapped_column(
        ForeignKey("schedule_series.id", ondelete="SET NULL"), index=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    date: Mapped[dt.date] = mapped_column("date", Date, nullable=False)
    start_time: Mapped[dt.time] = mapped_column(Time, nullable=False)
    end_time: Mapped[dt.time] = mapped_column(Time, nullable=False)
    location: Mapped[str | None] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)
    # 日程分类：general（普通）/ study（复习计划）等
    category: Mapped[str] = mapped_column(
        String(20), default="general", server_default="general", nullable=False
    )
    # 来源：manual（手动创建）/ template（系统模板生成）
    source: Mapped[str] = mapped_column(
        String(20), default="manual", server_default="manual", nullable=False
    )
    # 复习计划关联的考试，用于重新生成时精确清理旧日程
    exam_id: Mapped[int | None] = mapped_column(
        ForeignKey("exams.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    series: Mapped[ScheduleSeries | None] = relationship(back_populates="schedules")


class Exam(Base):
    __tablename__ = "exams"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    subject: Mapped[str | None] = mapped_column(String(100))
    exam_date: Mapped[dt.date] = mapped_column(Date, nullable=False)
    # 难度 1-5 星，决定复习计划的提前天数与每日时长
    difficulty: Mapped[int] = mapped_column(
        Integer, default=3, server_default="3", nullable=False
    )
    start_time: Mapped[dt.time | None] = mapped_column(Time)
    end_time: Mapped[dt.time | None] = mapped_column(Time)
    location: Mapped[str | None] = mapped_column(String(200))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )


class PeriodicRule(Base):
    """周期性规则（为后续自动生成日程预留的规则表）。"""

    __tablename__ = "periodic_rules"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    # daily / weekly / monthly
    rule_type: Mapped[str] = mapped_column(String(20), default="weekly", nullable=False)
    interval: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    weekday: Mapped[int | None] = mapped_column(Integer)  # 仅 weekly 使用，0=周一
    day_of_month: Mapped[int | None] = mapped_column(Integer)  # 仅 monthly 使用
    start_time: Mapped[dt.time] = mapped_column(Time, nullable=False)
    end_time: Mapped[dt.time] = mapped_column(Time, nullable=False)
    start_date: Mapped[dt.date | None] = mapped_column(Date)
    end_date: Mapped[dt.date | None] = mapped_column(Date)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )


class Task(Base):
    """周期性任务目标，例如「本周跑步 4 次，每次 40 分钟」。"""

    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    # 目标周的周一日期
    week_start: Mapped[dt.date] = mapped_column(Date, nullable=False)
    target_count: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_min: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), default="pending", server_default="pending", nullable=False
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )

    slots: Mapped[list[TaskSlot]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="TaskSlot.date, TaskSlot.start_time",
    )


class TaskSlot(Base):
    """任务被拆分到具体时间段的执行槽位。"""

    __tablename__ = "task_slots"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int] = mapped_column(
        ForeignKey("tasks.id", ondelete="CASCADE"), index=True, nullable=False
    )
    date: Mapped[dt.date] = mapped_column("date", Date, nullable=False)
    start_time: Mapped[dt.time] = mapped_column(Time, nullable=False)
    end_time: Mapped[dt.time] = mapped_column(Time, nullable=False)
    # scheduled / done / missed
    status: Mapped[str] = mapped_column(
        String(20), default="scheduled", server_default="scheduled", nullable=False
    )
    # 同步写入 schedules 后回填，用于从槽位跳到周视图日程
    schedule_id: Mapped[int | None] = mapped_column(
        ForeignKey("schedules.id", ondelete="SET NULL"), index=True
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )

    task: Mapped[Task] = relationship(back_populates="slots")


class Checkin(Base):
    """打卡记录：target_type 为 schedule（单条日程）或 periodic（固定日常）。"""

    __tablename__ = "checkins"
    __table_args__ = (
        # 同一用户、同一目标、同一天只能打卡一次
        UniqueConstraint(
            "user_id", "target_type", "target_id", "date",
            name="uq_checkins_user_target_date",
        ),
        Index("ix_checkins_user_date", "user_id", "date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    # schedule: target_id 指向 schedules.id；periodic: 指向 routines.id
    target_type: Mapped[str] = mapped_column(String(20), nullable=False)
    target_id: Mapped[int] = mapped_column(Integer, nullable=False)
    date: Mapped[dt.date] = mapped_column("date", Date, nullable=False)
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )


class Notice(Base):
    """调课通知：保存粘贴的原始文本与解析结果，确认后才真正修改日程。

    status：pending（待确认）/ confirmed（已执行）/ discarded（已丢弃）。
    parsed_json 存放解析结果（action、匹配的日程 id、新时间等）。
    """

    __tablename__ = "notices"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False
    )
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    parsed_json: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(20), default="pending", server_default="pending", nullable=False
    )
    created_at: Mapped[dt.datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
