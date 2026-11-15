"""轻量级数据库迁移：为已存在的 SQLite 库补齐新增字段。

项目尚未引入 Alembic 版本目录，启动时由 ``run_migrations`` 保证旧库结构
与新模型一致；全新的库已由 ``Base.metadata.create_all`` 按模型建表，
这里的每一步都做了存在性判断，可重复执行。
"""
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine


def run_migrations(engine: Engine) -> None:
    if engine.dialect.name != "sqlite":
        return

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    with engine.begin() as conn:
        if "schedules" in tables:
            columns = {col["name"] for col in inspector.get_columns("schedules")}
            if "category" not in columns:
                conn.execute(
                    text(
                        "ALTER TABLE schedules ADD COLUMN category "
                        "VARCHAR(20) NOT NULL DEFAULT 'general'"
                    )
                )
            if "source" not in columns:
                conn.execute(
                    text(
                        "ALTER TABLE schedules ADD COLUMN source "
                        "VARCHAR(20) NOT NULL DEFAULT 'manual'"
                    )
                )
            if "exam_id" not in columns:
                conn.execute(text("ALTER TABLE schedules ADD COLUMN exam_id INTEGER"))
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_schedules_exam_id "
                    "ON schedules (exam_id)"
                )
            )

        if "exams" in tables:
            columns = {col["name"] for col in inspector.get_columns("exams")}
            if "difficulty" not in columns:
                conn.execute(
                    text(
                        "ALTER TABLE exams ADD COLUMN difficulty "
                        "INTEGER NOT NULL DEFAULT 3"
                    )
                )
