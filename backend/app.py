from flask import Flask, request, jsonify
from flask_cors import CORS
import boto3
import os
import datetime
from boto3.dynamodb.conditions import Key

app = Flask(__name__)
CORS(app) # Abilita chiamate dal frontend

# Configurazione DynamoDB (prende il nome tabella dalle variabili d'ambiente)
TABLE_NAME = os.environ.get('TABLE_NAME', 'CloudRegistryDB')
dynamodb = boto3.resource('dynamodb', region_name='eu-central-1')
table = dynamodb.Table(TABLE_NAME)

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "healthy", "service": "Note Disciplinari"}), 200

# GET: Leggi le note di uno studente
@app.route('/note', methods=['GET'])
def get_notes():
    email = request.args.get('email')
    if not email:
        return jsonify({"error": "Manca email studente"}), 400

    try:
        # Le note sono salvate con PK=STUDENT#email e SK che inizia con NOTA#
        response = table.query(
            KeyConditionExpression=Key('PK').eq(f"STUDENT#{email}") & Key('SK').begins_with("NOTA#")
        )
        return jsonify(response.get('Items', [])), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# POST: Aggiungi una nota
@app.route('/note', methods=['POST'])
def add_note():
    data = request.json
    student_email = data.get('student_email')
    testo = data.get('testo')
    teacher = data.get('teacher', 'Docente')

    if not student_email or not testo:
        return jsonify({"error": "Dati mancanti"}), 400

    timestamp = datetime.datetime.now().isoformat()
    
    item = {
        'PK': f"STUDENT#{student_email}",
        'SK': f"NOTA#{timestamp}",
        'tipo': 'NOTA',
        'testo': testo,
        'data': timestamp,
        'teacher': teacher
    }

    try:
        table.put_item(Item=item)
        return jsonify({"message": "Nota inserita", "nota": item}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    # Ascolta su tutte le interfacce sulla porta 80
    app.run(host='0.0.0.0', port=80)

# DELETE: Rimuovi una nota
@app.route('/note', methods=['DELETE'])
def delete_note():
    # Flask legge il body anche nelle DELETE se glielo mandiamo
    data = request.json
    student_email = data.get('student_email')
    note_sk = data.get('sk') # L'SK della nota (es. NOTA#2024-05...)

    if not student_email or not note_sk:
        return jsonify({"error": "Dati mancanti (email o sk)"}), 400

    try:
        table.delete_item(
            Key={
                'PK': f"STUDENT#{student_email}",
                'SK': note_sk
            }
        )
        return jsonify({"message": "Nota eliminata"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500