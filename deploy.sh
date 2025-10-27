#!/bin/bash

# Script per deploy su Google Cloud Run
# Esegui questo script da Google Cloud Shell

# Imposta il progetto
gcloud config set project dispenza-cb47a

# Abilita le API necessarie
gcloud services enable run.googleapis.com
gcloud services enable cloudbuild.googleapis.com

# Deploy su Cloud Run
gcloud run deploy dispenza-backend \
  --source . \
  --region europe-west1 \
  --allow-unauthenticated \
  --platform managed \
  --memory 512Mi \
  --timeout 300

echo "✅ Deploy completato!"
echo "Il tuo backend è disponibile all'URL mostrato sopra"
