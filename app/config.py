"""应用配置。

所有配置都可以通过环境变量覆盖，未设置时使用适合本地开发的默认值。
"""
import os
from pathlib import Path

# 项目根目录（shiguang-backend/），用于把 SQLite 文件固定放在项目根目录，
# 避免从不同工作目录启动 uvicorn 时生成不同的数据库文件。
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings:
    # 默认使用项目根目录下的 shiguang.db
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", f"sqlite:///{(BASE_DIR / 'shiguang.db').as_posix()}"
    )
    # 生产环境务必通过环境变量 SECRET_KEY 覆盖
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-only-secret-key-please-change-me")
    JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
    # 默认 7 天，移动端场景下免频繁登录
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(
        os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "10080")
    )


settings = Settings()
