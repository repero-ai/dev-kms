FROM python:3.13-slim AS builder

WORKDIR /build
COPY pyproject.toml README.md LICENSE ./
COPY dev_kms ./dev_kms
RUN python -m pip wheel --no-cache-dir --wheel-dir /wheels .

FROM python:3.13-slim

LABEL org.opencontainers.image.source="https://github.com/smncjl-labs/dev-kms" \
      org.opencontainers.image.licenses="Apache-2.0" \
      org.opencontainers.image.description="Development-only disposable KMS emulator"

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DEV_KMS_DATABASE_PATH=/data/dev-kms.db

RUN groupadd --system devkms && useradd --system --gid devkms --home-dir /nonexistent devkms \
    && mkdir /data && chown devkms:devkms /data

COPY --from=builder /wheels /wheels
RUN python -m pip install --no-cache-dir /wheels/*.whl && rm -rf /wheels

USER devkms
EXPOSE 8080
VOLUME ["/data"]
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health')" || exit 1

CMD ["uvicorn", "dev_kms.main:app", "--host", "0.0.0.0", "--port", "8080"]
