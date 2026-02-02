import json
import boto3
import os
import datetime

# Clienti AWS
dynamodb = boto3.resource('dynamodb')
sns = boto3.client('sns')

# Variabili d'ambiente passate da Terraform
TABLE_NAME = os.environ.get('TABLE_NAME')
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN')

def lambda_handler(event, context):
    print("Evento ricevuto:", event) # Per debug nei log
    
    try:
        # 1. Parsing del body
        if 'body' in event:
            body = json.loads(event['body'])
        else:
            body = event # Fallback per test diretti

        student_id = body.get('student_id')
        materia = body.get('materia')
        voto = body.get('voto')
        
        if not student_id or not voto:
            return {'statusCode': 400, 'body': json.dumps('Dati mancanti')}

        # 2. Scrittura su DynamoDB
        table = dynamodb.Table(TABLE_NAME)
        timestamp = datetime.datetime.now().isoformat()
        
        item = {
            'PK': f"STUDENT#{student_id}",
            'SK': f"VOTO#{timestamp}",
            'materia': materia,
            'voto': str(voto),
            'data': timestamp
        }
        
        table.put_item(Item=item)

        # 3. Invio Notifica SNS (Email)
        message = f"Nuovo voto registrato per {student_id} in {materia}: {voto}"
        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Message=message,
            Subject="Notifica Registro Elettronico"
        )

        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({'message': 'Voto salvato e notifica inviata via email!', 'id': student_id})
        }

    except Exception as e:
        print(e)
        return {'statusCode': 500, 'body': json.dumps(f"Errore interno: {str(e)}")}