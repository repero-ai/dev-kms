from __future__ import annotations

import asyncio
import base64
import json
import sqlite3

import httpx

from dev_kms.main import create_app


class ApiClient:
    def __init__(self, database: str) -> None:
        self.app = create_app(database, default_key_id="")
        self.app.state.store.initialize()

    def get(self, path: str) -> httpx.Response:
        return asyncio.run(self._request("GET", path))

    def post(self, path: str, json: dict | None = None) -> httpx.Response:
        return asyncio.run(self._request("POST", path, json))

    async def _request(self, method: str, path: str, json: dict | None = None) -> httpx.Response:
        transport = httpx.ASGITransport(app=self.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path, json=json)


def client_for(tmp_path) -> ApiClient:
    app = create_app(str(tmp_path / "dev-kms.db"), default_key_id="")
    app.state.store.initialize()
    return ApiClient(str(tmp_path / "dev-kms.db"))


def create(client: ApiClient, key_id: str = "dev-key") -> dict:
    response = client.post("/v1/keys", json={"key_id": key_id})
    assert response.status_code == 201
    return response.json()


def generate(client: ApiClient, key_id: str = "dev-key") -> dict:
    response = client.post(f"/v1/keys/{key_id}/generate-data-key")
    assert response.status_code == 200
    return response.json()


def test_health_and_create_duplicate_and_list_keys(tmp_path) -> None:
    client = client_for(tmp_path)
    assert client.get("/health").json() == {"status": "ok"}
    created = create(client)
    assert created["key_id"] == "dev-key"
    assert created["version"] == 1
    assert "wrapping_key" not in created
    duplicate = client.post("/v1/keys", json={"key_id": "dev-key"})
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "key_already_exists"
    assert client.get("/v1/keys").json() == [created]


def test_api_round_trip_and_two_keys_differ(tmp_path) -> None:
    client = client_for(tmp_path)
    create(client)
    first = generate(client)
    second = generate(client)
    assert first["plaintext"] != second["plaintext"]
    assert first["ciphertext"] != second["ciphertext"]
    decrypted = client.post("/v1/keys/dev-key/decrypt", json={"ciphertext": first["ciphertext"]})
    assert decrypted.status_code == 200
    assert decrypted.json()["plaintext"] == first["plaintext"]


def test_ciphertext_errors(tmp_path) -> None:
    client = client_for(tmp_path)
    create(client, "first")
    create(client, "second")
    generated = generate(client, "first")

    wrong_key = client.post("/v1/keys/second/decrypt", json={"ciphertext": generated["ciphertext"]})
    assert wrong_key.status_code == 400
    assert wrong_key.json()["error"]["code"] == "key_mismatch"

    malformed = client.post("/v1/keys/first/decrypt", json={"ciphertext": "not base64!"})
    assert malformed.status_code == 400
    assert malformed.json()["error"]["code"] == "invalid_ciphertext"

    payload = json.loads(base64.b64decode(generated["ciphertext"]))
    payload["v"] = 999
    unsupported = base64.b64encode(json.dumps(payload).encode()).decode()
    response = client.post("/v1/keys/first/decrypt", json={"ciphertext": unsupported})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "unsupported_format"

    payload = json.loads(base64.b64decode(generated["ciphertext"]))
    payload["c"] = base64.b64encode(b"tampered ciphertext").decode()
    tampered = base64.b64encode(json.dumps(payload).encode()).decode()
    response = client.post("/v1/keys/first/decrypt", json={"ciphertext": tampered})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_ciphertext"


def test_missing_key_is_a_clean_error(tmp_path) -> None:
    client = client_for(tmp_path)
    response = client.post("/v1/keys/nope/generate-data-key")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "key_not_found"


def test_restart_preserves_decrypt_and_no_plaintext_is_persisted(tmp_path) -> None:
    database = tmp_path / "dev-kms.db"
    client = ApiClient(str(database))
    create(client)
    generated = generate(client)

    plaintext = base64.b64decode(generated["plaintext"])
    assert plaintext not in database.read_bytes()

    client = ApiClient(str(database))
    response = client.post("/v1/keys/dev-key/decrypt", json={"ciphertext": generated["ciphertext"]})
    assert response.status_code == 200
    assert response.json()["plaintext"] == generated["plaintext"]

    with sqlite3.connect(database) as connection:
        columns = {row[1] for row in connection.execute("PRAGMA table_info(keys)")}
    assert "plaintext" not in columns
