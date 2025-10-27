# 🚀 DEPLOY SU RENDER - GUIDA COMPLETA

## 📋 Prerequisiti
- Account GitHub (con il progetto pushato)
- Account Render (gratuito su https://render.com)
- File `serviceAccountKey.json` di Firebase

---

## 🔧 STEP 1: Prepara il progetto

### 1.1 Verifica che questi file esistano:
- ✅ `render.yaml` (configurazione Render)
- ✅ `requirements.txt` (dipendenze Python)
- ✅ `app.py` (applicazione Flask)
- ✅ `backend/serviceAccountKey.json` (credenziali Firebase)

### 1.2 Push su GitHub
```bash
git add .
git commit -m "Setup per deploy Render"
git push origin main
```

---

## 🌐 STEP 2: Deploy su Render

### 2.1 Crea account su Render
1. Vai su https://render.com
2. Clicca "Get Started for Free"
3. Registrati con GitHub

### 2.2 Collega il repository
1. Nel dashboard Render, clicca **"New +"** → **"Web Service"**
2. Clicca **"Connect account"** per collegare GitHub
3. Seleziona il repository del progetto
4. Clicca **"Connect"**

### 2.3 Configura il servizio
Compila i campi:
- **Name**: `dispensa-app` (o quello che vuoi)
- **Region**: `Frankfurt (EU Central)` (più vicino all'Italia)
- **Branch**: `main`
- **Root Directory**: lascia vuoto
- **Runtime**: `Python 3`
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `gunicorn app:app`
- **Plan**: **Free**

### 2.4 Aggiungi variabili d'ambiente
Nella sezione **"Environment Variables"**, aggiungi:

| Key | Value |
|-----|-------|
| `PYTHON_VERSION` | `3.11.0` |
| `PORT` | `10000` |

### 2.5 Aggiungi le credenziali Firebase
**IMPORTANTE**: Devi caricare il file `serviceAccountKey.json` come variabile d'ambiente.

**Opzione A - File Secret (consigliata)**:
1. Nella dashboard del servizio, vai su **"Environment"**
2. Clicca **"Add Secret File"**
3. **File Path**: `backend/serviceAccountKey.json`
4. Copia e incolla il contenuto del tuo file `serviceAccountKey.json`
5. Salva

**Opzione B - Variabile d'ambiente JSON**:
1. Apri il file `backend/serviceAccountKey.json`
2. Copia tutto il contenuto
3. Aggiungi variabile d'ambiente:
   - **Key**: `FIREBASE_CREDENTIALS`
   - **Value**: incolla il JSON completo
4. Modifica `app.py` per leggere da variabile d'ambiente (vedi sotto)

### 2.6 Deploy!
1. Clicca **"Create Web Service"**
2. Render inizierà il build (ci vogliono 2-3 minuti)
3. Quando vedi "Live" in verde, l'app è online! 🎉

---

## 🔗 STEP 3: Ottieni il link

Il tuo link sarà tipo:
```
https://dispensa-app.onrender.com
```

Copialo e condividilo con i tuoi amici!

---

## ⚠️ IMPORTANTE: Limitazioni piano gratuito

- ⏱️ **Sleep dopo 15 minuti** di inattività
- 🐌 **Primo caricamento lento** (~30 secondi) dopo sleep
- 💾 **750 ore/mese** di uptime gratuito
- 🔄 **Auto-deploy** ad ogni push su GitHub

---

## 🔄 Aggiornare l'app

Ogni volta che fai modifiche:
```bash
git add .
git commit -m "Descrizione modifiche"
git push origin main
```

Render farà automaticamente il redeploy! 🚀

---

## 🐛 Troubleshooting

### L'app non parte?
1. Vai su Render Dashboard → Il tuo servizio → **"Logs"**
2. Cerca errori nei log
3. Problemi comuni:
   - ❌ `serviceAccountKey.json` non trovato → Aggiungi Secret File
   - ❌ Errore Firebase → Verifica credenziali
   - ❌ Errore import → Verifica `requirements.txt`

### L'app è lenta?
- È normale al primo caricamento dopo sleep
- Considera upgrade a piano paid ($7/mese) per evitare sleep

### Errore 502 Bad Gateway?
- L'app sta ancora facendo il build
- Aspetta 2-3 minuti e ricarica

---

## 📝 Modifica app.py per variabile d'ambiente (Opzione B)

Se usi la variabile d'ambiente invece del Secret File, modifica `app.py`:

```python
import os
import json

# Invece di:
# cred = credentials.Certificate("backend/serviceAccountKey.json")

# Usa:
if os.environ.get('FIREBASE_CREDENTIALS'):
    # Produzione (Render)
    firebase_creds = json.loads(os.environ.get('FIREBASE_CREDENTIALS'))
    cred = credentials.Certificate(firebase_creds)
else:
    # Sviluppo locale
    cred = credentials.Certificate("backend/serviceAccountKey.json")

firebase_admin.initialize_app(cred)
```

---

## ✅ Checklist finale

- [ ] Repository pushato su GitHub
- [ ] Account Render creato
- [ ] Web Service creato e collegato a GitHub
- [ ] Variabili d'ambiente configurate
- [ ] `serviceAccountKey.json` caricato come Secret File
- [ ] Deploy completato (status "Live")
- [ ] Link testato e funzionante
- [ ] Link condiviso con amici! 🎉

---

**Buon testing! 🚀**
