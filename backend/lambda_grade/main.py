import json
import boto3
import os
import datetime

# Client AWS
dynamodb = boto3.resource('dynamodb')
sns = boto3.client('sns')

# Variabili d'ambiente passate da Terraform
TABLE_NAME = os.environ['TABLE_NAME']
SNS_TOPIC_ARN = os.environ['SNS_TOPIC_ARN']
table = dynamodb.Table(TABLE_NAME)

def lambda_handler(event, context):
    print("Evento ricevuto:", event)
    
    # Headers per CORS (fondamentale per far funzionare il frontend)
    headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Allow-Methods": "OPTIONS,POST"
    }

    try:
        # Gestione pre-flight request (CORS)
        if event['requestContext']['http']['method'] == 'OPTIONS':
            return {'statusCode': 200, 'headers': headers}

        # Parsing del body
        body = json.loads(event['body'])
        student_id = body.get('student_id')
        subject = body.get('subject')
        grade = body.get('grade')
        note = body.get('note', '') # Opzionale
        type_record = body.get('type', 'VOTO') # VOTO, NOTA, ASSENZA

        if not student_id or not subject:
            return {'statusCode': 400, 'headers': headers, 'body': json.dumps({'error': 'Dati mancanti'})}

        timestamp = datetime.datetime.now().isoformat()
        
        # Salvataggio su DynamoDB
        item = {
            'PK': f"STUDENT#{student_id}",
            'SK': f"{type_record}#{timestamp}",
            'Subject': subject,
            'Grade': str(grade) if grade else "N/A",
            'Note': note,
            'Date': timestamp,
            'Type': type_record
        }
        table.put_item(Item=item)
        
        # Invio Notifica SNS
        message_text = f"Nuovo inserimento nel registro.\nMateria: {subject}\nTipo: {type_record}\nValore: {grade if grade else note}"
        
        sns.publish(
            TopicArn=SNS_TOPIC_ARN,
            Message=message_text,
            Subject=f"CloudRegistry: Aggiornamento per {subject}"
        )
        
        return {
            'statusCode': 200,
            'headers': headers,
            'body': json.dumps({'message': 'Dati salvati e notifica inviata!'})
        }
        
    except Exception as e:
        print(f"Errore: {str(e)}")
        return {
            'statusCode': 500,
            'headers': headers,
            'body': json.dumps({'error': str(e)})
        }