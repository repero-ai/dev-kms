"""HTTP API for the development-only KMS emulator."""

from __future__ import annotations

import base64
import logging
import os
import time
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from dev_kms import __version__
from dev_kms.crypto import (
    CiphertextError,
    generate_data_key,
    new_wrapping_key,
    unwrap_data_key,
)
from dev_kms.database import KeyAlreadyExistsError, KeyRecord, KeyStore

logger = logging.getLogger("dev_kms")


class CreateKeyRequest(BaseModel):
    key_id: Annotated[str, Field(min_length=1, max_length=255, pattern=r"^[A-Za-z0-9._-]+$")]


class CiphertextRequest(BaseModel):
    ciphertext: str = Field(description="Opaque base64 wrapped DEK returned by generate-data-key.")


class ApiError(Exception):
    def __init__(self, status_code: int, code: str) -> None:
        self.status_code = status_code
        self.code = code


def _metadata(key: KeyRecord) -> dict[str, str | int | bool]:
    return {
        "key_id": key.key_id,
        "version": key.key_version,
        "active": key.active,
        "created_at": key.created_at,
    }


def _error(status_code: int, code: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"error": {"code": code}})


def create_app(database_path: str | None = None, default_key_id: str | None = None) -> FastAPI:
    store = KeyStore(database_path or os.getenv("DEV_KMS_DATABASE_PATH", "/data/dev-kms.db"))
    default_key = (
        default_key_id
        if default_key_id is not None
        else os.getenv("DEV_KMS_DEFAULT_KEY_ID", "dev-key")
    )

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        store.initialize()
        if default_key and not store.get(default_key):
            store.create(default_key, new_wrapping_key())
            logger.info("created default key key_id=%s", default_key)
        yield

    app = FastAPI(
        title="dev-kms",
        version=__version__,
        description="Development-only KMS emulator. Never use with real secrets or in production.",
        lifespan=lifespan,
    )
    app.state.store = store

    @app.middleware("http")
    async def request_log(request: Request, call_next):
        started = time.monotonic()
        response = await call_next(request)
        logger.info(
            "request method=%s endpoint=%s status=%s duration_ms=%d",
            request.method,
            request.url.path,
            response.status_code,
            (time.monotonic() - started) * 1000,
        )
        return response

    @app.exception_handler(ApiError)
    async def api_error(_: Request, error: ApiError):
        return _error(error.status_code, error.code)

    @app.exception_handler(KeyAlreadyExistsError)
    async def duplicate_key(_: Request, __: KeyAlreadyExistsError):
        return _error(409, "key_already_exists")

    @app.exception_handler(CiphertextError)
    async def bad_ciphertext(_: Request, error: CiphertextError):
        return _error(400, error.code)

    @app.exception_handler(Exception)
    async def internal_error(request: Request, error: Exception):
        logger.exception("internal error endpoint=%s", request.url.path)
        return _error(500, "internal_error")

    @app.get("/health", summary="Health check")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/version", summary="Service version")
    async def version() -> dict[str, str]:
        return {"version": __version__}

    @app.post("/v1/keys", status_code=201, summary="Create a wrapping key")
    async def create_key(payload: CreateKeyRequest) -> dict[str, str | int | bool]:
        return _metadata(store.create(payload.key_id, new_wrapping_key()))

    @app.get("/v1/keys", summary="List non-sensitive key metadata")
    async def list_keys() -> list[dict[str, str | int | bool]]:
        return [_metadata(key) for key in store.list()]

    @app.post(
        "/v1/keys/{key_id}/generate-data-key", summary="Generate a temporary AES-256 data key"
    )
    async def generate(key_id: str) -> dict[str, str | int]:
        key = _require_key(store, key_id)
        plaintext, ciphertext = generate_data_key(key.wrapping_key, key.key_id, key.key_version)
        return {
            "key_id": key.key_id,
            "key_version": key.key_version,
            "plaintext": base64.b64encode(plaintext).decode("ascii"),
            "ciphertext": ciphertext,
        }

    @app.post("/v1/keys/{key_id}/decrypt", summary="Decrypt or unwrap an opaque data key")
    async def decrypt(key_id: str, payload: CiphertextRequest) -> dict[str, str]:
        key = _require_key(store, key_id)
        plaintext = unwrap_data_key(
            key.wrapping_key, key.key_id, key.key_version, payload.ciphertext
        )
        return {"plaintext": base64.b64encode(plaintext).decode("ascii")}

    return app


def _require_key(store: KeyStore, key_id: str) -> KeyRecord:
    key = store.get(key_id)
    if not key:
        raise ApiError(404, "key_not_found")
    return key


app = create_app()
