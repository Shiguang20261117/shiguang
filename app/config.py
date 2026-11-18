"""应用配置。

所有配置都可以通过环境变量覆盖，未设置时使用适合本地开发的默认值。
"""
import os
from pathlib import Path

# 项目根目录（shiguang-backend/），用于把 SQLite 文件固定放在项目根目录，
# 避免从不同工作目录启动 uvicorn 时生成不同的数据库文件。
BASE_DIR = Path(__file__).resolve().parent.parent


def _normalize_database_url(url: str) -> str:
    """统一 PostgreSQL 连接串格式。

    Vercel / Supabase 等平台下发的连接串常以 ``postgres://`` 或
    ``postgresql://`` 开头，SQLAlchemy 无法识别前者，且默认驱动为 psycopg2；
    这里统一改写为 ``postgresql+psycopg://``，由 requirements 中的
    psycopg（v3）驱动连接。
    """
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    return url


class Settings:
    # 默认使用项目根目录下的 shiguang.db；生产环境通过 DATABASE_URL 指向 PostgreSQL
    DATABASE_URL: str = _normalize_database_url(
        os.getenv(
            "DATABASE_URL", f"sqlite:///{(BASE_DIR / 'shiguang.db').as_posix()}"
        )
    )
    # 生产环境务必通过环境变量 SECRET_KEY 覆盖
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-only-secret-key-please-change-me")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    # 默认 7 天，移动端场景下免频繁登录
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "10080")
    )


settings = Settings()
