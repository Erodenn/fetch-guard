FROM python:3.12-slim AS builder
WORKDIR /app
COPY pyproject.toml README.md ./
COPY fetch_guard/ ./fetch_guard/
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.12-slim
WORKDIR /app
COPY --from=builder /install /usr/local
COPY --from=builder /app/fetch_guard ./fetch_guard/

RUN useradd --no-create-home --shell /bin/false appuser
USER appuser

CMD ["python", "-m", "fetch_guard.server"]
