# Contributing

Thanks for contributing. Keep dev-kms intentionally small and development-only: additions should support generate-data-key or decrypt/unwrap semantics, not turn it into a production KMS.

Before opening a pull request, run:

```bash
ruff check .
ruff format --check .
pytest
docker build -t dev-kms:test .
./scripts/docker-smoke.sh
```

Never add real credentials, secrets, or production security claims to this repository.

