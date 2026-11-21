# Jenkins with the tools our pipeline needs: Docker CLI, Python, kubectl, SonarScanner.
FROM jenkins/jenkins:lts-jdk17
USER root

RUN apt-get update \
 && apt-get install -y --no-install-recommends docker.io python3 python3-pip python3-venv \
        curl unzip ca-certificates \
 && rm -rf /var/lib/apt/lists/*

RUN curl -fsSL -o /tmp/sonar.zip \
      https://binaries.sonarsource.com/Distribution/sonar-scanner-cli/sonar-scanner-cli-6.2.1.4610-linux-x64.zip \
 && unzip -q /tmp/sonar.zip -d /opt \
 && ln -s /opt/sonar-scanner-6.2.1.4610-linux-x64/bin/sonar-scanner /usr/local/bin/sonar-scanner \
 && rm /tmp/sonar.zip

RUN curl -fsSL -o /usr/local/bin/kubectl https://dl.k8s.io/release/v1.31.0/bin/linux/amd64/kubectl \
 && chmod +x /usr/local/bin/kubectl

# Docker command-line client (the apt package on this Jenkins image does not include it).
RUN curl -fsSL https://download.docker.com/linux/static/stable/x86_64/docker-27.3.1.tgz \
      | tar -xz -C /tmp \
 && mv /tmp/docker/docker /usr/local/bin/docker \
 && rm -rf /tmp/docker

# Plugins are installed from the Jenkins web page ("Install suggested plugins").
# Runs as root so it can use the Docker socket (lab setup only, not for production).