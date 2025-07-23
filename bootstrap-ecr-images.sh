#!/bin/bash

set -e

# Variables
AWS_REGION="us-east-1"
LOGGER_REPO="$1"
GRAFANA_REPO="$2"
LOKI_REPO="$3"
TAG="latest"

if [[ -z "$LOGGER_REPO" || -z "$GRAFANA_REPO" || -z "$LOKI_REPO" ]]; then
  echo "Usage: ./bootstrap-ecr-images.sh <LOGGER_ECR_REPO> <GRAFANA_ECR_REPO> <LOKI_ECR_REPO>"
  exit 1
fi

echo "Logging in to ECR..."
aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "${LOGGER_REPO%/*}"
aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "${GRAFANA_REPO%/*}"
aws ecr get-login-password --region "$AWS_REGION" | docker login --username AWS --password-stdin "${LOKI_REPO%/*}"

echo "Building and pushing Logger image..."
docker buildx build --platform linux/amd64 -t logger-app:$TAG -f Dockerfile .
docker tag logger-app:$TAG $LOGGER_REPO:$TAG
docker push $LOGGER_REPO:$TAG

echo "Building and pushing Grafana image..."
docker buildx build --platform linux/amd64 -t grafana-app:$TAG -f app/config/grafana/Dockerfile .
docker tag grafana-app:$TAG $GRAFANA_REPO:$TAG
docker push $GRAFANA_REPO:$TAG

echo "Building and pushing Loki image..."
docker buildx build --platform linux/amd64 -t loki-app:$TAG -f app/config/loki/Dockerfile .
docker tag loki-app:$TAG $LOKI_REPO:$TAG
docker push $LOKI_REPO:$TAG

echo "✅ All images have been built and pushed with tag '$TAG'"
