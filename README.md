# dev-kms

> **Warning:** dev-kms is a disposable KMS emulator for local development and integration testing. It is not a production KMS and must not be used to protect real secrets or sensitive data.

`dev-kms` implements only the envelope-encryption primitives applications need: generate a 256-bit data-encryption key (DEK), then decrypt/unwrap it later. It is intended for local development, CI, integration tests, and other disposable environments.

It is **not** a production KMS. It provides no HSM, hardware-backed key protection, authentication, authorization, TLS, tenant isolation, secret storage, or arbitrary encrypt/decrypt API. Do not expose it to the public Internet.

## Quick start

```bash
docker compose up
curl http://localhost:8090/health
```

Compose creates the default `dev-key` automatically and publishes only on loopback (`127.0.0.1:8090`). The service uses HTTP because it is intended for local Docker networks only; production KMS implementations **must** use authenticated TLS.

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

Plaintext DEKs are never stored. To deliberately discard all local keys and data:

```bash
docker compose down -v
```

## Integration example

```yaml
services:
  dev-kms:
    image: ghcr.io/smncjl-labs/dev-kms:latest
    environment:
      DEV_KMS_DEFAULT_KEY_ID: dev-key

  application:
    environment:
      KMS_ENDPOINT: http://dev-kms:8080
      KMS_KEY_ID: dev-key
```

For a stable image, pin a version:

```bash
docker pull ghcr.io/smncjl-labs/dev-kms:1.0.0
```

Use `:latest` for the most recent stable release, or `:edge` to follow `main` development.

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
