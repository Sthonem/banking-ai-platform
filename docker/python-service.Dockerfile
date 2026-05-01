FROM python:3.12-slim

ARG SERVICE_DIR
ARG REQUIREMENTS_FILE=requirements/base.txt
ARG APT_PACKAGES="curl"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app:/app/services/shared

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ${APT_PACKAGES} \
    && rm -rf /var/lib/apt/lists/*

COPY requirements/base.txt /app/requirements/base.txt
COPY requirements /app/requirements
RUN pip install --no-cache-dir -r /app/${REQUIREMENTS_FILE}

COPY services/shared /app/services/shared
COPY alembic.ini /app/alembic.ini
COPY migrations /app/migrations
COPY ${SERVICE_DIR} /app/${SERVICE_DIR}
COPY scripts /app/scripts

WORKDIR /app/${SERVICE_DIR}
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
