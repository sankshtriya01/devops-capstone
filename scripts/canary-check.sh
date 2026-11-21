#!/usr/bin/env bash
# Checks that the canary pod is healthy before the full rollout.
# Exits with an error (which triggers the rollback step in the pipeline) if not.
set -euo pipefail

NS=tasktracker
CHECKS=10

echo "Starting canary health checks..."
POD=$(kubectl -n "$NS" get pod -l track=canary -o jsonpath='{.items[0].metadata.name}')

kubectl -n "$NS" port-forward "pod/$POD" 18080:8080 >/dev/null 2>&1 &
PF_PID=$!
trap 'kill $PF_PID 2>/dev/null || true' EXIT
sleep 3

FAIL=0
for i in $(seq 1 $CHECKS); do
  CODE=$(curl -s -o /dev/null -w '%{http_code}' http://localhost:18080/health || echo 000)
  echo "check $i/$CHECKS -> HTTP $CODE"
  [ "$CODE" = "200" ] || FAIL=$((FAIL + 1))
  sleep 2
done

if [ "$FAIL" -gt 0 ]; then
  echo "Canary FAILED ($FAIL of $CHECKS checks bad). Aborting."
  exit 1
fi
echo "Canary PASSED. Safe to promote."
