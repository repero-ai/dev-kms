# dev-kms

> **Warning:** dev-kms is a disposable KMS emulator for local development and integration testing. It is not a production KMS and must not be used to protect real secrets or sensitive data.

`dev-kms` implements only the envelope-encryption primitives applications need: generate a 256-bit data-encryption key (DEK), then decrypt/unwrap it later. It is intended for local development, CI, integration tests, and other disposable environments.

It is **not** a production KMS. It provides no HSM, hardware-backed key protection, authentication, authorization, TLS, tenant isolation, secret storage, or arbitrary encrypt/decrypt API. Do not expose it to the public Internet.

## Quick start — use the published image

```bash
docker run --rm \
  -p 127.0.0.1:8090:8080 \
  -e DEV_KMS_DEFAULT_KEY_ID=dev-key \
  -v dev-kms-data:/data \
  ghcr.io/smncjl-labs/dev-kms:<version>

curl http://localhost:8090/health
```

Pin an explicit version for reproducible integrations. `latest` is the latest stable tagged release; `edge` is the latest build from `main` and is intended for development. The loopback mapping gives a developer direct host access without publicly exposing the service.

The service uses HTTP because it is intended for local Docker networks only; production KMS implementations **must** use authenticated TLS.

## Integrating into another Compose stack

For a consuming application, use the published image in that application's Compose stack:

```yaml
services:
  dev-kms:
    image: ghcr.io/smncjl-labs/dev-kms:<version>
    environment:
      DEV_KMS_DEFAULT_KEY_ID: dev-key
    volumes:
      - dev-kms-data:/data

  application:
    environment:
      KMS_ENDPOINT: http://dev-kms:8080
      KMS_KEY_ID: dev-key

volumes:
  dev-kms-data:
```

Containers on the same Compose network reach the service at `http://dev-kms:8080`. Publishing a host port is unnecessary unless a developer needs direct host access. This is the expected integration model for projects such as Billing Platform.

## Developing dev-kms itself

The repository-local Compose file is for developing or testing the current checkout:

```bash
git clone https://github.com/smncjl-labs/dev-kms.git
cd dev-kms
docker compose up --build
```

Its `compose.yml` intentionally uses `build: .` so contributors exercise the local source tree. Downstream consumers should pull the published GHCR image instead of building dev-kms themselves.

## API

FastAPI serves OpenAPI at `/docs` and `/openapi.json`.

```bash
curl -X POST http://localhost:8090/v1/keys \
  -H 'Content-Type: application/json' \
  -d '{"key_id":"test"}'

curl -X POST http://localhost:8090/v1/keys/test/generate-data-key

curl -X POST http://localhost:8090/v1/keys/test/decrypt \
  -H 'Content-Type: application/json' \
  -d '{"ciphertext":"<ciphertext from generate-data-key>"}'
```

`plaintext` is a base64-encoded, 32-byte AES-256 key. Use it immediately and do not persist it. `ciphertext` is an opaque, versioned base64 payload containing metadata and an AES-256-GCM wrapped DEK; callers must treat it as opaque.

## Envelope encryption flow

```text
application -> dev-kms: generate DEK -> plaintext DEK + wrapped DEK
application -> AES-256-GCM encrypts its own data with plaintext DEK
application -> persists encrypted data + wrapped DEK
application -> dev-kms: decrypt wrapped DEK -> plaintext DEK for decryption
```

Billing Platform is one intended use case, but dev-kms has no code dependency on it. In production, use a real KMS such as OVH KMS instead.

## Persistence and reset

Keys are stored in SQLite at `/data/dev-kms.db`; the database and schema are created at startup. In V1, the wrapping/root key is deliberately stored in that SQLite database. This lets local containers retain KMS-like semantics across restarts, but it does **not** protect the database from an attacker and is not a bootstrap-secret system.

Plaintext DEKs are never stored. To deliberately discard all local keys and data when using the repository Compose setup:

```bash
docker compose down -v
```

Removing the named volume used by the standalone command (`docker volume rm dev-kms-data`) also destroys all disposable KMS state.

## CI and images

Pull requests run Ruff, pytest, and a Docker build. Pushes to `main` publish `edge` and `sha-<shortsha>` to GHCR. Tags such as `v1.2.3` publish `1.2.3`, `1.2`, `1`, and `latest`, for `linux/amd64` and `linux/arm64`.

After the first GHCR publication, make the package public manually if needed:

```text
GitHub → Packages → dev-kms → Package settings → Change visibility → Public
```

## Security

Read [SECURITY.md](SECURITY.md) before using this project. It is intentionally unsafe for real data: no authentication, no TLS, no HSM, no host-compromise protection, and locally stored root keys.

## License

Licensed under the Apache License, Version 2.0. See [LICENSE](LICENSE).
