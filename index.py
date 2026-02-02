import json
import boto3
import os
import datetime
import traceback
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource('dynamodb')
sns = boto3.client('sns')

TABLE_NAME = os.environ.get('TABLE_NAME')
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN')

def lambda_handler(event, context):
    print("Evento ricevuto:", json.dumps(event)) # Log completo per debug
    
    headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'OPTIONS,POST,GET'
    }

    try:
        # --- FIX ROBUSTEZZA: Supportiamo sia API Gateway v1 che v2 ---
        http_method = None
        
        # Tentativo 1: Formato v2 (requestContext -> http -> method)
        if 'requestContext' in event and 'http' in event['requestContext']:
            http_method = event['requestContext']['http'].get('method')
        
        # Tentativo 2: Formato v1 (httpMethod diretto nella root)
        if not http_method:
            http_method = event.get('httpMethod')
            
        # Tentativo 3: Formato v1 alternativo (requestContext -> httpMethod)
        if not http_method and 'requestContext' in event:
            http_method = event['requestContext'].get('httpMethod')

        print(f"Metodo rilevato: {http_method}")

        if http_method == 'GET':
            return gestisci_lettura(event, headers)

        if http_method == 'POST':
            return gestisci_scrittura(event, headers)
            
        return {'statusCode': 400, 'headers': headers, 'body': json.dumps(f"Metodo non supportato o non trovato. Evento: {str(event)}")}

    except Exception as e:
        error_message = traceback.format_exc()
        print(f"CRASH LAMBDA: {error_message}")
        return {
            'statusCode': 500, 
            'headers': headers, 
            'body': json.dumps({
                "error": "Errore interno del server",
                "message": str(e),
                "trace": error_message
            })
        }

def gestisci_scrittura(event, headers):
    # Gestione Body anche se arriva come stringa JSON
    body = event.get('body')
    if isinstance(body, str):
        body = json.loads(body)
    
    if not body:
         return {'statusCode': 400, 'headers': headers, 'body': json.dumps("Body mancante")}

    action = body.get('action')

    if action == 'add_grade':
        student_email = body.get('student_email')
        materia = body.get('materia')
        voto_raw = body.get('voto')
        teacher = body.get('teacher_email', 'Prof')

        if not student_email or not materia or not voto_raw:
             return {'statusCode': 400, 'headers': headers, 'body': json.dumps("Dati incompleti")}

        table = dynamodb.Table(TABLE_NAME)
        timestamp = datetime.datetime.now().isoformat()
        
        item = {
            'PK': f"STUDENT#{student_email}",
            'SK': f"VOTO#{timestamp}",
            'materia': materia,
            'voto': str(voto_raw),
            'data': timestamp,
            'teacher': teacher
        }
        table.put_item(Item=item)

        try:
            msg = f"Nuovo voto per {student_email}: {voto_raw} in {materia}"
            sns.publish(TopicArn=SNS_TOPIC_ARN, Message=msg, Subject="Nuovo Voto")
        except Exception as sns_error:
            print(f"Errore SNS: {sns_error}")

        return {'statusCode': 200, 'headers': headers, 'body': json.dumps({'message': 'Voto inserito!'})}

def gestisci_lettura(event, headers):
    # Gestione Parametri query string (v1 e v2)
    params = event.get('queryStringParameters') or {}
    student_email = params.get('email')

    if not student_email:
        return {'statusCode': 400, 'headers': headers, 'body': json.dumps("Manca l'email nella richiesta")}

    table = dynamodb.Table(TABLE_NAME)
    
    response = table.query(
        KeyConditionExpression=Key('PK').eq(f"STUDENT#{student_email}")
    )
    
    items = response.get('Items', [])
    
    voti_per_materia = {}
    for item in items:
        mat = item.get('materia', 'Sconosciuta')
        val = float(item.get('voto', 0))
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