from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import firebase_admin
from firebase_admin import credentials, auth, firestore
import json
import os
from datetime import datetime
import logging

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'chiave-segreta-fissa-da-cambiare-in-produzione')

# make routing less strict about trailing slashes
app.url_map.strict_slashes = False

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
    aggiorna_prodotti_scaduti(uid)
    dispense = carica_dispense_utente(uid)
    dispense_list = []
    for nome, alimenti in dispense.items():
        dispense_list.append({'nome_dispensa': nome, 'alimenti': list(alimenti.values())})
    return render_template('home.html', dispense=dispense_list, show_menu=True)

@app.route('/dispense')
@richiede_autenticazione
def dispense_page():
    uid = verifica_autenticazione()
    aggiorna_prodotti_scaduti(uid)
    dispense = carica_dispense_utente(uid)
    return render_template('dispense.html', dispense=dispense, show_menu=True)

@app.route('/lista_spesa')
@richiede_autenticazione
def lista_spesa_page():
    uid = verifica_autenticazione()
    aggiorna_prodotti_scaduti(uid)
    prodotti_generale = []  # Sostituisci con la logica reale
    prodotti_scaduti = []
    # Carica prodotti scaduti dalla lista dedicata
    lista_ref = db.collection('utenti').document(uid).collection('liste_spesa').document('Prodotti Scaduti')
    lista_doc = lista_ref.get()
    if lista_doc.exists:
        prodotti_scaduti = lista_doc.to_dict().get('prodotti', [])
    return render_template('lista_spesa.html', prodotti_generale=prodotti_generale, prodotti_scaduti=prodotti_scaduti, show_menu=True)

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

@app.route('/dispensa/<nome_dispensa>')
@richiede_autenticazione
def dispensa_detail(nome_dispensa):
    uid = verifica_autenticazione()
    aggiorna_prodotti_scaduti(uid)
    dispense = carica_dispense_utente(uid)
    prodotti = dispense.get(nome_dispensa, {})
    if not prodotti:
        for key, val in dispense.items():
            if key.strip().lower() == nome_dispensa.strip().lower():
                prodotti = val
                nome_dispensa = key
                app.logger.info(f"Matched dispensa by case/trim to '{key}'")
                break
    return render_template('dispensa_detail.html', nome_dispensa=nome_dispensa, prodotti=prodotti, show_menu=True)

@app.route('/profilo')
def profilo_page():  # <-- rinominato da 'profilo' a 'profilo_page'
    uid = verifica_autenticazione()
    user_ref = db.collection('utenti').document(uid)
    user_doc = user_ref.get()

    profilo = None
    if user_doc.exists:
        profilo = user_doc.to_dict()

    return render_template('profilo.html', profilo=profilo)

@app.route('/salva_profilo', methods=['POST'])
@richiede_autenticazione
def salva_profilo():
    uid = verifica_autenticazione()

    try:
        nome = request.form.get('nome', '')
        cognome = request.form.get('cognome', '')
        nickname = request.form.get('nickname', '')
        data_nascita = request.form.get('data_nascita', '')
        dieta = request.form.get('dieta', '')
        biografia = request.form.get('biografia', '')

        if not nickname or not data_nascita or not dieta:
            return jsonify({'success': False, 'message': 'Campi obbligatori mancanti'}), 400

        profilo_data = {
            'nome': nome,
            'cognome': cognome,
            'nickname': nickname,
            'data_nascita': data_nascita,
            'dieta': dieta,
            'biografia': biografia,
            'aggiornato_il': firestore.SERVER_TIMESTAMP
        }

        if 'foto' in request.files:
            foto = request.files['foto']
            if foto.filename:
                profilo_data['foto_url'] = 'https://via.placeholder.com/150x150.png?text=' + nickname[0].upper()

        user_ref = db.collection('utenti').document(uid)
        user_ref.set(profilo_data, merge=True)

        return jsonify({'success': True, 'message': 'Profilo salvato con successo!'})
    except Exception as e:
        print(f"Errore nel salvataggio del profilo: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500

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

@app.route('/rimuovi_prodotto_lista_spesa', methods=['POST'])
@richiede_autenticazione
def rimuovi_prodotto_lista_spesa():
    uid = verifica_autenticazione()
    nome_lista = request.form['nome_lista']
    nome_prodotto = request.form['nome_prodotto']

    # Recupera la lista dal database
    lista_ref = db.collection('utenti').document(uid).collection('liste_spesa').document(nome_lista)
    lista_doc = lista_ref.get()
    if not lista_doc.exists:
        return jsonify({'success': False, 'message': 'Lista non trovata'}), 404

    prodotti = lista_doc.to_dict().get('prodotti', [])
    if nome_prodotto in prodotti:
        prodotti.remove(nome_prodotto)
        lista_ref.set({'prodotti': prodotti}, merge=True)
        return jsonify({'success': True, 'message': 'Prodotto rimosso'})
    else:
        return jsonify({'success': False, 'message': 'Prodotto non trovato'}), 404

@app.route('/sposta_in_lista_spesa', methods=['POST'])
@richiede_autenticazione
def sposta_in_lista_spesa():
    uid = verifica_autenticazione()
    nome_dispensa = request.form['nome_dispensa']
    nome_alimento = request.form['nome_alimento']
    lista_destinazione = request.form['lista_destinazione']

    # Rimuovi il prodotto dalla dispensa
    dispense = carica_dispense_utente(uid)
    if nome_dispensa not in dispense or nome_alimento not in dispense[nome_dispensa]:
        return jsonify({'success': False, 'message': 'Prodotto non trovato nella dispensa'}), 404

    prodotto = dispense[nome_dispensa][nome_alimento]
    del dispense[nome_dispensa][nome_alimento]
    salva_dispensa_utente(uid, nome_dispensa, dispense[nome_dispensa])

    # Aggiungi il prodotto alla lista spesa
    lista_ref = db.collection('utenti').document(uid).collection('liste_spesa').document(lista_destinazione)
    lista_doc = lista_ref.get()
    prodotti = []
    if lista_doc.exists:
        prodotti = lista_doc.to_dict().get('prodotti', [])
    if nome_alimento not in prodotti:
        prodotti.append(nome_alimento)
    lista_ref.set({'prodotti': prodotti}, merge=True)

    return jsonify({'success': True, 'message': 'Prodotto spostato'})

@app.route('/sposta_in_dispensa', methods=['POST'])
@richiede_autenticazione
def sposta_in_dispensa():
    uid = verifica_autenticazione()
    nome_lista = request.form['nome_lista']
    nome_prodotto = request.form['nome_prodotto']
    nome_dispensa = request.form['nome_dispensa']

    # Rimuovi il prodotto dalla lista spesa
    lista_ref = db.collection('utenti').document(uid).collection('liste_spesa').document(nome_lista)
    lista_doc = lista_ref.get()
    prodotti = []
    if lista_doc.exists:
        prodotti = lista_doc.to_dict().get('prodotti', [])
    if nome_prodotto in prodotti:
        prodotti.remove(nome_prodotto)
        lista_ref.set({'prodotti': prodotti}, merge=True)
    else:
        return jsonify({'success': False, 'message': 'Prodotto non trovato nella lista'}), 404

    # Aggiungi il prodotto alla dispensa (aggiunto come semplice nome, puoi estendere con dettagli)
    dispense = carica_dispense_utente(uid)
    if nome_dispensa not in dispense:
        dispense[nome_dispensa] = {}
    dispense[nome_dispensa][nome_prodotto] = {
        "quantita": 1,
        "scadenza": "",
        "unita": "",
        "categoria": trova_categoria(nome_prodotto),
        "tipo": "alimento"
    }
    salva_dispensa_utente(uid, nome_dispensa, dispense[nome_dispensa])

    return jsonify({'success': True, 'message': 'Prodotto spostato nella dispensa'})

# handy redirect for /dispensa to main list
@app.route('/dispensa')
@app.route('/dispensa/')
@richiede_autenticazione
def dispensa_index():
    return redirect(url_for('dispense_page'))

# 404 handler that logs path (useful to see why a Not Found occurred)
@app.errorhandler(404)
def handle_404(e):
    app.logger.warning(f"404 Not Found: {request.path}")
    # keep default behavior but return the template if you want custom page
    return "Not Found", 404

@app.route('/')
def landing():
    return render_template('landing.html')

@app.route('/login')
def login():
    uid = verifica_autenticazione()
    if uid:
        return redirect(url_for('profilo_page'))  # <-- usa il nome corretto della funzione
    return render_template('login.html')

@app.route('/register')
def register():
    return render_template('register.html')

@app.route('/lista_spesa/<nome_lista>')
@richiede_autenticazione
def lista_spesa_detail(nome_lista):
    uid = verifica_autenticazione()
    aggiorna_prodotti_scaduti(uid)
    lista_ref = db.collection('utenti').document(uid).collection('liste_spesa').document(nome_lista)
    lista_doc = lista_ref.get()
    prodotti = []
    if lista_doc.exists:
        prodotti = lista_doc.to_dict().get('prodotti', [])
    return render_template('lista_spesa_detail.html', nome_lista=nome_lista, prodotti=prodotti, show_menu=True)

def aggiorna_prodotti_scaduti(uid):
    dispense = carica_dispense_utente(uid)
    oggi = datetime.now().date()
    prodotti_scaduti = []

    for nome_dispensa, alimenti in dispense.items():
        to_remove = []
        for nome_alimento, dati in list(alimenti.items()):
            scadenza = dati.get('scadenza')
            if scadenza:
                try:
                    data_scadenza = datetime.strptime(scadenza, "%Y-%m-%d").date()
                    if data_scadenza < oggi:
                        prodotti_scaduti.append(nome_alimento)
                        to_remove.append(nome_alimento)
                except Exception:
                    continue
        # Rimuovi i prodotti scaduti dalla dispensa
        for nome_alimento in to_remove:
            del dispense[nome_dispensa][nome_alimento]
        if to_remove:
            salva_dispensa_utente(uid, nome_dispensa, dispense[nome_dispensa])

    # Aggiungi i prodotti scaduti alla lista "Prodotti Scaduti"
    if prodotti_scaduti:
        lista_ref = db.collection('utenti').document(uid).collection('liste_spesa').document('Prodotti Scaduti')
        lista_doc = lista_ref.get()
        prodotti_lista = []
        if lista_doc.exists:
            prodotti_lista = lista_doc.to_dict().get('prodotti', [])
        for prod in prodotti_scaduti:
            if prod not in prodotti_lista:
                prodotti_lista.append(prod)
        lista_ref.set({'prodotti': prodotti_lista}, merge=True)

if __name__ == "__main__":
    app.run(debug=True)