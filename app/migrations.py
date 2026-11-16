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

        # 旧版 tasks / task_slots 与任务排程模型不兼容（旧表无 week_start、
        # target_count、duration_min，槽位用 is_completed）。旧表无业务数据，直接重建。
        if "tasks" in tables:
            columns = {col["name"] for col in inspector.get_columns("tasks")}
            if "week_start" not in columns:
                conn.execute(text("DROP TABLE IF EXISTS task_slots"))
                conn.execute(text("DROP TABLE IF EXISTS tasks"))
                conn.execute(
                    text(
                        """
                        CREATE TABLE tasks (
                            id INTEGER NOT NULL,
                            user_id INTEGER NOT NULL,
                            title VARCHAR(200) NOT NULL,
                            week_start DATE NOT NULL,
                            target_count INTEGER NOT NULL,
                            duration_min INTEGER NOT NULL,
                            status VARCHAR(20) NOT NULL DEFAULT 'pending',
                            created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                            PRIMARY KEY (id),
                            FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
                        )
                        """
                    )
                )
                conn.execute(
                    text(
                        """
                        CREATE TABLE task_slots (
                            id INTEGER NOT NULL,
                            task_id INTEGER NOT NULL,
                            date DATE NOT NULL,
                            start_time TIME NOT NULL,
                            end_time TIME NOT NULL,
                            status VARCHAR(20) NOT NULL DEFAULT 'scheduled',
                            schedule_id INTEGER,
                            created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                            PRIMARY KEY (id),
                            FOREIGN KEY(task_id) REFERENCES tasks (id) ON DELETE CASCADE,
                            FOREIGN KEY(schedule_id) REFERENCES schedules (id)
                                ON DELETE SET NULL
                        )
                        """
                    )
                )
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_tasks_user_id ON tasks (user_id)"
                    )
                )
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_task_slots_task_id "
                        "ON task_slots (task_id)"
                    )
                )
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_task_slots_schedule_id "
                        "ON task_slots (schedule_id)"
                    )
                )

        if "task_slots" in tables:
            columns = {col["name"] for col in inspector.get_columns("task_slots")}
            if "status" not in columns:
                conn.execute(
                    text(
                        "ALTER TABLE task_slots ADD COLUMN status "
                        "VARCHAR(20) NOT NULL DEFAULT 'scheduled'"
                    )
                )
            if "schedule_id" not in columns:
                conn.execute(
                    text("ALTER TABLE task_slots ADD COLUMN schedule_id INTEGER")
                )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_task_slots_schedule_id "
                    "ON task_slots (schedule_id)"
                )
            )

        # 旧版 checkins（routine_id / task_id / checkin_date）与打卡模型不兼容，
        # 直接重建为 target_type + target_id + date，并建立唯一索引防重复打卡。
        if "checkins" in tables:
            columns = {col["name"] for col in inspector.get_columns("checkins")}
            if not {"target_type", "target_id", "date"} <= columns:
                conn.execute(text("DROP TABLE IF EXISTS checkins"))
                conn.execute(
                    text(
                        """
                        CREATE TABLE checkins (
                            id INTEGER NOT NULL,
                            user_id INTEGER NOT NULL,
                            target_type VARCHAR(20) NOT NULL,
                            target_id INTEGER NOT NULL,
                            date DATE NOT NULL,
                            created_at DATETIME DEFAULT CURRENT_TIMESTAMP NOT NULL,
                            PRIMARY KEY (id),
                            CONSTRAINT uq_checkins_user_target_date
                                UNIQUE (user_id, target_type, target_id, date),
                            FOREIGN KEY(user_id) REFERENCES users (id) ON DELETE CASCADE
                        )
                        """
                    )
                )
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_checkins_user_id "
                        "ON checkins (user_id)"
                    )
                )
                conn.execute(
                    text(
                        "CREATE INDEX IF NOT EXISTS ix_checkins_user_date "
                        "ON checkins (user_id, date)"
                    )
                )
