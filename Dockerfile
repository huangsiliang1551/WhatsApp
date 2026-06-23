FROM python:3.14-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /workspace

# System deps first (stable layer, rarely changes)
RUN apt-get update && \
    apt-get install -y --no-install-recommends libpq5 unar && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /opt/whatsapp/static/templates /opt/whatsapp/uploads/templates

# Python deps second (changes only when pyproject.toml changes)
COPY pyproject.toml ./
RUN python -m pip install --upgrade pip && \
    python -m pip install .

# Business code last (changes frequently)
COPY alembic.ini ./
COPY alembic/ ./alembic/
COPY app/ ./app/

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
