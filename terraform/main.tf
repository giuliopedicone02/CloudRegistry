# Ruolo IAM per la Lambda
resource "aws_iam_role" "lambda_role" {
  name = "cloud_registry_lambda_role"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

# Policy per permettere alla Lambda di scrivere su DynamoDB e SNS
resource "aws_iam_role_policy" "lambda_policy" {
  role = aws_iam_role.lambda_role.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = ["dynamodb:PutItem", "dynamodb:GetItem", "dynamodb:Query"]
        Effect = "Allow"
        Resource = "*"
      },
      {
        Action = ["sns:Publish"]
        Effect = "Allow"
        Resource = "*"
      }
    ]
  })
}

# La risorsa Lambda vera e propria
resource "aws_lambda_function" "registry_lambda" {
  filename      = "dummy_payload.zip" # Terraform ha bisogno di un file iniziale
  function_name = "CloudRegistry_Logic"
  role          = aws_iam_role.lambda_role.arn
  handler       = "lambda_function.lambda_handler"
  runtime       = "python3.9"

  environment {
    variables = {
      TABLE_NAME     = aws_dynamodb_table.cloud_registry_db.name
      SNS_TOPIC_ARN  = aws_sns_topic.registry_notifications.arn
    }
  }
}