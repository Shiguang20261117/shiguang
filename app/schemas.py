"""Pydantic 请求 / 响应模型。"""
from __future__ import annotations

import datetime as dt
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


def _validate_time_range(start: dt.time | None, end: dt.time | None) -> None:
    if start is not None and end is not None and start >= end:
        raise ValueError("结束时间必须晚于开始时间")


# --------------------------------------------------------------------------
# 认证 / 用户
# --------------------------------------------------------------------------
class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    password: str = Field(min_length=6, max_length=128)
    # 需求未要求邮箱，设为可选；填写时做最简格式校验
    email: str | None = Field(
        default=None,
        max_length=120,
        pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$",
    )


class UserRead(ORMModel):
    id: int
    username: str
    email: str | None
    is_active: bool
    created_at: dt.datetime


class LoginRequest(BaseModel):
    username: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


# --------------------------------------------------------------------------
# 作息模板 routines
# --------------------------------------------------------------------------
class RoutineBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    weekday: int = Field(ge=0, le=6, description="0=周一 ... 6=周日")
    start_time: dt.time
    end_time: dt.time
    is_active: bool = True

    @model_validator(mode="after")
    def _check_range(self) -> "RoutineBase":
        _validate_time_range(self.start_time, self.end_time)
        return self


class RoutineCreate(RoutineBase):
    pass


class RoutineUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    weekday: int | None = Field(default=None, ge=0, le=6)
    start_time: dt.time | None = None
    end_time: dt.time | None = None
    is_active: bool | None = None

    @model_validator(mode="after")
    def _check_range(self) -> "RoutineUpdate":
        _validate_time_range(self.start_time, self.end_time)
        return self


class RoutineRead(ORMModel):
    id: int
    title: str
    description: str | None
    weekday: int
    start_time: dt.time
    end_time: dt.time
    is_active: bool
    created_at: dt.datetime
    updated_at: dt.datetime


# --------------------------------------------------------------------------
# 日程 schedules
# --------------------------------------------------------------------------
class ScheduleBase(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    date: dt.date
    start_time: dt.time
    end_time: dt.time
    location: str | None = Field(default=None, max_length=200)
    status: str = Field(default="pending", max_length=20)

    @model_validator(mode="after")
    def _check_range(self) -> "ScheduleBase":
        _validate_time_range(self.start_time, self.end_time)
        return self


class ScheduleCreate(ScheduleBase):
    # 关联到某个周期系列；普通单条日程传 None
    series_id: int | None = None


class ScheduleUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    date: dt.date | None = None
    start_time: dt.time | None = None
    end_time: dt.time | None = None
    location: str | None = Field(default=None, max_length=200)
    status: str | None = Field(default=None, max_length=20)
    series_id: int | None = None

    @model_validator(mode="after")
    def _check_range(self) -> "ScheduleUpdate":
        _validate_time_range(self.start_time, self.end_time)
        return self


class ScheduleRead(ORMModel):
    id: int
    series_id: int | None
    title: str
    description: str | None
    date: dt.date
    start_time: dt.time
    end_time: dt.time
    location: str | None
    status: str
    category: str
    source: str
    exam_id: int | None
    created_at: dt.datetime
    updated_at: dt.datetime


# --------------------------------------------------------------------------
# 任务排程 tasks / task_slots
# --------------------------------------------------------------------------
class TaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    week_start: dt.date = Field(description="目标周的周一日期")
    target_count: int = Field(ge=1, description="目标次数")
    duration_min: int = Field(ge=1, le=1440, description="每次时长（分钟）")

    @model_validator(mode="after")
    def _check_week_start(self) -> "TaskCreate":
        if self.week_start.weekday() != 0:
            raise ValueError("week_start 必须是周一")
        return self


class TaskSlotRead(ORMModel):
    id: int
    date: dt.date
    start_time: dt.time
    end_time: dt.time
    status: str
    schedule_id: int | None


class TaskRead(ORMModel):
    id: int
    title: str
    week_start: dt.date
    target_count: int
    duration_min: int
    status: str
    created_at: dt.datetime
    updated_at: dt.datetime
    slots: list[TaskSlotRead] = []


class TaskScheduleResult(BaseModel):
    scheduled_count: int
    shortage: int
    slots: list[TaskSlotRead]


# --------------------------------------------------------------------------
# 打卡 checkins
# --------------------------------------------------------------------------
class CheckinCreate(BaseModel):
    # schedule: 单条日程；periodic: 固定日常
    target_type: Literal["schedule", "periodic"]
    target_id: int


class CheckinRead(ORMModel):
    id: int
    target_type: str
    target_id: int
    date: dt.date
    created_at: dt.datetime


class CheckinStats(BaseModel):
    days: int
    # 近 N 天打卡数
    total: int
    # 连续打卡天数
    streak_days: int
    # 近 N 天应完成日程的打卡比例（0-100）
    completion_rate: float
    # happy / normal / sad
    mascot: Literal["happy", "normal", "sad"]


# --------------------------------------------------------------------------
# 考试 exams
# --------------------------------------------------------------------------
class ExamCreate(BaseModel):
    subject: str = Field(min_length=1, max_length=100)
    exam_date: dt.date
    difficulty: int = Field(default=3, ge=1, le=5, description="难度 1-5 星")


class ExamRead(ORMModel):
    id: int
    subject: str
    exam_date: dt.date
    difficulty: int
    created_at: dt.datetime
    # 是否已经生成过复习计划（存在 source=template 的复习日程）
    has_plan: bool = False


class StudyPlanRead(BaseModel):
    """复习计划生成结果。"""

    created: list[ScheduleRead]
    skipped_days: list[dt.date]


# --------------------------------------------------------------------------
# 周期系列 schedule_series
# --------------------------------------------------------------------------
class SeriesCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    weekday: int = Field(ge=0, le=6, description="0=周一 ... 6=周日")
    start_time: dt.time
    end_time: dt.time
    start_date: dt.date
    end_date: dt.date

    @model_validator(mode="after")
    def _check_ranges(self) -> "SeriesCreate":
        _validate_time_range(self.start_time, self.end_time)
        if self.end_date < self.start_date:
            raise ValueError("end_date 不能早于 start_date")
        return self


class SeriesRead(ORMModel):
    id: int
    title: str
    weekday: int
    start_time: dt.time
    end_time: dt.time
    start_date: dt.date
    end_date: dt.date
    created_at: dt.datetime
    # 该系列实际生成的日程数量
    schedule_count: int = 0


class SeriesUpdate(BaseModel):
    """整体修改周期系列。

    series 表只存 title / start_time / end_time，地点和备注会同步写入该系列的所有日程。
    """

    title: str | None = Field(default=None, min_length=1, max_length=200)
    start_time: dt.time | None = None
    end_time: dt.time | None = None
    location: str | None = Field(default=None, max_length=200)
    description: str | None = None

    @model_validator(mode="after")
    def _check_range(self) -> "SeriesUpdate":
        _validate_time_range(self.start_time, self.end_time)
        return self


class SeriesCreateResult(BaseModel):
    series: SeriesRead
    created_count: int


# --------------------------------------------------------------------------
# 课表文本导入
# --------------------------------------------------------------------------
class TimetableImportRequest(BaseModel):
    text: str = Field(min_length=1, max_length=50000)


class TimetableImportError(BaseModel):
    # 原始文本中的行号，从 1 开始
    line: int
    content: str
    reason: str


class TimetableImportResult(BaseModel):
    created: int
    errors: list[TimetableImportError] = []


def apply_updates(obj: Any, data: dict[str, Any]) -> None:
    """把 exclude_unset 的更新字典写入 ORM 对象。"""
    for field, value in data.items():
        setattr(obj, field, value)
