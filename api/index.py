"""Vercel 无服务器函数入口：用 Mangum 把 FastAPI 应用包装成 ASGI handler。

Vercel 的 Python 运行时约定：``api/index.py`` 中名为 ``handler`` 的可调用对象
即函数处理入口。
"""
from mangum import Mangum

from app.main import app, init_db

# 无服务器环境下不使用 ASGI lifespan（Mangum 关闭后每次调用不会重复初始化），
# 改为在冷启动导入时执行一次建表 / 迁移 / 演示数据种子。
init_db()

handler = Mangum(app, lifespan="off")
