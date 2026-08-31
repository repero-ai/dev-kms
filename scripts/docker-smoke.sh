#!/usr/bin/env bash
set -euo pipefail

image="dev-kms:smoke"
container=""
cleanup() {
  if [[ -n "$container" ]]; then
    docker rm -f "$container" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

docker build -t "$image" .
container=$(docker run -d -p 127.0.0.1::8080 "$image")
port=$(docker port "$container" 8080/tcp | sed -n 's/.*:\([0-9]*\)$/\1/p')

for _ in $(seq 1 30); do
  if curl --fail --silent "http://127.0.0.1:$port/health" >/dev/null; then
    break
  fi
  sleep 1
done
curl --fail --silent "http://127.0.0.1:$port/health" >/dev/null

generated=$(curl --fail --silent -X POST "http://127.0.0.1:$port/v1/keys/dev-key/generate-data-key")
ciphertext=$(printf '%s' "$generated" | python3 -c 'import json,sys; print(json.load(sys.stdin)["ciphertext"])')
plaintext=$(printf '%s' "$generated" | python3 -c 'import json,sys; print(json.load(sys.stdin)["plaintext"])')
unwrapped=$(curl --fail --silent -X POST "http://127.0.0.1:$port/v1/keys/dev-key/decrypt" \
  -H 'Content-Type: application/json' \
  -d "{\"ciphertext\":\"$ciphertext\"}" | python3 -c 'import json,sys; print(json.load(sys.stdin)["plaintext"])')

[[ "$plaintext" == "$unwrapped" ]]
echo "Docker smoke test passed."
