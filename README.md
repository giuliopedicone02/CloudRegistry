Ecco il file `README.md` aggiornato e completo, pronto per essere caricato su GitHub. Ho inserito il link al sito funzionante in evidenza e la struttura delle cartelle esattamente come me l'hai passata.

Puoi copiare e incollare tutto il blocco qui sotto.

---

# ☁️ CloudRegistry - Registro Elettronico Cloud-Native su AWS

**CloudRegistry** è una piattaforma di registro elettronico moderna, scalabile e sicura, progettata seguendo i paradigmi **Cloud-Native** su Amazon Web Services (AWS). Il progetto adotta un'architettura ibrida che combina la flessibilità del **Serverless** con la portabilità dei **Microservizi Containerizzati**.

## 🌐 Demo Live

Il progetto è attualmente deployato e funzionante. Puoi visualizzare il frontend ospitato su S3 qui:

👉 **[Clicca qui per accedere a CloudRegistry](http://registro-cloud-frontend-cca91a84.s3-website.eu-central-1.amazonaws.com/)**

---

## 📂 Struttura del Progetto

L'organizzazione del codice riflette la separazione tra infrastruttura, backend serverless, microservizi containerizzati e frontend:

```bash
.
├── backend/            # Microservizio Python Flask (Gestione Note Disciplinari)
│   ├── app.py          # Logica applicativa del container
│   ├── Dockerfile      # Definizione dell'immagine Docker
│   └── requirements.txt # Dipendenze Python
├── frontend/           # Interfaccia Utente (SPA)
│   └── index.html      # HTML, CSS e JS (comunica con Lambda e ECS)
├── index.py            # Funzione AWS Lambda (Gestione Voti e Studenti)
├── main.tf             # Infrastructure as Code (Terraform)
├── terraform.tfstate   # Stato dell'infrastruttura (gestito da Terraform)
└── terraform.tfstate.backup

```

---

## 🏗️ Architettura del Sistema

L'architettura è progettata per garantire alta disponibilità, sicurezza e scalabilità automatica.

### Servizi AWS Utilizzati

| Servizio | Ruolo nell'Architettura |
| --- | --- |
| **Amazon S3** | Ospita il **frontend** statico (HTML/JS/CSS) con hosting web pubblico. |
| **Amazon Cognito** | Gestisce le identità, il login e la sicurezza, distinguendo i ruoli (Docente/Studente). |
| **AWS Lambda** | **Backend Serverless**. Implementa la logica CRUD per studenti e voti. |
| **Amazon DynamoDB** | **Database NoSQL**. Memorizza dati su utenti, classi, voti e note con bassa latenza. |
| **Amazon API Gateway** | Punto di ingresso per le API REST. Instrada le richieste verso Lambda. |
| **Amazon SNS** | **Notifiche**. Invia email automatiche agli studenti quando ricevono un nuovo voto (pub/sub). |
| **Amazon ECR** | Registro container privato dove viene caricata l'immagine Docker del backend. |
| **Amazon ECS (Fargate)** | **Compute Containerizzato**. Esegue il microservizio delle "Note Disciplinari" senza server. |

---

## 🚀 Funzionalità Principali

### 1. Autenticazione & Ruoli

* Login sicuro tramite **Cognito User Pools**.
* Distinzione dei ruoli:
* **Docente:** Può inserire voti, note e visualizzare gli studenti.
* **Studente:** Può visualizzare solo i propri voti, medie e note.



### 2. Gestione Voti (Serverless)

* Microservizio basato su **AWS Lambda**.
* Permette l'inserimento e la cancellazione dei voti.
* Calcolo automatico delle medie per materia in tempo reale.

### 3. Note Disciplinari (Microservizio Docker)

* Implementato in **Python/Flask** e containerizzato.
* Eseguito su **AWS Fargate** per dimostrare l'uso di container in cloud.
* Supporta operazioni CRUD (Lettura, Scrittura, Cancellazione).

### 4. Notifiche Email

* Integrazione con **Amazon SNS**.
* Ogni volta che un docente inserisce un voto, lo studente riceve una mail di notifica istantanea.

> **Nota:** La gestione delle *Presenze* è stata volontariamente esclusa da questa iterazione del progetto per mantenere il focus sull'architettura cloud e non sulla complessità della logica di business.

---

## 🛠️ DevOps & Deployment

Il progetto utilizza l'approccio **Infrastructure as Code (IaC)** per garantire che l'intero ambiente sia riproducibile e versionabile.

### Terraform

Tutta l'infrastruttura (Rete, Database, Compute, Security Group, IAM Roles) è definita nel file `main.tf`.

* **Deployment:** `terraform apply`
* **Cleanup:** `terraform destroy`

### GitHub Actions (CI/CD)

Una pipeline automatizzata gestisce il deployment continuo:

1. **Build:** Costruzione dell'immagine Docker per il servizio Note.
2. **Push:** Caricamento dell'immagine su Amazon ECR.
3. **Update:** Aggiornamento automatico del servizio ECS Fargate.

---

