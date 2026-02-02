provider "aws" {
  region = "us-east-1"
}

# --- 1. DYNAMODB (Database - Configurazione Free Tier Sicura) ---
resource "aws_dynamodb_table" "registry_table" {
  name           = "CloudRegistryData"
  billing_mode   = "PROVISIONED" # Impostato su Provisioned per sicurezza Free Tier
  read_capacity  = 5             # Max 25 unità gratis
  write_capacity = 5             # Max 25 unità gratis
  hash_key       = "PK"
  range_key      = "SK"

  attribute {
    name = "PK"
    type = "S"
  }
  attribute {
    name = "SK"
    type = "S"
  }
}

# --- 2. COGNITO (Login Utenti) ---
resource "aws_cognito_user_pool" "pool" {
  name = "cloudregistry-pool"
  
  password_policy {
    minimum_length = 8
    require_lowercase = true
    require_numbers = true
  }
}

resource "aws_cognito_user_pool_client" "client" {
  name = "cloudregistry-app-client"
  user_pool_id = aws_cognito_user_pool.pool.id
  explicit_auth_flows = ["ALLOW_USER_PASSWORD_AUTH", "ALLOW_REFRESH_TOKEN_AUTH", "ALLOW_USER_SRP_AUTH"]
}

# --- 3. SNS (Notifiche Email) ---
resource "aws_sns_topic" "alerts" {
  name = "student-alerts-topic"
}

# --- 4. LAMBDA (Backend) ---

# Creazione automatica dello ZIP del codice Python
data "archive_file" "lambda_zip" {
  type        = "zip"
  source_dir  = "../backend/lambda_grade"
  output_path = "lambda_function_payload.zip"
}

# Ruolo IAM per la Lambda
resource "aws_iam_role" "lambda_role" {
  name = "cloudregistry_lambda_role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{ Action = "sts:AssumeRole", Effect = "Allow", Principal = { Service = "lambda.amazonaws.com" } }]
  })
}

# Gruppo di Log CloudWatch (Per risparmiare costi, cancella log dopo 7 giorni)
resource "aws_cloudwatch_log_group" "lambda_log_group" {
  name              = "/aws/lambda/CloudRegistry_AddGrade"
  retention_in_days = 7
}

# Permessi per la Lambda (Logs, DynamoDB, SNS)
resource "aws_iam_policy" "lambda_policy" {
  name = "cloudregistry_lambda_policy"
  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      { Action = ["dynamodb:PutItem", "dynamodb:Query"], Effect = "Allow", Resource = aws_dynamodb_table.registry_table.arn },
      { Action = ["sns:Publish"], Effect = "Allow", Resource = aws_sns_topic.alerts.arn },
      { Action = ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents"], Effect = "Allow", Resource = "*" }
    ]
  })
}

resource "aws_iam_role_policy_attachment" "attach_policy" {
  role       = aws_iam_role.lambda_role.name
  policy_arn = aws_iam_policy.lambda_policy.arn
}

# Funzione Lambda con DEPENDS_ON per evitare il blocco
resource "aws_lambda_function" "grade_handler" {
  filename         = data.archive_file.lambda_zip.output_path
  function_name    = "CloudRegistry_AddGrade"
  role             = aws_iam_role.lambda_role.arn
  handler          = "main.lambda_handler"
  runtime          = "python3.9"
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  timeout          = 10

  environment {
    variables = {
      TABLE_NAME = aws_dynamodb_table.registry_table.name
      SNS_TOPIC_ARN = aws_sns_topic.alerts.arn
    }
  }

  # FONDAMENTALE: Aspetta che ruolo e log group siano pronti prima di creare la funzione
  depends_on = [
    aws_iam_role_policy_attachment.attach_policy,
    aws_cloudwatch_log_group.lambda_log_group
  ]
}

# --- 5. API GATEWAY (Punto di accesso Web) ---
resource "aws_apigatewayv2_api" "http_api" {
  name          = "cloudregistry-api"
  protocol_type = "HTTP"
  
  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["POST", "GET", "OPTIONS"]
    allow_headers = ["content-type"]
  }
}

resource "aws_apigatewayv2_stage" "default" {
  api_id = aws_apigatewayv2_api.http_api.id
  name   = "$default"
  auto_deploy = true
}

resource "aws_apigatewayv2_integration" "lambda_int" {
  api_id           = aws_apigatewayv2_api.http_api.id
  integration_type = "AWS_PROXY"
  integration_uri  = aws_lambda_function.grade_handler.invoke_arn
}

# Rotta POST
resource "aws_apigatewayv2_route" "post_grade" {
  api_id    = aws_apigatewayv2_api.http_api.id
  route_key = "POST /grades"
  target    = "integrations/${aws_apigatewayv2_integration.lambda_int.id}"
}

# Permesso API Gateway -> Lambda
resource "aws_lambda_permission" "api_gw" {
  statement_id  = "AllowExecutionFromAPIGateway"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.grade_handler.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.http_api.execution_arn}/*/*"
}

# --- OUTPUTS (Dati da usare nel frontend) ---
output "api_url" {
  value = aws_apigatewayv2_stage.default.invoke_url
}

output "cognito_user_pool_id" {
  value = aws_cognito_user_pool.pool.id
}

output "cognito_client_id" {
  value = aws_cognito_user_pool_client.client.id
}