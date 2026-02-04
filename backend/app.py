from flask import Flask, request, jsonify
from flask_cors import CORS
import boto3
import os
import datetime
from boto3.dynamodb.conditions import Key

app = Flask(__name__)
CORS(app) # Fondamentale per far passare le chiamate dal browser

# Configurazione DynamoDB
TABLE_NAME = os.environ.get('TABLE_NAME', 'CloudRegistryDB')
dynamodb = boto3.resource('dynamodb', region_name='eu-central-1')
table = dynamodb.Table(TABLE_NAME)

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
    item = {
        'PK': f"STUDENT#{data.get('student_email')}",
        'SK': f"NOTA#{datetime.datetime.now().isoformat()}",
        'tipo': 'NOTA',
        'testo': data.get('testo'),
        'data': datetime.datetime.now().isoformat(),
        'teacher': data.get('teacher')
    }
    try:
        table.put_item(Item=item)
        return jsonify({"message": "Nota inserita"}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# 👇👇👇 QUESTA È LA PARTE CHE MANCA SU AWS 👇👇👇
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