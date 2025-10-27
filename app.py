from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import firebase_admin
from firebase_admin import credentials, auth, firestore
import json
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'chiave-segreta-fissa-da-cambiare-in-produzione')

if os.environ.get('FIREBASE_CREDENTIALS'):
    firebase_creds = json.loads(os.environ.get('FIREBASE_CREDENTIALS'))
    cred = credentials.Certificate(firebase_creds)
elif os.path.exists('serviceAccountKey.json'):
    cred = credentials.Certificate('serviceAccountKey.json')
elif os.path.exists('/etc/secrets/serviceAccountKey.json'):
    cred = credentials.Certificate('/etc/secrets/serviceAccountKey.json')
else:
    cred = credentials.Certificate("backend/serviceAccountKey.json")

firebase_admin.initialize_app(cred)

db = firestore.client()

with open('food_data.json', 'r', encoding='utf-8') as f:
    food_data = json.load(f)

def trova_categoria(nome_alimento):
    nome_lower = nome_alimento.lower().strip()

    for categoria in food_data['categorie_cibi']:
        nome_categoria = categoria['nome_categoria']
        prodotti = categoria['prodotti']

        if nome_lower in [p.lower() for p in prodotti]:
            return nome_categoria

    for categoria in food_data['categorie_cibi']:
        nome_categoria = categoria['nome_categoria']
        prodotti = categoria['prodotti']

        for prodotto in prodotti:
            prodotto_lower = prodotto.lower()
            parole_prodotto = prodotto_lower.split()
            parole_alimento = nome_lower.split()

            if any(parola in parole_prodotto for parola in parole_alimento if len(parola) > 2):
                return nome_categoria

    return 'altro'

def verifica_autenticazione():
    id_token = request.cookies.get('token')

    if not id_token:
        return None

    try:
        decoded_token = auth.verify_id_token(id_token)
        uid = decoded_token['uid']
        return uid
    except Exception as e:
        print(f"Errore durante la verifica del token: {e}")
        return None

def richiede_autenticazione(f):
    from functools import wraps
    @wraps(f)
    def decorated_function(*args, **kwargs):
        uid = verifica_autenticazione()
        if uid is None:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def carica_dispense_utente(uid):
    try:
        dispense_ref = db.collection('utenti').document(uid).collection('dispense')
        dispense_docs = dispense_ref.stream()

        dispense = {}
        for doc in dispense_docs:
            dispense[doc.id] = doc.to_dict().get('alimenti', {})

        return dispense
    except Exception as e:
        print(f"Errore nel caricamento delle dispense: {e}")
        return {}

def salva_dispensa_utente(uid, nome_dispensa, alimenti):
    try:
        dispensa_ref = db.collection('utenti').document(uid).collection('dispense').document(nome_dispensa)
        dispensa_ref.set({
            'alimenti': alimenti,
            'ultima_modifica': firestore.SERVER_TIMESTAMP
        })
        return True
    except Exception as e:
        print(f"Errore nel salvataggio della dispensa: {e}")
        return False

def elimina_dispensa_utente(uid, nome_dispensa):
    try:
        db.collection('utenti').document(uid).collection('dispense').document(nome_dispensa).delete()
        return True
    except Exception as e:
        print(f"Errore nell'eliminazione della dispensa: {e}")
        return False

def crea_profilo_utente(uid, email):
    try:
        user_ref = db.collection('utenti').document(uid)
        user_ref.set({
            'email': email,
            'data_creazione': firestore.SERVER_TIMESTAMP
        })
        return True
    except Exception as e:
        print(f"Errore nella creazione del profilo utente: {e}")
        return False

@app.route('/home')
@richiede_autenticazione
def home():
    uid = verifica_autenticazione()
    dispense = carica_dispense_utente(uid)
    dispense_list = [{"nome_dispensa": k, "alimenti": v} for k, v in dispense.items()]
    return render_template('home.html', dispense=dispense_list)

@app.route('/dispense')
@richiede_autenticazione
def dispense_page():
    uid = verifica_autenticazione()
    dispense = carica_dispense_utente(uid)
    return render_template('dispense.html', dispense=dispense)

@app.route('/lista_spesa')
@richiede_autenticazione
def lista_spesa_page():
    return render_template('lista_spesa.html')

@app.route('/aggiungi', methods=['POST'])
@richiede_autenticazione
def aggiungi():
    uid = verifica_autenticazione()
    nome_dispensa = request.form['nome_dispensa']
    nome_alimento = request.form['nome_alimento']
    quantita = int(request.form['quantita'])
    scadenza = request.form['scadenza']
    unita = request.form['unita']

    categoria = trova_categoria(nome_alimento)
    tipo = "alimento"

    dispense = carica_dispense_utente(uid)

    if nome_dispensa not in dispense:
        dispense[nome_dispensa] = {}

    dispense[nome_dispensa][nome_alimento] = {
        "quantita": quantita,
        "scadenza": scadenza,
        "unita": unita,
        "categoria": categoria,
        "tipo": tipo
    }

    salva_dispensa_utente(uid, nome_dispensa, dispense[nome_dispensa])

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'message': 'Alimento aggiunto alla dispensa!'})
    else:
        return redirect(url_for('dispense_page'))

@app.route('/rimuovi', methods=['POST'])
@richiede_autenticazione
def rimuovi():
    uid = verifica_autenticazione()
    nome_dispensa = request.form['nome_dispensa']
    nome_alimento = request.form['nome_alimento']

    dispense = carica_dispense_utente(uid)

    if nome_dispensa in dispense and nome_alimento in dispense[nome_dispensa]:
        del dispense[nome_dispensa][nome_alimento]
        salva_dispensa_utente(uid, nome_dispensa, dispense[nome_dispensa])
        return jsonify({'message': 'Alimento rimosso dalla dispensa!'})
    else:
        return jsonify({'message': 'Alimento non trovato nella dispensa!'}), 404

@app.route('/profilo')
@richiede_autenticazione
def profilo_page():
    return render_template('profilo.html')

@app.route('/crea_dispensa', methods=['POST'])
@richiede_autenticazione
def crea_dispensa():
    uid = verifica_autenticazione()
    nome_nuova_dispensa = request.form['nome_nuova_dispensa']

    dispense = carica_dispense_utente(uid)

    if nome_nuova_dispensa and nome_nuova_dispensa not in dispense:
        salva_dispensa_utente(uid, nome_nuova_dispensa, {})
        return jsonify({'message': 'Dispensa creata!', 'success': True})
    else:
        return jsonify({'message': 'Nome non valido o già esistente.', 'success': False}), 400

@app.route('/modifica_dispensa', methods=['POST'])
@richiede_autenticazione
def modifica_dispensa():
    uid = verifica_autenticazione()
    nome_dispensa_originale = request.form['nome_dispensa_originale']
    nuovo_nome_dispensa = request.form['nuovo_nome_dispensa']
    alimenti_json = request.form['alimenti']
    alimenti = json.loads(alimenti_json)

    dispense = carica_dispense_utente(uid)

    if nome_dispensa_originale not in dispense:
        return jsonify({'message': 'Dispensa non trovata!', 'success': False}), 404

    if nuovo_nome_dispensa != nome_dispensa_originale:
        if nuovo_nome_dispensa in dispense:
            return jsonify({'message': 'Il nuovo nome della dispensa è già in uso!', 'success': False}), 400
        elimina_dispensa_utente(uid, nome_dispensa_originale)

    salva_dispensa_utente(uid, nuovo_nome_dispensa, alimenti)

    return jsonify({'message': 'Dispensa modificata con successo!', 'success': True})

@app.route('/elimina_dispensa', methods=['POST'])
@richiede_autenticazione
def elimina_dispensa():
    uid = verifica_autenticazione()
    nome_dispensa = request.form['nome_dispensa']

    dispense = carica_dispense_utente(uid)

    if nome_dispensa in dispense:
        elimina_dispensa_utente(uid, nome_dispensa)
        return jsonify({'message': 'Dispensa eliminata con successo!', 'success': True})
    else:
        return jsonify({'message': 'Dispensa non trovata!', 'success': False}), 404

@app.route('/')
def landing():
    return render_template('landing.html')

@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/register')
def register():
    return render_template('register.html')

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)