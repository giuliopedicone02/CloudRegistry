resource "aws_cognito_user_pool" "pool" {
  name = "cloud-registry-user-pool"

  password_policy {
    minimum_length = 8
  }

  schema {
    attribute_data_type      = "String"
    name                     = "role"
    mutable                  = true
  }
}

resource "aws_cognito_user_group" "teachers" {
  name         = "Teachers"
  user_pool_id = aws_cognito_user_pool.pool.id
}

resource "aws_cognito_user_group" "students" {
  name         = "Students"
  user_pool_id = aws_cognito_user_pool.pool.id
}

resource "aws_cognito_user_pool_client" "client" {
  name         = "registry-app-client"
  user_pool_id = aws_cognito_user_pool.pool.id
}