import json
import boto3
import os
import datetime
import traceback
from boto3.dynamodb.conditions import Key

# --- INIZIALIZZAZIONE SERVIZI ---
dynamodb = boto3.resource('dynamodb')
# ses = boto3.client('ses') # RIMOSSO: Usiamo SNS
sns = boto3.client('sns')   # NUOVO: Client SNS
cognito = boto3.client('cognito-idp')
ecs = boto3.client('ecs')
ec2 = boto3.client('ec2')

# --- CONFIGURAZIONE ---
TABLE_NAME = os.environ.get('TABLE_NAME')
USER_POOL_ID = os.environ.get('USER_POOL_ID')
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN') # Assicurati che Terraform passi questa variabile
CLUSTER_NAME = "registro-cloud-cluster" 

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

    # --- AZIONE 1: TROVA IP DOCKER ---
    if action == 'get_container_ip':
        try:
            tasks = ecs.list_tasks(cluster=CLUSTER_NAME, desiredStatus='RUNNING')
            task_arns = tasks.get('taskArns', [])

            if not task_arns:
                return {'statusCode': 200, 'headers': headers, 'body': json.dumps({'ip': None, 'error': 'Nessun container acceso trovato'})}

            desc = ecs.describe_tasks(cluster=CLUSTER_NAME, tasks=[task_arns[0]])
            if not desc['tasks']:
                 return {'statusCode': 200, 'headers': headers, 'body': json.dumps({'ip': None, 'error': 'Impossibile descrivere il task'})}
                 
            task_details = desc['tasks'][0]
            eni_id = None
            if 'attachments' in task_details and len(task_details['attachments']) > 0:
                for detail in task_details['attachments'][0]['details']:
                    if detail['name'] == 'networkInterfaceId':
                        eni_id = detail['value']
                        break
            
            if not eni_id:
                return {'statusCode': 200, 'headers': headers, 'body': json.dumps({'ip': None, 'error': 'ENI non trovata'})}

            net_info = ec2.describe_network_interfaces(NetworkInterfaceIds=[eni_id])
            public_ip = net_info['NetworkInterfaces'][0].get('Association', {}).get('PublicIp')

            return {'statusCode': 200, 'headers': headers, 'body': json.dumps({'ip': public_ip})}

        except Exception as e:
            print("Errore ricerca IP:", str(e))
            traceback.print_exc()
            return {'statusCode': 500, 'headers': headers, 'body': json.dumps({'error': str(e)})}

    # --- AZIONE 2: GET STUDENTS ---
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

    # --- AZIONE 3: SUBSCRIBE STUDENT (NUOVA) ---
    if action == 'subscribe_student':
        student_email = body.get('email')
        
        if not student_email:
            return {'statusCode': 400, 'headers': headers, 'body': json.dumps("Email mancante")}
        
        try:
            if SNS_TOPIC_ARN:
                filter_policy = {
                    "target_email": [student_email]
                }
                
                print(f"Iscrizione SNS per nuovo studente: {student_email}")
                sns.subscribe(
                    TopicArn=SNS_TOPIC_ARN,
                    Protocol='email',
                    Endpoint=student_email,
                    Attributes={
                        'FilterPolicy': json.dumps(filter_policy)
                    }
                )
                return {'statusCode': 200, 'headers': headers, 'body': json.dumps({'message': 'Iscrizione richiesta. Controlla la tua email per confermare.'})}
            else:
                return {'statusCode': 500, 'headers': headers, 'body': json.dumps("SNS_TOPIC_ARN non configurato")}
        except Exception as e:
            print(f"Errore subscribe SNS: {e}")
            return {'statusCode': 500, 'headers': headers, 'body': json.dumps(str(e))}

    # --- AZIONE 4: ADD GRADE ---
    if action == 'add_grade':
        student_email = body.get('student_email')
        materia = body.get('materia')
        voto_raw = body.get('voto')
        teacher_name = body.get('teacher_name', 'Docente')

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

        # --- INVIO NOTIFICA SNS ---
        try:
            subject = f"Nuovo Voto in {materia}"
            messaggio = f"Ciao, hai ricevuto un nuovo voto: {voto_raw} in {materia}.\nDocente: {teacher_name}"
            
            if SNS_TOPIC_ARN:
                print(f"Invio notifica SNS a: {student_email}")
                sns.publish(
                    TopicArn=SNS_TOPIC_ARN,
                    Message=messaggio,
                    Subject=subject,
                    MessageAttributes={
                        'target_email': {
                            'DataType': 'String',
                            'StringValue': student_email
                        }
                    }
                )
            else:
                print("ERRORE: SNS_TOPIC_ARN non configurato nelle variabili d'ambiente")

        except Exception as e:
            print(f"Errore invio SNS: {e}")
            
        return {'statusCode': 200, 'headers': headers, 'body': json.dumps({'message': 'Voto inserito e notifica inviata!'})}

    # --- AZIONE: DELETE GRADE ---
    if action == 'delete_grade':
        student_email = body.get('student_email')
        timestamp_sk = body.get('sk') 

        if not student_email or not timestamp_sk:
             return {'statusCode': 400, 'headers': headers, 'body': json.dumps("Dati mancanti")}

        table = dynamodb.Table(TABLE_NAME)
        
        try:
            table.delete_item(
                Key={
                    'PK': f"STUDENT#{student_email}",
                    'SK': timestamp_sk
                }
            )
            return {'statusCode': 200, 'headers': headers, 'body': json.dumps({'message': 'Voto eliminato'})}
        except Exception as e:
            print(f"Errore cancellazione: {str(e)}")
            return {'statusCode': 500, 'headers': headers, 'body': json.dumps(str(e))}

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