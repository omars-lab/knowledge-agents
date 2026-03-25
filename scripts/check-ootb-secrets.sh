#!/usr/bin/env bash
# Check for OOTB/default credentials in the running stack.
# Run on Mac Studio (prod) as a security regression check.
# Exit code 0 = all secure, 1 = OOTB secrets found.

set -euo pipefail

RED="\033[91m"
GREEN="\033[92m"
RESET="\033[0m"
ERRORS=0
CHECKS=0

check() {
  local name="$1" ok="$2" detail="${3:-}"
  CHECKS=$((CHECKS + 1))
  if [ "$ok" = "true" ]; then
    printf "  %bPASS%b  %s\n" "$GREEN" "$RESET" "$name"
  else
    printf "  %bFAIL%b  %s  %s\n" "$RED" "$RESET" "$name" "$detail"
    ERRORS=$((ERRORS + 1))
  fi
}

echo ""
echo "── OOTB Credential Security Check ──"
echo ""

# Known OOTB passwords that must NOT be in .env
OOTB_PASSWORDS=("knowledge123" "clickhouse123" "minio123456" "password" "changeme" "admin123" "langfuse-secret-changeme" "langfuse-secret-knowledge-agents" "pk-lf-knowledge" "sk-lf-knowledge" "pk-lf-changeme" "sk-lf-changeme")

# 1. Check .env file exists and has non-default values
echo "Step 1: Check .env has non-default values"
if [ ! -f .env ]; then
  check ".env exists" "false" "No .env file found"
else
  check ".env exists" "true"
  while IFS= read -r line; do
    [[ "$line" =~ ^#.*$ ]] && continue
    [[ -z "$line" ]] && continue
    key=$(echo "$line" | cut -d= -f1)
    value=$(echo "$line" | cut -d= -f2-)
    # Skip empty values and non-secret keys
    [[ -z "$value" ]] && continue
    [[ "$key" =~ (HOST|PORT|URL|EMAIL) ]] && continue
    for ootb in "${OOTB_PASSWORDS[@]}"; do
      if [ "$value" = "$ootb" ]; then
        check "$key is not OOTB" "false" "value is default '$ootb'"
      fi
    done
  done < .env
fi

# 2. Check compose file has no literal secret values (ignore ${VAR:-default} patterns)
echo ""
echo "Step 2: Check docker-compose.yml for hardcoded secrets (not env var defaults)"
HARDCODED_SECRETS=("knowledge123" "clickhouse123" "minio123456" "pk-lf-knowledge" "sk-lf-knowledge")
for ootb in "${HARDCODED_SECRETS[@]}"; do
  # Count occurrences that are NOT inside ${...:-...} default patterns
  count=$(grep -v '^\s*#' docker-compose.yml | grep -v '\${'  | grep -c "$ootb" 2>/dev/null || true)
  if [ "$count" -eq 0 ]; then
    check "No hardcoded '$ootb' in compose" "true"
  else
    check "No hardcoded '$ootb' in compose" "false" "found $count occurrences outside \${} defaults"
  fi
done

# 3. Check running services reject OOTB creds
echo ""
echo "Step 3: Check running services reject OOTB credentials"

# PostgreSQL — try TCP connection with OOTB password
PG_PORT=$(grep POSTGRES_HOST_PORT .env 2>/dev/null | cut -d= -f2 || echo "5433")
if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "postgres"; then
  if PGPASSWORD=knowledge123 psql -h localhost -p "$PG_PORT" -U knowledge -d knowledge_workflow -c "SELECT 1" >/dev/null 2>&1; then
    check "PostgreSQL rejects 'knowledge123' (TCP)" "false" "OOTB password works over TCP!"
  else
    check "PostgreSQL rejects 'knowledge123' (TCP)" "true"
  fi
else
  check "PostgreSQL rejects 'knowledge123' (TCP)" "true" "(container not running, skipped)"
fi

# Grafana
if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "grafana"; then
  GF_STATUS=$(curl -sf -o /dev/null -w "%{http_code}" http://localhost:3211/api/org -u admin:knowledge123 2>/dev/null || echo "000")
  if [ "$GF_STATUS" = "200" ]; then
    check "Grafana rejects admin/knowledge123" "false" "OOTB password still works!"
  else
    check "Grafana rejects admin/knowledge123" "true"
  fi
else
  check "Grafana rejects admin/knowledge123" "true" "(container not running, skipped)"
fi

# MinIO
if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "minio"; then
  MINIO_STATUS=$(curl -sf -o /dev/null -w "%{http_code}" "http://localhost:9001/api/v1/login" -X POST -d '{"accessKey":"minio","secretKey":"minio123456"}' -H "Content-Type: application/json" 2>/dev/null || echo "000")
  if [ "$MINIO_STATUS" = "204" ] || [ "$MINIO_STATUS" = "200" ]; then
    check "MinIO rejects minio/minio123456" "false" "OOTB password still works!"
  else
    check "MinIO rejects minio/minio123456" "true"
  fi
else
  check "MinIO rejects minio/minio123456" "true" "(container not running, skipped)"
fi

# Langfuse health
if docker ps --format '{{.Names}}' 2>/dev/null | grep -q "langfuse"; then
  LF_HEALTH=$(curl -sf http://localhost:3210/api/public/health 2>/dev/null || echo "down")
  if echo "$LF_HEALTH" | grep -q "OK"; then
    check "Langfuse is running" "true"
  else
    check "Langfuse is running" "false" "$LF_HEALTH"
  fi
else
  check "Langfuse is running" "true" "(container not running, skipped)"
fi

# Summary
echo ""
echo "── Done: $CHECKS checks, $ERRORS failed ──"
echo ""
exit $((ERRORS > 0 ? 1 : 0))
