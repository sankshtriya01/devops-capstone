// Jenkins CI/CD pipeline for TaskTracker.
// Runs automatically after every Git push (it checks GitHub every 2 minutes).
// Secrets are never written here: they come from Jenkins Credentials.
pipeline {
    agent any

    options {
        timestamps()
        disableConcurrentBuilds()
        buildDiscarder(logRotator(numToKeepStr: '10'))
    }

    triggers {
        pollSCM('H/2 * * * *')
    }

    parameters {
        booleanParam(name: 'PUSH_IMAGE', defaultValue: false,
                     description: 'Push the image to GitHub Container Registry (needs ghcr-credentials)')
        booleanParam(name: 'DEPLOY_TO_K8S', defaultValue: false,
                     description: 'Deploy to Kubernetes with a canary (needs kubeconfig credential)')
    }

    environment {
        IMAGE = 'ghcr.io/sankshtriya01/devops-capstone'
        TAG   = "${env.GIT_COMMIT ? env.GIT_COMMIT.take(7) : 'local'}"
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
            }
        }

        stage('Install and lint') {
            steps {
                sh '''
                    python3 -m venv .venv
                    . .venv/bin/activate
                    pip install --quiet -r app/requirements-dev.txt
                    flake8 app --max-line-length=100
                    bandit -r app/main.py app/db.py -q
                '''
            }
        }

        stage('Unit tests') {
            steps {
                sh '''
                    . .venv/bin/activate
                    pytest app -q --junitxml=test-results.xml \
                        --cov=app --cov-report=xml:coverage.xml --cov-report=term
                '''
            }
            post {
                always {
                    junit 'test-results.xml'
                    archiveArtifacts artifacts: 'coverage.xml', allowEmptyArchive: true
                }
            }
        }

        stage('SonarQube analysis') {
            steps {
                withCredentials([string(credentialsId: 'sonar-token', variable: 'SONAR_TOKEN')]) {
                    sh '''
                        sonar-scanner \
                            -Dsonar.host.url=http://sonarqube:9000 \
                            -Dsonar.token=$SONAR_TOKEN
                    '''
                }
            }
        }

        stage('Build Docker image') {
            steps {
                sh 'docker build -t ${IMAGE}:${TAG} --build-arg APP_VERSION=${TAG} .'
            }
        }

        stage('Scan image') {
            steps {
                sh '''
                    docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
                        aquasec/trivy:0.58.1 image --severity CRITICAL --exit-code 1 \
                        --ignore-unfixed ${IMAGE}:${TAG}
                '''
            }
        }

        stage('Push image') {
            when { expression { params.PUSH_IMAGE } }
            steps {
                withCredentials([usernamePassword(credentialsId: 'ghcr-credentials',
                                                  usernameVariable: 'REG_USER',
                                                  passwordVariable: 'REG_PASS')]) {
                    sh '''
                        echo "$REG_PASS" | docker login ghcr.io -u "$REG_USER" --password-stdin
                        docker push ${IMAGE}:${TAG}
                    '''
                }
            }
        }

        stage('Deploy canary, then promote') {
            when { expression { params.DEPLOY_TO_K8S } }
            steps {
                withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG')]) {
                    sh '''
                        kubectl -n tasktracker set image deployment/tasktracker-canary app=${IMAGE}:${TAG}
                        kubectl -n tasktracker rollout status deployment/tasktracker-canary --timeout=120s
                        bash scripts/canary-check.sh
                        kubectl -n tasktracker set image deployment/tasktracker app=${IMAGE}:${TAG}
                        kubectl -n tasktracker rollout status deployment/tasktracker --timeout=180s
                    '''
                }
            }
            post {
                failure {
                    withCredentials([file(credentialsId: 'kubeconfig', variable: 'KUBECONFIG')]) {
                        sh '''
                            kubectl -n tasktracker rollout undo deployment/tasktracker || true
                            kubectl -n tasktracker scale deployment/tasktracker-canary --replicas=0 || true
                        '''
                    }
                }
            }
        }
    }

    post {
        success { echo "Pipeline passed for ${IMAGE}:${TAG}" }
        failure { echo 'Pipeline failed - check the stage that is red.' }
    }
}
