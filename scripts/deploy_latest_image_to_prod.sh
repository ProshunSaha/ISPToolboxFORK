#!/bin/bash
# DEPLOY LATEST ECR DOCKER IMAGES TO ECS, PRODUCTION
echo "Pushing Latest image to Async Tier"
aws ecs update-service --cluster isptoolbox-production-async-cluster \
    --service isptoolbox-production-async-service --force-new-deployment
echo "Pushing Latest image to Web Tier"
aws ecs update-service --cluster isptoolbox-production-webserver-cluster \
    --service isptoolbox-production-webserver-service --force-new-deployment
echo "It may take a few minutes for the old containers to stop. \
    The webserver has a 300 second draining period from the load balancer"