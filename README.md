# DevOps Capstone - Version B

Course: DevOps & Automation Lab (ENSP461), B.Tech CSE Semester VII.

Application: **TaskTracker**, a task manager with user login, a PostgreSQL database, a responsive
web interface and a REST API (Python/Flask). The application is deliberately simple; the project
is about the delivery platform around it.

## Phase map (assignment phase -> where it is in this repo)

| Phase | Requirement | Where |
|---|---|---|
| App | Login, CRUD, database, responsive UI, REST API, error handling | `app/` |
| 1 | Version control (GitHub, branches, merges, conflicts) | this repo, `docs/GIT-WORKFLOW.md` |
| 2 | CI with Jenkins (build, test, package after every push) | `Jenkinsfile`, `jenkins/` |
| 3 | Docker (Dockerfile, image, Compose) | `Dockerfile`, `docker-compose.yml` |
| 4 | Kubernetes (Deployment, Service, ConfigMap, Secret, Persistent Volume, scaling, rolling update, rollback) | `k8s/app/` |
| 5 | Ansible (Docker, Kubernetes, app deployment, configuration) | `ansible/` |
| 6 | Terraform (variables, outputs, modules) | `terraform/` |
| 7 | Monitoring (Prometheus, Grafana) | `monitoring/`, `k8s/app/prometheusrule.yaml`, `terraform/modules/monitoring` |
| 8 | Logging (Fluentd + Elasticsearch + Kibana) | `k8s/logging/` |
| 9 | Security (SonarQube, secrets, image scanning, RBAC, Jenkins credentials) | `sonar-project.properties`, `k8s/app/secret.yaml`, `k8s/app/rbac.yaml`, `Jenkinsfile` |
| 10 | Deployment strategy (canary) | `k8s/app/deployment-canary.yaml`, `scripts/canary-check.sh` |
| 11 | GitOps (Argo CD) | `argocd/application.yaml`, `terraform/modules/gitops` |
| Bonus | Auto scaling, CI security scanning, unit test coverage | `k8s/app/hpa-pdb.yaml`, `.github/workflows/ci-cd.yml`, `Jenkinsfile` |

`.github/workflows/ci-cd.yml` is a second pipeline on GitHub Actions. Jenkins is the pipeline the
assignment asks for; GitHub Actions builds and publishes the container image that Kubernetes pulls.

## Flow

```
Developer -> GitHub -> Jenkins (lint, test, SonarQube, build, scan) -> Docker image (ghcr.io)
                                         |
                    Argo CD watches k8s/app in GitHub  ->  Kubernetes cluster
                                                            |-- Prometheus -> Grafana (metrics, alerts)
                                                            |-- Fluentd -> Elasticsearch -> Kibana (logs)
                                                            `-- PostgreSQL + Persistent Volume
```

## Run it

### 1. The application, with Docker (needs Docker Desktop)

```bash
docker compose up -d --build
```

- App: http://localhost:8080 (register an account, then log in)
- Prometheus: http://localhost:9090  Grafana: http://localhost:3000 (admin / admin)

Run the tests without Docker:

```bash
cd app
pip install -r requirements-dev.txt
pytest -q
```

### 2. Jenkins and SonarQube

```bash
cd jenkins
docker compose up -d --build
```

- Jenkins: http://localhost:8081 (first password: `docker exec jenkins cat /var/jenkins_home/secrets/initialAdminPassword`)
- SonarQube: http://localhost:9000 (admin / admin, it asks you to change the password)

One-time setup in Jenkins:
1. Install suggested plugins and create an admin user.
2. In SonarQube create a token (My Account > Security). In Jenkins add it under Manage Jenkins >
   Credentials as **Secret text** with ID `sonar-token`.
3. New Item > Pipeline > "Pipeline script from SCM" > Git > your repo URL, branch `main`,
   script path `Jenkinsfile`.
4. Click **Build Now**. After that it polls GitHub every 2 minutes and builds after every push.

Optional credentials (the pipeline only needs them if you tick the matching parameter):
`ghcr-credentials` (Username with password, a GitHub token with package write) and `kubeconfig` (Secret file).

### 3. Kubernetes (Docker Desktop with Kubernetes enabled)

```bash
cd terraform
terraform init
terraform apply -var "kube_context=docker-desktop" -var "grafana_admin_password=<choose one>"
cd ..
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/app/
kubectl apply -f k8s/logging/
kubectl -n tasktracker get pods,pvc,pv
```

Use `-var "enable_gitops=false"` to skip Argo CD if the laptop is short of memory.

Open the app: `kubectl -n tasktracker port-forward svc/tasktracker 8080:80`

### 4. GitOps with Argo CD

```bash
kubectl apply -f argocd/application.yaml
kubectl -n argocd port-forward svc/argocd-server 8443:443
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}"
```

The last command prints the password in base64; decode it, then log in at https://localhost:8443
as `admin`. When using GitOps, do not run `kubectl apply -f k8s/app/` yourself; Argo CD does it.

### 5. Ansible (on a Linux or WSL machine)

```bash
cd ansible
ansible-playbook site.yml                 # everything
ansible-playbook playbooks/01-docker.yml  # or one at a time
```

## Demonstrations

| What | Commands |
|---|---|
| Scaling | `kubectl -n tasktracker scale deployment/tasktracker --replicas=12` and `kubectl -n tasktracker get hpa` |
| Rolling update | `kubectl -n tasktracker set image deployment/tasktracker app=ghcr.io/sankshtriya01/devops-capstone:<tag>` then `kubectl -n tasktracker rollout status deployment/tasktracker` |
| Rollback | `kubectl -n tasktracker rollout undo deployment/tasktracker` |
| Canary | `kubectl -n tasktracker get pods --show-labels` (9 stable + 1 canary) |
| RBAC | `kubectl auth can-i get pods -n tasktracker --as=system:serviceaccount:tasktracker:viewer` (yes) and `... delete pods ...` (no) and `... get secrets ...` (no) |
| Persistent data | Add a task, run `kubectl -n tasktracker delete pod -l app=postgres`, wait, reload: the task is still there |
| Alert | `docker compose stop app`, wait 2 minutes, open http://localhost:9090/alerts |
| Logs | `kubectl -n logging port-forward svc/kibana 5601:5601`, then create a data view `logstash-*` |

## Security measures

- Passwords are stored hashed; login cookies are HttpOnly and SameSite; forms carry a CSRF token.
- Each user can only see their own tasks.
- Container runs as a non-root user with a read-only filesystem and no Linux capabilities.
- Secrets are in a Kubernetes Secret, not in code. The values in `k8s/app/secret.yaml` are lab
  values; production would use Sealed Secrets or a cloud secret manager.
- Jenkins credentials are stored in the Jenkins credential store, never in the `Jenkinsfile`.
- SonarQube analyses the code and enforces a quality gate; Bandit, Gitleaks and Trivy scan code, secrets and images.
- RBAC: the app has no API access, `viewer` is read-only, `ci-deployer` can only update deployments.
- Network policy: the database accepts traffic only from the app pods.

## Sample data

`sample-data/app-sample.log` holds real JSON log lines (including a failed and a successful login) and
`sample-data/metrics-sample.txt` holds real metrics captured from the running application.
nBuilt for the ENSP461 DevOps and Automation Lab.
