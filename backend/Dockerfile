# ============================================================
# Backend 镜像：FastAPI + SQLAlchemy + Alembic
# 容器内监听 8000 端口，对应宿主机的 backend 服务。
# ============================================================

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

# 使用 uv 安装和锁定 Python 依赖。
COPY --from=ghcr.io/astral-sh/uv:0.11.24 /uv /uvx /bin/

WORKDIR /app

# 先复制依赖清单，利用 Docker layer cache 加速后续构建。
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# 复制后端源代码和迁移配置。
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini main.py ./

EXPOSE 8000

# 容器启动时先执行数据库迁移，再启动 FastAPI。
CMD ["sh", "-c", "alembic upgrade head && exec uvicorn app.main:app --host 0.0.0.0 --port 8000"]

