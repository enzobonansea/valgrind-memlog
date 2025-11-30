#!/bin/bash

# Build and push Docker image to your fixed Amazon ECR repository

# Usage: ./build_and_push_ecr.sh


set -e



# Get latest commit hash of main repo
MAIN_COMMIT=$(git rev-parse --short HEAD)

IMAGE_TAG="memlog-${MAIN_COMMIT}"
ECR_REPO_URI="764515255972.dkr.ecr.eu-north-1.amazonaws.com/computer-science/memlog"
ECR_URL="$ECR_REPO_URI:$IMAGE_TAG"



echo "Using image tag: $IMAGE_TAG"

echo "Logging in to Amazon ECR..."
aws ecr get-login-password --region eu-north-1 | docker login --username AWS --password-stdin 764515255972.dkr.ecr.eu-north-1.amazonaws.com



echo "Building Docker image..."
docker build -t memlog:$IMAGE_TAG .

echo "Tagging Docker image..."
docker tag memlog:$IMAGE_TAG $ECR_URL


echo "Pushing Docker image to ECR..."
docker push $ECR_URL

echo "Image pushed: $ECR_URL"
