FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PACKET_PATH=/reference/okafor_lindqvist_2025_packet.json

WORKDIR /app

COPY backend/requirements.txt backend/requirements-dev.txt ./
RUN pip install -r requirements.txt -r requirements-dev.txt

COPY backend/ .
COPY reference/okafor_lindqvist_2025_packet.json /reference/okafor_lindqvist_2025_packet.json

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && python -m app.cli import-packet && uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
