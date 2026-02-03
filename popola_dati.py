import boto3
import time
import random
from datetime import datetime

# --- CONFIGURAZIONE ---
USER_POOL_ID = "INCOLLA_TUO_POOL_ID" 
TABLE_NAME = "CloudRegistryDB_Final" # Assicurati sia quello giusto (Plan output)
REGION = "eu-central-1"
PASSWORD_DEFAULT = "Password123!"
# ----------------------

cognito = boto3.client('cognito-idp', region_name=REGION)
dynamodb = boto3.resource('dynamodb', region_name=REGION)
table = dynamodb.Table(TABLE_NAME)

# Studenti con NOME e COGNOME
studenti_finti = [
    {"nome": "Mario",   "cognome": "Rossi",   "email": "mario.rossi@scuola.it",   "classe": "5A"},
    {"nome": "Luigi",   "cognome": "Verdi",   "email": "luigi.verdi@scuola.it",   "classe": "5A"},
    {"nome": "Anna",    "cognome": "Bianchi", "email": "anna.bianchi@scuola.it",  "classe": "5A"},
    {"nome": "Sofia",   "cognome": "Neri",    "email": "sofia.neri@scuola.it",    "classe": "5B"},
    {"nome": "Luca",    "cognome": "Gialli",  "email": "luca.gialli@scuola.it",   "classe": "5B"},
    {"nome": "Giulia",  "cognome": "Blu",     "email": "giulia.blu@scuola.it",    "classe": "3C"}
]

# Creiamo anche il DOCENTE
docente = {"nome": "Giuseppe", "cognome": "Conte", "email": "preside@scuola.it"}

materie = ["Matematica", "Storia", "Italiano", "Inglese", "Informatica"]

def crea_utente(user, role):
    email = user['email']
    print(f"🔨 Creazione {role}: {user['nome']} {user['cognome']}...")
    
    attrs = [
        {'Name': 'email', 'Value': email},
        {'Name': 'given_name', 'Value': user['nome']},
        {'Name': 'family_name', 'Value': user['cognome']},
        {'Name': 'custom:role', 'Value': role},
        {'Name': 'email_verified', 'Value': 'true'}
    ]
    
    if role == 'Student':
        attrs.append({'Name': 'custom:classe', 'Value': user['classe']})
    else:
        attrs.append({'Name': 'custom:classe', 'Value': 'N/A'})

    try:
        cognito.admin_create_user(
            UserPoolId=USER_POOL_ID,
            Username=email,
            UserAttributes=attrs,
            MessageAction='SUPPRESS'
        )
        cognito.admin_set_user_password(
            UserPoolId=USER_POOL_ID, Username=email, Password=PASSWORD_DEFAULT, Permanent=True
        )
        print(f"✅ OK")
        return True
    except cognito.exceptions.UsernameExistsException:
        print(f"⚠️  Esiste già.")
        return True
    except Exception as e:
        print(f"❌ Errore: {e}")
        return False

def inserisci_voti(email):
    for _ in range(3):
        materia = random.choice(materie)
        item = {
            'PK': f"STUDENT#{email}",
            'SK': f"VOTO#{datetime.now().isoformat()}#{random.randint(100,999)}",
            'materia': materia,
            'voto': str(random.randint(4, 10)),
            'data': datetime.now().isoformat(),
            'teacher': 'Prof. Giuseppe Conte'
        }
        try: table.put_item(Item=item)
        except: pass

print("--- START ---")
# Crea Docente
crea_utente(docente, 'Teacher')

# Crea Studenti
for s in studenti_finti:
    if crea_utente(s, 'Student'):
        inserisci_voti(s['email'])
        time.sleep(0.2)

print("\n--- FATTO ---")