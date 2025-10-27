# Comandi per Deploy su Google Cloud Run

# 1. Autenticati con Google Cloud
gcloud auth login

# 2. Imposta il progetto
gcloud config set project dispenza-cb47a

# 3. Abilita le API necessarie
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com

# 4. Deploy su Cloud Run
gcloud run deploy dispenza-backend \
  --source . \
  --region europe-west1 \
  --allow-unauthenticated \
  --platform managed

# Dopo il deploy, otterrai un URL tipo:
# https://dispenza-backend-xxxxx-ew.a.run.app
