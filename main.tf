terraform {
  backend "s3" {
    bucket = "terraform-state-cloud-registry-5780"  # <--- METTI IL TUO NOME BUCKET QUI
    key    = "stato-registro/terraform.tfstate" # Nome del file di memoria
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

  # Sintassi corretta
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
}

resource "aws_cognito_user_pool_client" "client" {
  name         = "RegistryClient"
  user_pool_id = aws_cognito_user_pool.pool.id
}

# 3. SNS
resource "aws_sns_topic" "topic" {
  name = "RegistryNotifications"
}

# 4. IAM ROLE (V7 - NOME NUOVO)
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

resource "aws_iam_role_policy" "lambda_policy" {
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

# 6. API GATEWAY (V5 - NOME NUOVO)
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
  statement_id  = "AllowAPI_v7" # ID UNIVOCO NUOVO
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.backend.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.api.execution_arn}/*/*"
}

# --- 7. S3 STATIC WEBSITE HOSTING ---

# Generiamo un nome univoco casuale per il bucket
resource "random_id" "bucket_suffix" {
  byte_length = 4
}

resource "aws_s3_bucket" "frontend" {
  bucket = "registro-cloud-frontend-${random_id.bucket_suffix.hex}"
  force_destroy = true # Permette di cancellare il bucket anche se pieno
}

# Configuriamo il bucket come sito web
resource "aws_s3_bucket_website_configuration" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  index_document {
    suffix = "index.html"
  }
}

# Rendiamo il bucket pubblico (necessario per static hosting semplice)
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

# 1. Carica index.html (File statico)
resource "aws_s3_object" "index" {
  bucket       = aws_s3_bucket.frontend.id
  key          = "index.html"
  source       = "index.html"
  content_type = "text/html"
  etag         = filemd5("index.html") # Ricarica se il file cambia
}

# 2. GENERA E CARICA config.js (File Dinamico)
resource "aws_s3_object" "config" {
  bucket       = aws_s3_bucket.frontend.id
  key          = "config.js"
  content_type = "application/javascript"
  
  # Qui avviene la magia: creiamo il contenuto del file al volo
  content = <<EOF
window.apiConfig = {
    UserPoolId: "${aws_cognito_user_pool.pool.id}",
    ClientId:   "${aws_cognito_user_pool_client.client.id}",
    ApiUrl:     "${aws_apigatewayv2_stage.stage.invoke_url}"
};
EOF
}

# --- NUOVO OUTPUT ---
output "SITO_WEB_URL" {
  value = "http://${aws_s3_bucket_website_configuration.frontend.website_endpoint}"
  description = "Clicca qui per vedere il sito funzionante"
}