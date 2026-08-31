# Security policy

dev-kms is deliberately a development-only, disposable KMS emulator. It is **not intended for production** and must never be trusted with real secrets or sensitive data.

It has no HSM, no hardware-backed key protection, no TLS, no authentication or authorization, and no guarantee against host compromise. Its root/wrapping keys are stored locally in SQLite by design so local containers can survive restarts. Anyone able to read the database or control the host can compromise those keys and the wrapped DEKs.

Use only synthetic, disposable data. Do not expose dev-kms to the public Internet. Production KMS implementations must use authenticated TLS and appropriate key-management controls.

Security reports about accidental exposure, unsafe defaults, or a deviation from this documented scope can be opened as a private GitHub security advisory where available. Do not report a lack of production-grade protection as a vulnerability: that limitation is intentional and documented.

