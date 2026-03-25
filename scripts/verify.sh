#!/usr/bin/env bash
# Post-deploy health verification — runs on the target host (localhost checks).
set -euo pipefail

PASS=0; FAIL=0; WARN=0

check() {
  if [ "$2" = "$3" ]; then
    echo "  ✓ $1"
    PASS=$((PASS+1))
  else
    echo "  ✗ $1 (expected $3, got $2)"
    FAIL=$((FAIL+1))
  fi
}

echo "── 1. Service health endpoints ──"
for pair in \
  "knowledge-api:localhost:8001/health" \
  "claude-agent:localhost:8004/health" \
  "tidy-mcp:localhost:8003/health" \
  "litellm-proxy:localhost:4000/health/liveliness"; do
  SVC=${pair%%:*}; URL=${pair#*:}
  CODE=$(curl -sf -o /dev/null -w "%{http_code}" --connect-timeout 5 "http://$URL" 2>/dev/null || echo "000")
  check "$SVC" "$CODE" "200"
done

echo ""
echo "── 2. Database connectivity ──"
CODE=$(curl -sf -o /dev/null -w "%{http_code}" --connect-timeout 5 "http://localhost:6333/healthz" 2>/dev/null || echo "000")
check "qdrant" "$CODE" "200"

NEO4J=$(curl -sf -o /dev/null -w "%{http_code}" --connect-timeout 5 "http://localhost:7474" 2>/dev/null || echo "000")
check "neo4j" "$NEO4J" "200"

PG=$(docker compose exec -T postgres pg_isready -q 2>/dev/null && echo ok || echo fail)
if [ "$PG" = "ok" ]; then
  echo "  ✓ postgres"; PASS=$((PASS+1))
else
  echo "  ✗ postgres (not ready)"; FAIL=$((FAIL+1))
fi

echo ""
echo "── 3. LM Studio (embedding model) ──"
LMS=$(curl -sf -o /dev/null -w "%{http_code}" --connect-timeout 5 "http://localhost:1234/v1/models" 2>/dev/null || echo "000")
check "lm-studio" "$LMS" "200"

echo ""
echo "── 4. Container status ──"
UNHEALTHY=$(docker compose ps 2>/dev/null | grep -cE 'Restarting|Exit' || true)
if [ "$UNHEALTHY" = "0" ]; then
  echo "  ✓ All containers running"; PASS=$((PASS+1))
else
  echo "  ✗ $UNHEALTHY container(s) unhealthy"; FAIL=$((FAIL+1))
  docker compose ps 2>/dev/null | grep -E 'Restarting|Exit'
fi

echo ""
echo "── 5. Observability ──"
PROM=$(curl -sf -o /dev/null -w "%{http_code}" --connect-timeout 5 "http://localhost:9090/-/ready" 2>/dev/null || echo "000")
check "prometheus" "$PROM" "200"

GRAF=$(curl -sf -o /dev/null -w "%{http_code}" --connect-timeout 5 "http://localhost:3001/api/health" 2>/dev/null || echo "000")
check "grafana" "$GRAF" "200"

FUSE=$(curl -sf -o /dev/null -w "%{http_code}" --connect-timeout 5 "http://localhost:3210/api/public/health" 2>/dev/null || echo "000")
if [ "$FUSE" = "200" ]; then
  echo "  ✓ langfuse"; PASS=$((PASS+1))
else
  echo "  ⚠ langfuse (not running — optional)"; WARN=$((WARN+1))
fi

echo ""
echo "── Summary: $PASS passed, $FAIL failed, $WARN skipped ──"
[ "$FAIL" = "0" ] && echo "✓ All checks passed" || { echo "✗ $FAIL check(s) failed"; exit 1; }
