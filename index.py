import json
import boto3
import os
import datetime
import traceback
from boto3.dynamodb.conditions import Key

# --- INIZIALIZZAZIONE SERVIZI ---
dynamodb = boto3.resource('dynamodb')
ses = boto3.client('ses')    # ✅ Usiamo SES (Postino) per mail dirette
cognito = boto3.client('cognito-idp')

# --- CONFIGURAZIONE ---
TABLE_NAME = os.environ.get('TABLE_NAME')
USER_POOL_ID = os.environ.get('USER_POOL_ID')

# ⚠️ SOSTITUISCI CON LA TUA MAIL VERIFICATA SU SES
SENDER_EMAIL = "pediconegiulio02@gmail.com" 

def lambda_handler(event, context):
    print("Evento:", json.dumps(event))
    
    headers = {
        'Content-Type': 'application/json',
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'OPTIONS,POST,GET'
    }

    try:
        http_method = None
        if 'requestContext' in event and 'http' in event['requestContext']:
            http_method = event['requestContext']['http'].get('method')
        if not http_method:
            http_method = event.get('httpMethod')

        if http_method == 'GET':
            return gestisci_lettura(event, headers)

        if http_method == 'POST':
            return gestisci_scrittura(event, headers)
            
        return {'statusCode': 400, 'headers': headers, 'body': json.dumps("Metodo non supportato")}

    except Exception as e:
        return {'statusCode': 500, 'headers': headers, 'body': json.dumps({"error": str(e), "trace": traceback.format_exc()})}

def gestisci_scrittura(event, headers):
    body = event.get('body')
    if isinstance(body, str): body = json.loads(body)
    
    action = body.get('action')

    # --- 1. SCARICA LISTA STUDENTI ---
    if action == 'get_students':
        try:
            response = cognito.list_users(UserPoolId=USER_POOL_ID)
            students = []
            classes_set = set()
            
            for user in response['Users']:
                attrs = {a['Name']: a['Value'] for a in user['Attributes']}
                if attrs.get('custom:role') == 'Student':
                    classe = attrs.get('custom:classe', 'N/A')
                    nome = attrs.get('given_name', '')
                    cognome = attrs.get('family_name', '')
                    if classe != 'N/A': classes_set.add(classe)

                    students.append({
                        'email': attrs.get('email'),
                        'nome': nome,
                        'cognome': cognome,
                        'classe': classe,
                        'display_name': f"{cognome} {nome}" if nome else attrs.get('email')
                    })
            
            sorted_classes = sorted(list(classes_set))
            students.sort(key=lambda x: x['cognome'])
            
            return {'statusCode': 200, 'headers': headers, 'body': json.dumps({
                'students': students, 
                'classes': sorted_classes
            })}
        except Exception as e:
            return {'statusCode': 500, 'headers': headers, 'body': json.dumps(str(e))}

    # --- 2. AGGIUNGI VOTO E INVIA MAIL ---
    if action == 'add_grade':
        student_email = body.get('student_email')
        materia = body.get('materia')
        voto_raw = body.get('voto')
        teacher_name = body.get('teacher_name', 'Docente')

        # A. Salva nel Database
        table = dynamodb.Table(TABLE_NAME)
        timestamp = datetime.datetime.now().isoformat()
        
        item = {
            'PK': f"STUDENT#{student_email}",
            'SK': f"VOTO#{timestamp}",
            'materia': materia,
            'voto': str(voto_raw),
            'data': timestamp,
            'teacher': teacher_name
        }
        table.put_item(Item=item)

        # B. Invia Email con SES (Diretta allo studente)
        try:
            subject = f"Nuovo Voto in {materia} - Registro Cloud"
            messaggio = (
                f"Ciao,\n\n"
                f"È stato inserito un nuovo voto sul tuo Registro Cloud.\n\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                f"📚 Materia: {materia}\n"
                f"📊 Voto: {voto_raw}\n"
                f"👨‍🏫 Docente: {teacher_name}\n"
                f"📅 Data: {timestamp[:10]}\n"
                f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"Accedi al portale per vedere la tua media aggiornata."
            )

            ses.send_email(
                Source=SENDER_EMAIL,
                Destination={
                    'ToAddresses': [student_email] # ✅ Manda SOLO a lui!
                },
                Message={
                    'Subject': {'Data': subject},
                    'Body': {'Text': {'Data': messaggio}}
                }
            )
            print(f"✅ Email SES inviata con successo a {student_email}")
            
        except Exception as mail_error:
            print(f"❌ Errore invio Email SES: {mail_error}")
            traceback.print_exc()

        return {'statusCode': 200, 'headers': headers, 'body': json.dumps({'message': 'Voto inserito!'})}

def gestisci_lettura(event, headers):
    params = event.get('queryStringParameters') or {}
    student_email = params.get('email')

    if not student_email: return {'statusCode': 400, 'headers': headers, 'body': json.dumps("No email")}

    table = dynamodb.Table(TABLE_NAME)
    response = table.query(KeyConditionExpression=Key('PK').eq(f"STUDENT#{student_email}"))
    items = response.get('Items', [])
    
    voti_per_materia = {}
    for item in items:
        mat = item.get('materia', 'Sconosciuta')
        val = float(item.get('voto', 0))
        if mat not in voti_per_materia: voti_per_materia[mat] = []
        voti_per_materia[mat].append(val)
        
    medie = {mat: round(sum(l)/len(l), 1) for mat, l in voti_per_materia.items()}

    return {'statusCode': 200, 'headers': headers, 'body': json.dumps({'voti': items, 'medie': medie})}