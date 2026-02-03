terraform {
  backend "s3" {
    bucket = "terraform-state-cloud-registry-5780"  # Assicurati che questo sia il tuo bucket corretto
    key    = "stato-registro/terraform.tfstate"
    region = "eu-central-1"
  }
}

provider "aws" {
  region = "eu-central-1"
}

# 1. DYNAMODB
resource "aws_dynamodb_table" "db" {
  name         = "CloudRegistryDB"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "PK"
  range_key    = "SK"

  attribute {
    name = "PK"
    type = "S"
  }

  attribute {
    name = "SK"
    type = "S"
  }
}

# 2. COGNITO
resource "aws_cognito_user_pool" "pool" {
  name = "RegistryPool"
  admin_create_user_config {
    allow_admin_create_user_only = false
  }
  
  schema {
    attribute_data_type = "String"
    name                = "role"
    mutable             = true
    string_attribute_constraints {
      min_length = 1
      max_length = 20
    }
  }

  schema {
    attribute_data_type = "String"
    name                = "classe"
    mutable             = true
    string_attribute_constraints {
      min_length = 1
      max_length = 10
    }
  }

  # Configurazione Email per Cognito (Verifica Account)
  auto_verified_attributes = ["email"]

  email_configuration {
    email_sending_account = "COGNITO_DEFAULT" 
  }

  verification_message_template {
    default_email_option = "CONFIRM_WITH_CODE"
    email_subject        = "Il tuo codice di verifica registro Cloud"
    email_message        = "Benvenuto! Il tuo codice di verifica è: {####}"
  }
}

resource "aws_cognito_user_pool_client" "client" {
  name         = "RegistryClient"
  user_pool_id = aws_cognito_user_pool.pool.id
}

# 3. SNS (Lasciato per compatibilità, ma useremo SES)
resource "aws_sns_topic" "topic" {
  name = "RegistryNotifications"
}

# 4. IAM ROLE
resource "aws_iam_role" "iam_for_lambda" {
  name = "iam_for_lambda_registry_v7" 
  
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "lambda.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_sns" {
  role       = aws_iam_role.iam_for_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSNSFullAccess"
}

resource "aws_iam_role_policy" "lambda_policy_v7" {
  name = "lambda_policy_v7"
  role = aws_iam_role.iam_for_lambda.id
  
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action   = ["dynamodb:PutItem", "dynamodb:GetItem", "dynamodb:Query", "dynamodb:Scan"]
        Effect   = "Allow"
        Resource = "*"
      },
      {
        Action   = ["sns:Publish"]
        Effect   = "Allow"
        Resource = "*"
      },
      # 👇👇👇 AGGIUNGI QUESTO BLOCCO PER SES 👇👇👇
      {
        Action   = ["ses:SendEmail", "ses:SendRawEmail"]
        Effect   = "Allow"
        Resource = "*"
      },
      # 👆👆👆 FINE AGGIUNTA 👆👆👆
      {
        Action   = ["logs:*"]
        Effect   = "Allow"
        Resource = "*"
      },
      {
        Action   = ["cognito-idp:ListUsers"]
        Effect   = "Allow"
        Resource = "*"
      }
    ]
  })
}

# 5. LAMBDA
resource "aws_lambda_function" "backend" {
  filename         = "codice.zip"
  function_name    = "RegistryBackend"
  role             = aws_iam_role.iam_for_lambda.arn
  handler          = "index.lambda_handler"
  source_code_hash = filebase64sha256("codice.zip")
  runtime          = "python3.9"
  
  environment {
    variables = {
      TABLE_NAME    = aws_dynamodb_table.db.name
      SNS_TOPIC_ARN = aws_sns_topic.topic.arn
      USER_POOL_ID  = aws_cognito_user_pool.pool.id
    }
  }
}

# 6. API GATEWAY
resource "aws_apigatewayv2_api" "api" {
  name          = "RegistryAPI_v5"
  protocol_type = "HTTP"

  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["POST", "GET", "OPTIONS"]
    allow_headers = ["content-type", "authorization"]
    max_age       = 300
  }
}

resource "aws_apigatewayv2_stage" "stage" {
  api_id      = aws_apigatewayv2_api.api.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_apigatewayv2_integration" "integ" {
  api_id           = aws_apigatewayv2_api.api.id
  integration_type = "AWS_PROXY"
  integration_uri  = aws_lambda_function.backend.invoke_arn
}

resource "aws_apigatewayv2_route" "route" {
  api_id    = aws_apigatewayv2_api.api.id
  route_key = "POST /voto"
  target    = "integrations/${aws_apigatewayv2_integration.integ.id}"
}

resource "aws_apigatewayv2_route" "route_get" {
  api_id    = aws_apigatewayv2_api.api.id
  route_key = "GET /voto"
  target    = "integrations/${aws_apigatewayv2_integration.integ.id}"
}

resource "aws_lambda_permission" "api_perm" {
  statement_id  = "AllowAPI_v7"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.backend.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.api.execution_arn}/*/*"
}

# --- 7. S3 STATIC WEBSITE HOSTING ---

resource "random_id" "bucket_suffix" {
  byte_length = 4
}

resource "aws_s3_bucket" "frontend" {
  bucket = "registro-cloud-frontend-${random_id.bucket_suffix.hex}"
  force_destroy = true 
}

resource "aws_s3_bucket_website_configuration" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  index_document {
    suffix = "index.html"
  }
}

resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

resource "aws_s3_bucket_policy" "frontend_public_read" {
  bucket = aws_s3_bucket.frontend.id
  depends_on = [aws_s3_bucket_public_access_block.frontend]

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "PublicReadGetObject"
        Effect    = "Allow"
        Principal = "*"
        Action    = "s3:GetObject"
        Resource  = "${aws_s3_bucket.frontend.arn}/*"
      },
    ]
  })
}

# --- 8. UPLOAD DEI FILE ---

resource "aws_s3_object" "index" {
  bucket       = aws_s3_bucket.frontend.id
  key          = "index.html"
  source       = "frontend/index.html"
  content_type = "text/html"
  etag         = filemd5("frontend/index.html")
}

resource "aws_s3_object" "config" {
  bucket       = aws_s3_bucket.frontend.id
  key          = "config.js"
  content_type = "application/javascript"
  
  content = <<EOF
window.apiConfig = {
    UserPoolId: "${aws_cognito_user_pool.pool.id}",
    ClientId:   "${aws_cognito_user_pool_client.client.id}",
    ApiUrl:     "${aws_apigatewayv2_stage.stage.invoke_url}"
};
EOF
}

output "SITO_WEB_URL" {
  value = "http://${aws_s3_bucket_website_configuration.frontend.website_endpoint}"
  description = "Clicca qui per vedere il sito funzionante"
}

# ==========================================
# SEZIONE CONTAINER (ECR + ECS FARGATE)
# ==========================================

# 1. ECR REPOSITORY (Il garage per l'immagine Docker)
resource "aws_ecr_repository" "repo" {
  name                 = "registro-note-app"
  image_tag_mutability = "MUTABLE"
  force_delete         = true # Permette di distruggere tutto con terraform destroy
}

# 2. RETE (Usiamo la VPC di Default per semplicità)
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# Security Group per il container (Apre la porta 80)
resource "aws_security_group" "ecs_sg" {
  name        = "ecs-tasks-sg"
  description = "Allow HTTP inbound traffic"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

# 3. IAM ROLES (Permessi per il Container)

# Ruolo di Esecuzione (Serve a Fargate per scaricare l'immagine e scrivere log)
resource "aws_iam_role" "ecs_execution_role" {
  name = "ecs_execution_role_v1"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_execution_policy" {
  role       = aws_iam_role.ecs_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# Ruolo del Task (Serve all'app Flask per usare DynamoDB)
resource "aws_iam_role" "ecs_task_role" {
  name = "ecs_task_role_v1"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
    }]
  })
}

# Policy per DynamoDB
resource "aws_iam_role_policy" "ecs_dynamo_policy" {
  name = "ecs_dynamo_access"
  role = aws_iam_role.ecs_task_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action   = ["dynamodb:PutItem", "dynamodb:GetItem", "dynamodb:Query", "dynamodb:Scan"]
        Effect   = "Allow"
        Resource = "*"
      }
    ]
  })
}

# 4. CLUSTER ECS E TASK DEFINITION

resource "aws_ecs_cluster" "cluster" {
  name = "registro-cloud-cluster"
}

resource "aws_cloudwatch_log_group" "ecs_logs" {
  name              = "/ecs/registro-note-app"
  retention_in_days = 1
}

resource "aws_ecs_task_definition" "app" {
  family                   = "registro-note-task"
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = "256" # 0.25 vCPU (Minimo per risparmiare)
  memory                   = "512" # 0.5 GB RAM (Minimo)
  execution_role_arn       = aws_iam_role.ecs_execution_role.arn
  task_role_arn            = aws_iam_role.ecs_task_role.arn

  container_definitions = jsonencode([
    {
      name      = "note-app"
      image     = "${aws_ecr_repository.repo.repository_url}:latest"
      essential = true
      portMappings = [
        {
          containerPort = 80
          hostPort      = 80
        }
      ]
      environment = [
        { name = "TABLE_NAME", value = aws_dynamodb_table.db.name }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.ecs_logs.name
          "awslogs-region"        = "eu-central-1"
          "awslogs-stream-prefix" = "ecs"
        }
      }
    }
  ])
}

# 5. IL SERVIZIO (Lancia il container)
resource "aws_ecs_service" "service" {
  name            = "registro-note-service"
  cluster         = aws_ecs_cluster.cluster.id
  task_definition = aws_ecs_task_definition.app.arn
  desired_count   = 1 # Ne lanciamo solo 1 per risparmiare
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = data.aws_subnets.default.ids
    security_groups  = [aws_security_group.ecs_sg.id]
    assign_public_ip = true # Fondamentale per raggiungerlo senza Load Balancer
  }
}

# Output per sapere l'URL dell'ECR (serve alla CI/CD)
output "ECR_REPO_URL" {
  value = aws_ecr_repository.repo.repository_url
}