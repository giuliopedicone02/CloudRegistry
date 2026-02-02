import json
import boto3
import os
import datetime
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource('dynamodb')
sns = boto3.client('sns')

TABLE_NAME = os.environ.get('TABLE_NAME')
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN')

def lambda_handler(event, context):
    print("Evento:", event)
    
    # Gestione CORS per il browser
    headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'OPTIONS,POST,GET'
    }

    try:
        # Se è una chiamata GET (Lettura voti)
        if event['requestContext']['http']['method'] == 'GET':
            return gestisci_lettura(event, headers)

        # Se è una chiamata POST (Scrittura voto)
        if event['requestContext']['http']['method'] == 'POST':
            return gestisci_scrittura(event, headers)

    except Exception as e:
        print(f"Errore: {str(e)}")
        return {'statusCode': 500, 'headers': headers, 'body': json.dumps(f"Errore: {str(e)}")}

def gestisci_scrittura(event, headers):
    body = json.loads(event['body'])
    action = body.get('action')

    # Aggiungi Voto
    if action == 'add_grade':
        student_email = body['student_email']
        materia = body['materia']
        voto = float(body['voto'])
        teacher = body.get('teacher_email', 'Prof')

        table = dynamodb.Table(TABLE_NAME)
        timestamp = datetime.datetime.now().isoformat()
        
        # Salviamo su DynamoDB
        # PK = EMAIL_STUDENTE (così possiamo trovare tutti i voti di uno studente)
        item = {
            'PK': f"STUDENT#{student_email}",
            'SK': f"VOTO#{timestamp}",
            'materia': materia,
            'voto': str(voto),
            'data': timestamp,
            'teacher': teacher
        }
        table.put_item(Item=item)

        # Notifica SNS
        msg = f"Nuovo voto per {student_email}: {voto} in {materia}"
        sns.publish(TopicArn=SNS_TOPIC_ARN, Message=msg, Subject="Nuovo Voto")

        return {'statusCode': 200, 'headers': headers, 'body': json.dumps({'message': 'Voto inserito!'})}

def gestisci_lettura(event, headers):
    # Recuperiamo l'email dalla query string ?email=...
    params = event.get('queryStringParameters', {})
    student_email = params.get('email')

    if not student_email:
        return {'statusCode': 400, 'headers': headers, 'body': json.dumps("Manca l'email")}

    table = dynamodb.Table(TABLE_NAME)
    
    # Cerchiamo tutti i record che iniziano con PK = STUDENT#email
    response = table.query(
        KeyConditionExpression=Key('PK').eq(f"STUDENT#{student_email}")
    )
    
    items = response.get('Items', [])
    
    # Calcolo Medie
    voti_per_materia = {}
    for item in items:
        mat = item['materia']
        val = float(item['voto'])
        if mat not in voti_per_materia:
            voti_per_materia[mat] = []
        voti_per_materia[mat].append(val)
        
    medie = {}
    for mat, lista_voti in voti_per_materia.items():
        medie[mat] = round(sum(lista_voti) / len(lista_voti), 1)

    return {
        'statusCode': 200, 
        'headers': headers, 
        'body': json.dumps({'voti': items, 'medie': medie})
    }