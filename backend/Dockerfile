# Usa un'immagine leggera di Python
FROM python:3.9-slim

# Imposta la directory di lavoro dentro il container
WORKDIR /app

# Copia i requisiti e installali
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copia il codice dell'app
COPY app.py .

# Esponi la porta 80 (standard HTTP)
EXPOSE 80

# Comando per avviare l'app
CMD ["python", "app.py"]