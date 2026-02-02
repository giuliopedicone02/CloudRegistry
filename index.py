import json
import boto3
import os
import datetime
import traceback # <--- Aggiunto per tracciare l'errore esatto
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource('dynamodb')
sns = boto3.client('sns')

TABLE_NAME = os.environ.get('TABLE_NAME')
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN')

def lambda_handler(event, context):
    print("Evento:", event)
    
    headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'OPTIONS,POST,GET'
    }

    try:
        # Gestione robusta per i parametri mancanti
        http_method = event.get('requestContext', {}).get('http', {}).get('method')
        
        if http_method == 'GET':
            return gestisci_lettura(event, headers)

        if http_method == 'POST':
            return gestisci_scrittura(event, headers)
            
        return {'statusCode': 400, 'headers': headers, 'body': json.dumps("Metodo non supportato")}

    except Exception as e:
        # DEBUG MODE: Restituiamo l'errore completo al frontend invece di crashare
        error_message = traceback.format_exc()
        print(f"CRASH LAMBDA: {error_message}")
        return {
            'statusCode': 500, 
            'headers': headers, 
            'body': json.dumps({
                "error": "Errore interno del server",
                "details": str(e),
                "trace": error_message
            })
        }

def gestisci_scrittura(event, headers):
    if not event.get('body'):
        return {'statusCode': 400, 'headers': headers, 'body': json.dumps("Body mancante")}
        
    body = json.loads(event['body'])
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

        # Notifica SNS (Avvolta in try per evitare blocchi se SNS fallisce)
        try:
            msg = f"Nuovo voto per {student_email}: {voto_raw} in {materia}"
            sns.publish(TopicArn=SNS_TOPIC_ARN, Message=msg, Subject="Nuovo Voto")
        except Exception as sns_error:
            print(f"Errore SNS: {sns_error}")

        return {'statusCode': 200, 'headers': headers, 'body': json.dumps({'message': 'Voto inserito!'})}

def gestisci_lettura(event, headers):
    # Gestione sicura dei parametri
    params = event.get('queryStringParameters') or {}
    student_email = params.get('email')

    if not student_email:
        return {'statusCode': 400, 'headers': headers, 'body': json.dumps("Manca l'email nella richiesta")}

    table = dynamodb.Table(TABLE_NAME)
    
    # QUI E' DOVE PROBABILMENTE FALLISCE SE MANCANO PERMESSI
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