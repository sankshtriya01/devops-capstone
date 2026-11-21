#!/usr/bin/env bash
# Manual recovery: go back to the previous working version.
set -euo pipefail
NS=tasktracker

echo "Current history:"
kubectl -n "$NS" rollout history deployment/tasktracker

kubectl -n "$NS" scale deployment/tasktracker-canary --replicas=0
kubectl -n "$NS" rollout undo deployment/tasktracker
kubectl -n "$NS" rollout status deployment/tasktracker --timeout=180s
echo "Rollback complete."
