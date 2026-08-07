FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Noto CJK is installed as an OS font so generated reports can render Chinese
# without distributing a font binary inside the repository.
RUN apt-get update \
    && apt-get install -y --no-install-recommends fonts-wqy-zenhei \
    && rm -rf /var/lib/apt/lists/*

COPY backend/pyproject.toml ./

RUN mkdir -p app \
    && touch app/__init__.py \
    && pip install --upgrade pip \
    && pip install . \
    && rm -r app

COPY backend/alembic.ini ./
COPY backend/alembic ./alembic
COPY backend/app ./app

# Keep release/legal/acceptance artifacts in the distributable image. Runtime
# calculation data remains a read-only Compose mount so it can be version-audited.
COPY VERSION LICENSE THIRD_PARTY_NOTICES.md CHANGELOG.md docker-compose.yml /release/
COPY scripts /release/scripts

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
