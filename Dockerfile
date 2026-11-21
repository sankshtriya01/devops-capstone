# ---- Stage 1: install dependencies ----
FROM python:3.13-slim AS builder
WORKDIR /build
COPY app/requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# ---- Stage 2: small final image ----
FROM python:3.13-slim
ARG APP_VERSION=1.0.0
ENV APP_VERSION=${APP_VERSION} \
    PYTHONUNBUFFERED=1 \
    PORT=8080 \
    WEB_CONCURRENCY=2

# Run as a normal user, not root (security)
RUN useradd --create-home --uid 10001 appuser
WORKDIR /app
COPY --from=builder /install /usr/local
COPY app/main.py app/db.py ./
COPY app/templates ./templates
USER 10001

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health')" || exit 1

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "main:app"]
