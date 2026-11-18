"""FastAPI 应用入口。

启动方式（在项目根目录执行）：
    pip install -r requirements.txt
    uvicorn app.main:app --reload

接口文档：http://127.0.0.1:8000/docs
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from . import models  # noqa: F401  确保所有模型注册到 Base.metadata
from .database import Base, SessionLocal, engine
from .migrations import run_migrations
from .seed import DEMO_PASSWORD, DEMO_USERNAME, seed_demo_data
from .routers import (
    auth,
    checkins,
    exams,
    export,
    free_blocks,
    imports,
    mascot,
    notices,
    routines,
    schedules,
    series,
    tasks,
)


def init_db() -> None:
    """建表、补齐旧库结构、空库注入演示数据（幂等）。"""
    # 使用 create_all 初始化建表；如需版本化迁移，可在此基础上接入 Alembic
    Base.metadata.create_all(bind=engine)
    # 兼容已存在的旧库：幂等补齐新增字段
    run_migrations(engine)
    # 用户表为空时写入演示账号与示例数据
    with SessionLocal() as db:
        if seed_demo_data(db):
            print(
                f"[seed] 已创建演示账号 {DEMO_USERNAME} / {DEMO_PASSWORD} "
                "并注入示例数据"
            )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="拾光 · 后端 API",
    description="基于 FastAPI + SQLAlchemy + SQLite 的日程 / 作息管理后端",
    version="1.0.0",
    lifespan=lifespan,
)

# 移动端 / 本地调试场景默认放开跨域；生产环境请按需收紧 allow_origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(routines.router)
app.include_router(schedules.router)
app.include_router(series.router)
app.include_router(free_blocks.router)
app.include_router(exams.router)
app.include_router(tasks.router)
app.include_router(checkins.router)
app.include_router(mascot.router)
app.include_router(export.router)
app.include_router(imports.router)
app.include_router(notices.router)


@app.get("/health", tags=["系统"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/keepalive", tags=["系统"])
def keepalive() -> dict[str, str]:
    """数据库保活：执行 SELECT 1 唤醒数据库，并由定时任务定期访问。"""
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    return {"status": "alive"}


if __name__ == "__main__":
    # 也可以直接 python -m app.main 启动
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
