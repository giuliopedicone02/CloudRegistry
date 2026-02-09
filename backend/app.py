from flask import Flask, request, jsonify
from flask_cors import CORS
import boto3
import os
import datetime
from boto3.dynamodb.conditions import Key

app = Flask(__name__)
CORS(app) 

# Configurazione DynamoDB
TABLE_NAME = os.environ.get('TABLE_NAME', 'CloudRegistryDB')
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN')  

dynamodb = boto3.resource('dynamodb', region_name='eu-central-1')
table = dynamodb.Table(TABLE_NAME)
sns = boto3.client('sns', region_name='eu-central-1') 

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy", "service": "Note Disciplinari"}), 200

# GET: Leggi le note
@app.route('/note', methods=['GET'])
def get_notes():
    email = request.args.get('email')
    if not email: return jsonify({"error": "Manca email"}), 400
    try:
        response = table.query(
            KeyConditionExpression=Key('PK').eq(f"STUDENT#{email}") & Key('SK').begins_with("NOTA#")
        )
        return jsonify(response.get('Items', [])), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# POST: Aggiungi nota
@app.route('/note', methods=['POST'])
def add_note():
    data = request.json
    student_email = data.get('student_email')
    testo = data.get('testo')
    teacher = data.get('teacher', 'Docente')
    
    item = {
        'PK': f"STUDENT#{student_email}",
        'SK': f"NOTA#{datetime.datetime.now().isoformat()}",
        'tipo': 'NOTA',
        'testo': testo,
        'data': datetime.datetime.now().isoformat(),
        'teacher': teacher
    }
    
    try:
        # Salva la nota su DynamoDB
        table.put_item(Item=item)
        
        if SNS_TOPIC_ARN:
            try:
                subject = "⚠️ Nuova Nota Disciplinare"
                message = f"Hai ricevuto una nuova nota disciplinare.\n\nMotivo: {testo}\n\nDocente: {teacher}"
                
                print(f"Invio notifica SNS per nota a: {student_email}")
                sns.publish(
                    TopicArn=SNS_TOPIC_ARN,
                    Message=message,
                    Subject=subject,
                    MessageAttributes={
                        'target_email': {
                            'DataType': 'String',
                            'StringValue': student_email
                        }
                    }
                )
                print(f"Notifica SNS inviata con successo a {student_email}")
            except Exception as e:
                print(f"Errore invio SNS per nota: {e}")
        else:
            print("ATTENZIONE: SNS_TOPIC_ARN non configurato, nessuna notifica inviata")
        
        return jsonify({"message": "Nota inserita e notifica inviata"}), 201
        
    except Exception as e:
        print(f"Errore inserimento nota: {e}")
        return jsonify({"error": str(e)}), 500

# DELETE: Elimina nota
@app.route('/note', methods=['DELETE'])
def delete_note():
    data = request.json
    try:
        table.delete_item(
            Key={
                'PK': f"STUDENT#{data.get('student_email')}",
                'SK': data.get('sk')
            }
        )
        return jsonify({"message": "Nota eliminata"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=80)