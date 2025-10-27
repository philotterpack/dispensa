# 🚀 DEPLOY VELOCE - 3 PASSI

## 1️⃣ Push su GitHub
```bash
git add .
git commit -m "Setup Render"
git push origin main
```

## 2️⃣ Vai su Render
1. Apri https://render.com e registrati con GitHub
2. Clicca **"New +"** → **"Web Service"**
3. Seleziona il tuo repository
4. Configura:
   - **Name**: `dispensa-app`
   - **Region**: `Frankfurt`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
   - **Plan**: **Free**

## 3️⃣ Aggiungi credenziali Firebase
1. Vai su **"Environment"** → **"Add Secret File"**
2. **File Path**: `backend/serviceAccountKey.json`
3. Copia e incolla il contenuto del tuo file JSON
4. Clicca **"Create Web Service"**

## ✅ Fatto!
Il tuo link sarà: `https://dispensa-app.onrender.com`

---

**📖 Guida completa**: vedi `RENDER_DEPLOY.md`
