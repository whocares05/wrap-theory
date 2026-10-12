FROM python:3.12-slim AS builder
ENV PIP_DISABLE_PIP_VERSION_CHECK=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY pyproject.toml ./
COPY app ./app
RUN python -m pip install --prefix=/install .

FROM python:3.12-slim AS runtime
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
RUN addgroup --system app && adduser --system --ingroup app app
COPY --from=builder /install /usr/local
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./
USER app
EXPOSE 4000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "4000", "--proxy-headers", "--forwarded-allow-ips", "*"]
