provider "aws" {
  region = "eu-central-1"
}

# 1. DYNAMODB
resource "aws_dynamodb_table" "db" {
  name         = "CloudRegistryDB"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "PK"
  range_key    = "SK"
  attribute { name = "PK"; type = "S" }
  attribute { name = "SK"; type = "S" }
}

# 2. COGNITO
resource "aws_cognito_user_pool" "pool" {
  name = "RegistryPool"
  admin_create_user_config { allow_admin_create_user_only = false }
  
  schema {
    attribute_data_type = "String"
    name                = "role"
    mutable             = true
    string_attribute_constraints { min_length = 1; max_length = 20; }
  }
  schema {
    attribute_data_type = "String"
    name                = "classe"
    mutable             = true
    string_attribute_constraints { min_length = 1; max_length = 10; }
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

# 4. IAM ROLE (V5)
resource "aws_iam_role" "iam_for_lambda" {
  name = "iam_for_lambda_registry_v5" 
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{ Action = "sts:AssumeRole", Effect = "Allow", Principal = { Service = "lambda.amazonaws.com" } }]
  })
}

resource "aws_iam_role_policy" "lambda_policy" {
  name = "lambda_policy_v5"
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
      # NUOVO PERMESSO FONDAMENTALE: Leggere gli utenti
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
      # NUOVA VARIABILE
      USER_POOL_ID  = aws_cognito_user_pool.pool.id
    }
  }
}

# 6. API GATEWAY (V3)
resource "aws_apigatewayv2_api" "api" {
  name          = "RegistryAPI_v3"
  protocol_type = "HTTP"
  cors_configuration {
    allow_origins = ["*"]
    allow_methods = ["POST", "GET", "OPTIONS"]
    allow_headers = ["content-type", "authorization"]
    max_age       = 300
  }
}

resource "aws_apigatewayv2_stage" "stage" {
  api_id = aws_apigatewayv2_api.api.id
  name   = "$default"
  auto_deploy = true
}

resource "aws_apigatewayv2_integration" "integ" {
  api_id           = aws_apigatewayv2_api.api.id
  integration_type = "AWS_PROXY"
  integration_uri  = aws_lambda_function.backend.invoke_arn
}

resource "aws_apigatewayv2_route" "route" {
  api_id    = aws_apigateway