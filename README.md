# Dockerized FastAPI Application for AWS EC2 Management

This project is a containerized FastAPI service designed to manage the lifecycle of AWS EC2 instances through REST endpoints. The application is built to programmatically create and terminate EC2 instances, making it a flexible solution for on-demand cloud resource management.

## Overview

- **FastAPI Backend:**  
  A high-performance REST API built using FastAPI allows users to create and terminate EC2 instances via clearly defined endpoints.

- **Dockerization:**  
  The entire application is containerized using Docker, which simplifies dependency management, ensures consistency across environments, and eases deployment.

- **AWS ECR Integration:**  
  Docker images are pushed to AWS Elastic Container Registry (ECR) for secure storage and version control, facilitating straightforward updates and rollbacks.

- **ECS Fargate Deployment:**  
  The application is deployed on AWS ECS Fargate using a task definition. This serverless container management approach eliminates the need to manage underlying infrastructure.

- **AWS Resource Management:**  
  Endpoints interact with AWS services (likely using the boto3 library) to manage EC2 instances, thereby automating the scaling and resource allocation processes.

## Features

- **API Endpoints:**
  - **Create Instance:** Launch new EC2 instances.
  - **Terminate Instance:** Shut down existing EC2 instances using their instance ID.
- **Containerized Deployment:**  
  Designed to run in a Docker container for streamlined deployment and reproducibility.

- **Cloud-First Approach:**  
  Fully integrates with AWS services (ECR, ECS Fargate, EC2) to provide a scalable, robust cloud-native solution.

## Prerequisites

Before running or deploying the application, ensure you have the following:

- [Docker](https://docs.docker.com/get-docker/)
- [AWS CLI](https://aws.amazon.com/cli/) configured with the necessary AWS credentials and permissions
- An AWS account with permissions for ECS, ECR, and EC2 management
- Python 3.12+ (for local development and testing)

## Getting Started

### 1. Clone the Repository

git clone <GITHUB-REPO>.git
cd fastapi-docker-ecs-app

### 2. Clone the Repository

docker build -t my-fastapi-app .

### 3. Run the Application Locally

docker run -p 8000:8000 my-fastapi-app

### 4. Push the Image to AWS ECR

aws ecr get-login-password --region <region> | docker login --username AWS --password-stdin <aws_account_id>.dkr.ecr.<region>.amazonaws.com

docker tag my-fastapi-app:latest <aws_account_id>.dkr.ecr.<region>.amazonaws.com/my-fastapi-app:latest
docker push <aws_account_id>.dkr.ecr.<region>.amazonaws.com/my-fastapi-app:latest

### 5. Deploy on AWS ECS Fargate

### Create an ECS Cluster:

aws ecs create-cluster --cluster-name fastapi-cluster

### IAM Task Definition execution role

aws iam create-role --role-name ecsTaskExecutionRole --assume-role-policy-document file://trust-policy.json

### Attach policy, AmazonECSTaskExecutionRolePolicy to role, ecsTaskExecutionRole

aws iam attach-role-policy \
 --role-name ecsTaskExecutionRole \
 --policy-arn arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy

### Create Task Role to create & terminate EC2 instance, create Key Pair, and create Security Group

aws iam create-role \
--role-name ECS_EC2Access_Role \
--assume-role-policy-document file://trust-policy.json

### Attach policy, ec2-policy.json to role, ECS_EC2Access_Role

aws iam put-role-policy \
--role-name ECS_EC2Access_Role \
--policy-name EC2PermissionsPolicy \
--policy-document file://ec2-policy.json

### Register the task definition

aws ecs register-task-definition \
--cli-input-json file://task-definition.json

### Create Security Group for ECS Service

aws ec2 create-security-group \
--group-name fastapi-app-sg \
--description "Security group for FastAPI application"

### Add Inbound Rules to the Security Group

# Allow HTTP

aws ec2 authorize-security-group-ingress \
--group-id <sg-id> \
--protocol tcp \
--port 8000 \
--cidr 0.0.0.0/0

### Create log group in CloudWatch

aws logs create-log-group \
 --log-group-name "/ecs/fastapi-task" \
 --region us-east-1

### Create ECS Service

aws ecs create-service \
 --cluster fastapi-cluster \
 --service-name fastapi-service \
 --task-definition fastapi-task \
 --desired-count 1 \
 --launch-type FARGATE \
 --network-configuration \
 "{
\"awsvpcConfiguration\": {
\"subnets\": [\"subnet-id1\", \"subnet-id2\"],
\"securityGroups\": [\"sg-id\"],
\"assignPublicIp\": \"ENABLED\"
}
}"
