import json
import boto3
import os
from datetime import datetime

dynamodb = boto3.resource('dynamodb')
sns = boto3.client('sns')

TABLE_NAME = os.environ['TABLE_NAME']
TOPIC_ARN = os.environ['SNS_TOPIC_ARN']

def lambda_handler(event, context):
    table = dynamodb.Table(TABLE_NAME)
    
    # Decodifica input (voto, studente, materia)
    body = json.loads(event['body'])
    student_id = body['student_id']
    valore_voto = body['voto']
    materia = body['materia']
    
    # 1. Salva su DynamoDB
    item = {
        'PK': f"STUDENT#{student_id}",
        'SK': f"GRADE#{datetime.now().isoformat()}",
        'materia': materia,
        'voto': valore_voto,
        'data': datetime.now().strftime("%Y-%m-%d")
    }
    table.put_item(Item=item)
    
    # 2. Invia Notifica SNS
    message = f"Nuovo voto inserito in {materia}: {valore_voto}"
    sns.publish(
        TopicArn=TOPIC_ARN,
        Message=message,
        Subject="Nuovo aggiornamento Registro Elettronico"
    )
    
    return {
        'statusCode': 200,
        'body': json.dumps({'message': 'Voto inserito e notifica inviata!'})
    }