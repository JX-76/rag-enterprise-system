# Terraform - AWS部署配置
terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# VPC
resource "aws_vpc" "rag_vpc" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "rag-vpc"
  }
}

# EKS Cluster
resource "aws_eks_cluster" "rag_cluster" {
  name     = "rag-cluster"
  role_arn = aws_iam_role.eks_cluster.arn
  version  = "1.28"

  vpc_config {
    subnet_ids = aws_subnet.rag_subnet[*].id
  }

  depends_on = [
    aws_iam_role_policy_attachment.eks_cluster_policy,
  ]
}

# RDS PostgreSQL (用于Milvus元数据)
resource "aws_db_instance" "rag_postgres" {
  identifier        = "rag-postgres"
  engine            = "postgres"
  engine_version    = "15"
  instance_class    = "db.t3.micro"
  allocated_storage = 20
  storage_type      = "gp2"
  
  db_name  = "ragdb"
  username = "raguser"
  password = var.db_password

  vpc_security_group_ids = [aws_security_group.rag_db.id]
  db_subnet_group_name   = aws_db_subnet_group.rag.name

  skip_final_snapshot = true
}

# ElastiCache Redis
resource "aws_elasticache_cluster" "rag_redis" {
  cluster_id           = "rag-redis"
  engine               = "redis"
  node_type            = "cache.t3.micro"
  num_cache_nodes      = 1
  parameter_group_name = "default.redis7"
  port                 = 6379
  security_group_ids   = [aws_security_group.rag_cache.id]
}

# S3 Bucket (文档存储)
resource "aws_s3_bucket" "rag_documents" {
  bucket = "rag-enterprise-documents"
}

# Application Load Balancer
resource "aws_lb" "rag_alb" {
  name               = "rag-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.rag_alb.id]
  subnets            = aws_subnet.rag_subnet[*].id
}
