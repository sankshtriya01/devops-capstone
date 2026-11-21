# DevOps Capstone: TaskTracker Delivery Platform

An end-to-end DevOps platform that takes code from a Git commit to a safe production
deployment automatically, with monitoring, logging, security checks and rollback built in.

The sample application is **TaskTracker**, a small REST API (Python/Flask) for managing tasks.
The application is deliberately simple. The point of this project is the platform around it.

## What the platform does

| Area | Tool | Where |
|---|---|---|
| Version control | Git + GitHub (feature branches, pull requests) | this repo |
| CI/CD pipeline | GitHub Actions | `.github/workflows/ci-cd.yml` |
| Containerization | Docker (multi-stage, non-root) | `Dockerfile`, `docker-compose.yml` |
| Orchestration | Kubernetes (self-healing, auto-scaling) | `k8s/` |
| Infrastructure automation | Terraform + Ansible | `terraform/`, `ansible/` |
| Monitoring and alerts | Prometheus + Grafana | `monitoring/`, `k8s/prometheusrule.yaml` |
| Logging | JSON logs + Loki + Promtail | `app/main.py`, `monitoring/promtail.yml` |
| Security | Secret scan, code scan, image scan, non-root pods, network policy | pipeline + `k8s/` |
| Advanced deployment | Canary release with automatic rollback | `k8s/deployment-canary.yaml`, `scripts/` |
| Recoverability | Rollout history, rollback script, pod disruption budget | `scripts/rollback.sh`, `k8s/hpa-pdb.yaml` |

## How the flow works

```
 Developer commits code
          |
          v
   GitHub (pull request)
          |
          v
 +---------------------- GitHub Actions ----------------------+
 | 1. Lint + unit tests + code security scan                  |
 | 2. Secret scan + config scan                               |
 | 3. Build Docker image -> scan image -> push to registry    |
 | 4. Deploy CANARY (10% of traffic)                          |
 | 5. Health check the canary                                 |
 |      pass -> promote to all pods                           |
 |      fail -> automatic rollback                            |
 +------------------------------------------------------------+
          |
          v
   Kubernetes cluster  --->  Prometheus (metrics) --> Grafana dashboards + alerts
          |
          +-------------->  Promtail --> Loki (logs) --> Grafana
```

## Project layout

```
app/                 The application and its unit tests
Dockerfile           Builds the container image
docker-compose.yml   Runs app + monitoring + logging on one machine
k8s/                 Kubernetes manifests (deployments, service, autoscaler, policies)
terraform/           Prepares the cluster and installs monitoring/logging
ansible/             Installs the tools on a fresh server
monitoring/          Prometheus, alert rules, Grafana dashboard, Promtail config
scripts/             canary-check.sh and rollback.sh
sample-data/         Real sample logs and metrics captured from the running app
docs/                Architecture notes, security notes, test evidence checklist
```

## Run it yourself

### Option A: Quickest (no Kubernetes), run on your laptop

Needs: Docker.

```bash
docker compose up -d --build
```

Then open:
- App: http://localhost:8080/health
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 (user `admin`, password `admin`; dashboard "TaskTracker Overview")

Try it:
```bash
curl -X POST localhost:8080/tasks -H 'Content-Type: application/json' -d '{"title":"hello"}'
curl localhost:8080/tasks
curl localhost:8080/crash        # makes an error so you can see the alert/dashboard react
```

Stop everything: `docker compose down`

### Option B: Full platform on Kubernetes (minikube)

Needs: Docker, minikube, kubectl, Terraform, Helm.
(`ansible-playbook -i ansible/inventory.ini ansible/playbook.yml` installs them on Ubuntu.)

```bash
# 1. Start a local cluster
minikube start --cpus=4 --memory=6g

# 2. Create namespaces, quotas, Prometheus, Grafana and Loki
cd terraform
terraform init
terraform apply -var="grafana_admin_password=choose-a-password"
cd ..

# 3. Put your GitHub username into the image name in both deployment files
#    (replace YOUR_GITHUB_USERNAME in k8s/deployment.yaml and k8s/deployment-canary.yaml)

# 4. Deploy the app
kubectl apply -f k8s/

# 5. Look at it
kubectl -n tasktracker get pods
kubectl -n tasktracker port-forward svc/tasktracker 8080:80
kubectl -n monitoring port-forward svc/kube-prometheus-stack-grafana 3000:80
```

### Option C: Turn on the automated pipeline

1. Push this repo to GitHub.
2. In the repo go to **Settings > Environments**, create an environment named `production`
   and add yourself as a required reviewer (this is the manual approval step).
3. In **Settings > Secrets and variables > Actions**, add a secret called `KUBE_CONFIG`
   containing your base64-encoded kubeconfig:
   `base64 -w0 ~/.kube/config`
   (The cluster must be reachable from the internet for GitHub-hosted runners. For a local
   minikube, use a self-hosted runner instead and change `runs-on` in the deploy job.)
4. Make a change, push to `main`, and watch the **Actions** tab.

## Run the tests

```bash
cd app
pip install -r requirements-dev.txt
pytest -q
```

## Demo: failure and recovery

1. Deploy a bad version (for example set `ENABLE_CRASH_ENDPOINT=true` and call `/crash`).
2. The `HighErrorRate` alert fires and the Grafana error-rate panel rises.
3. If the canary health check fails, the pipeline rolls back by itself.
4. To roll back by hand: `bash scripts/rollback.sh`

## Security measures

- Container runs as a non-root user with a read-only filesystem and all Linux capabilities dropped.
- Secrets are never stored in the repo (secret scanning in CI; `.gitignore` blocks `.env` and Terraform state).
- Image is scanned for critical vulnerabilities and the pipeline stops if any are found.
- Kubernetes namespace enforces the `restricted` pod security standard.
- Network policy denies all traffic except to the app port.
- Resource limits stop one pod from using the whole cluster.

## Sample data

`sample-data/app-sample.log` holds real JSON log lines and `sample-data/metrics-sample.txt`
holds real metrics captured from the running application.
