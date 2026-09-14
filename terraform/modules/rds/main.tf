terraform {
  required_version = ">= 1.5.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

resource "aws_db_subnet_group" "rds" {
  name       = "${var.environment}-rds-subnet-group"
  subnet_ids = var.subnet_ids

  tags = {
    Name = "${var.environment}-rds-subnet-group"
  }
}

resource "aws_security_group" "rds" {
  name        = "${var.environment}-rds-sg"
  description = "Allow inbound PostgreSQL traffic from ECS tasks"
  vpc_id      = var.vpc_id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [var.ecs_security_group_id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.environment}-rds-sg"
  }
}

resource "aws_rds_cluster_parameter_group" "aurora_pg" {
  name        = "${var.environment}-aurora-pg-params"
  family      = "aurora-postgresql16"
  description = "Parameter group enabling pgvector extension"

  parameter {
    name  = "shared_preload_libraries"
    value = "vector"
  }

  tags = {
    Name = "${var.environment}-aurora-pg-params"
  }
}

resource "aws_rds_cluster" "aurora" {
  cluster_identifier              = "${var.environment}-research-cluster"
  engine                          = "aurora-postgresql"
  engine_version                  = "16.1"
  database_name                   = var.database_name
  master_username                 = var.master_username
  master_password                 = var.master_password
  db_subnet_group_name            = aws_db_subnet_group.rds.name
  vpc_security_group_ids          = [aws_security_group.rds.id]
  db_cluster_parameter_group_name = aws_rds_cluster_parameter_group.aurora_pg.name
  skip_final_snapshot             = true

  serverlessv2_scaling_configuration {
    min_capacity = 0.5
    max_capacity = 4.0
  }

  tags = {
    Name = "${var.environment}-aurora-pgvector"
  }
}

resource "aws_rds_cluster_instance" "aurora_instance" {
  cluster_identifier = aws_rds_cluster.aurora.id
  instance_class     = "db.serverless"
  engine             = aws_rds_cluster.aurora.engine
  engine_version     = aws_rds_cluster.aurora.engine_version

  tags = {
    Name = "${var.environment}-aurora-instance-1"
  }
}
