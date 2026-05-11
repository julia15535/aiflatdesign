# syntax=docker/dockerfile:1.7

# ---------- Builder: ставим зависимости в /opt/venv ----------
FROM python:3.11-slim AS builder

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# uv (быстрый менеджер пакетов)
COPY --from=ghcr.io/astral-sh/uv:0.5.4 /uv /uvx /usr/local/bin/

# Копируем весь проект (нужно для setuptools build backend)
COPY pyproject.toml ./
COPY bot.py db.py states.py handlers.py ./
COPY ai/ ./ai/
COPY utils/ ./utils/

# Создаём виртуальное окружение и ставим проект+зависимости
RUN uv venv /opt/venv --python 3.11 && \
    VIRTUAL_ENV=/opt/venv uv pip install --no-cache .

# ---------- Runtime: тонкий образ с venv + кодом ----------
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH" \
    DATA_DIR=/app/data

WORKDIR /app

# Системные библиотеки для opencv-python-headless
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# venv из builder'а
COPY --from=builder /opt/venv /opt/venv

# Код приложения
COPY bot.py db.py states.py handlers.py ./
COPY ai/ ./ai/
COPY utils/ ./utils/

# Non-root user + папка для БД
RUN useradd -m -u 1000 botuser && \
    mkdir -p /app/data && \
    chown -R botuser:botuser /app

USER botuser

CMD ["python", "bot.py"]
