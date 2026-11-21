# Screenshots to capture for the report

I could not take these for you, because they come from your own machine and accounts.
Take each one while you follow the README, and paste it into the matching report section.

| # | What to capture | How |
|---|---|---|
| 1 | GitHub repo page showing folders and commit history | Open your repo on GitHub |
| 2 | Passing unit tests | `cd app && pytest -v` |
| 3 | Pipeline run, all green | GitHub > Actions tab |
| 4 | Pipeline security scan step output | Open the `security-scan` job |
| 5 | Docker image built and running | `docker compose ps` |
| 6 | Kubernetes pods running | `kubectl -n tasktracker get pods -o wide` |
| 7 | Canary and stable pods side by side | `kubectl -n tasktracker get pods --show-labels` |
| 8 | Terraform apply finished | `terraform apply` output |
| 9 | Grafana dashboard with live traffic | http://localhost:3000 |
| 10 | Prometheus alert firing | http://localhost:9090/alerts after calling `/crash` many times |
| 11 | Logs in Grafana (Loki) | Grafana > Explore > Loki |
| 12 | Rollback working | `bash scripts/rollback.sh` output |
| 13 | Auto-scaling reacting | `kubectl -n tasktracker get hpa -w` while sending load |
