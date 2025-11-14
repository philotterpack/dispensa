import pytesseract
from PIL import Image
import cv2
import numpy as np
import re
import json
from datetime import datetime, timedelta

# ========== CONFIGURAZIONE TESSERACT (decommentare se necessario) ==========
# WINDOWS:
# pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

# MAC (Homebrew):
# pytesseract.pytesseract.tesseract_cmd = r"/usr/local/bin/tesseract"
# pytesseract.pytesseract.tesseract_cmd = r"/opt/homebrew/bin/tesseract"

# LINUX:
# pytesseract.pytesseract.tesseract_cmd = r"/usr/bin/tesseract"

# ========== CARICA DATI ALIMENTARI ==========
with open('food_data.json', 'r', encoding='utf-8') as f:
    food_data = json.load(f)

# Crea lista di tutti i prodotti alimentari dal JSON e mappa prodotto -> categoria + range
PRODOTTI_ALIMENTARI = []
MAPPA_PRODOTTO_CATEGORIA = {}  # es: "finocchio" -> {"categoria": "verdura", "range_scadenza": "5-7 giorni (fresca), 3-4 mesi (congelata)"}

for categoria in food_data['categorie_cibi']:
    nome_cat = categoria['nome_categoria']
    range_scad = categoria.get('range_scadenza', '')
    for p in categoria['prodotti']:
        pl = p.lower()
        PRODOTTI_ALIMENTARI.append(pl)
        MAPPA_PRODOTTO_CATEGORIA[pl] = {
            'categoria': nome_cat,
            'range_scadenza': range_scad
        }

# ========== PAROLE CHIAVE NON ALIMENTARI ==========
PAROLE_NON_ALIMENTARI = [
    'sacchetto', 'sacch.', 'sacch', 'sacch.ortofr',
    'sconto', 'offerta', 'buste', 'busta',
    'apribottiglie', 'avvitatore', 'albero', 'flessibile',
    'trasp', 'trasparente',
    'lama', 'sega', 'acciaio',
    'lidl plus', 'biograd', 'ortofr',
    'a4', '50pz',
    'utensile', 'attrezzo',
    'plastica', 'carta', 'contenitore', 'borsa', 'shopper'
]

# ========== UTILITY PER DATE/SCADENZE ==========

def aggiungi_giorni_oggi(n_giorni):
    return (datetime.today() + timedelta(days=n_giorni)).strftime("%Y-%m-%d")

def aggiungi_mesi_oggi(n_mesi):
    # Approssimiamo 1 mese = 30 giorni
    return (datetime.today() + timedelta(days=30 * n_mesi)).strftime("%Y-%m-%d")

def stima_scadenze_da_range(range_scadenza):
    """
    Dal testo tipo:
      "5-7 giorni (fresca), 3-4 mesi (congelata)"
    ricava due date:
      - scadenza_suggerita (fresca)
      - scadenza_surgelato  (congelata)
    Se qualcosa non torna, usa fallback generici.
    """
    range_scadenza = (range_scadenza or "").lower()
    scadenza_suggerita = aggiungi_giorni_oggi(5)   # default fresh
    scadenza_surgelato = aggiungi_mesi_oggi(3)     # default frozen

    # fresca: "x-y giorni (fresca)"
    match_fresca = re.search(r'(\d+)\s*-\s*(\d+)\s*giorni\s*\(fresca', range_scadenza)
    if match_fresca:
        min_g = int(match_fresca.group(1))
        max_g = int(match_fresca.group(2))
        media = (min_g + max_g) // 2
        scadenza_suggerita = aggiungi_giorni_oggi(media)
    else:
        # altri pattern tipo "3 giorni (fresco)" ecc.
        match_fresco_singolo = re.search(r'(\d+)\s*giorni?\s*\(fresc', range_scadenza)
        if match_fresco_singolo:
            giorni = int(match_fresco_singolo.group(1))
            scadenza_suggerita = aggiungi_giorni_oggi(giorni)

    # congelata / surgelata: "x-y mesi (congelata)"
    match_congelata = re.search(r'(\d+)\s*-\s*(\d+)\s*mesi\s*\((congelata|congelato)', range_scadenza)
    if match_congelata:
        min_m = int(match_congelata.group(1))
        max_m = int(match_congelata.group(2))
        media = (min_m + max_m) // 2
        scadenza_surgelato = aggiungi_mesi_oggi(media)
    else:
        # pattern tipo "6 mesi (congelato)"
        match_cong_singolo = re.search(r'(\d+)\s*mesi\s*\((congelato|congelata)', range_scadenza)
        if match_cong_singolo:
            mesi = int(match_cong_singolo.group(1))
            scadenza_surgelato = aggiungi_mesi_oggi(mesi)

    return scadenza_suggerita, scadenza_surgelato

# ========== OCR E PARSING TESTO ==========

def preprocessa_immagine(image_path):
    """Migliora la qualità dell'immagine per OCR"""
    img = cv2.imread(image_path)
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Aumenta contrasto
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(gray)

    # Binarizzazione adattiva
    thresh = cv2.adaptiveThreshold(
        enhanced, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY, 11, 2
    )

    # Denoising
    denoised = cv2.fastNlMeansDenoising(thresh)

    return denoised

def estrai_testo_da_scontrino(image_path):
    """Estrae il testo dallo scontrino"""
    img_processed = preprocessa_immagine(image_path)

    # Configurazione ottimizzata per scontrini italiani
    custom_config = r'--oem 3 --psm 6 -l ita'
    testo = pytesseract.image_to_string(img_processed, config=custom_config)

    return testo

def pulisci_nome_prodotto(nome):
    """Pulisce il nome prodotto eliminando prezzi, numeri di peso e sigle tipo 'PZ', 'KG'."""
    # Rimuovi prezzi e percentuali
    nome = re.sub(r'\d+[,\.]\d+\s*€?', '', nome)
    nome = re.sub(r'\d+%', '', nome)
    nome = re.sub(r'EUR/kg', '', nome, flags=re.IGNORECASE)

    # Rimuovi sequenze tipo "1kg", "4Kg", "800G"
    nome = re.sub(r'\b\d+[,\.]?\d*\s*(kg|g)\b', '', nome, flags=re.IGNORECASE)

    # Rimuovi sigle di pezzi tipo "PZ", "Pz"
    nome = re.sub(r'\bpz\b', '', nome, flags=re.IGNORECASE)

    # Rimuovi simboli di valuta
    nome = re.sub(r'€|EUR|\$', '', nome, flags=re.IGNORECASE)

    # Mantieni solo lettere, numeri, spazi e punti
    nome = re.sub(r'[^\w\s\.]', ' ', nome)

    # Rimuovi spazi multipli
    nome = ' '.join(nome.split())

    return nome.strip()

def e_prodotto_alimentare(nome):
    """Verifica se il prodotto è alimentare"""
    nome_lower = nome.lower().strip()

    # 1. Controlla parole chiave NON alimentari
    for parola_non_alimentare in PAROLE_NON_ALIMENTARI:
        if parola_non_alimentare in nome_lower:
            return False

    # 2. Match diretto con il db
    if nome_lower in PRODOTTI_ALIMENTARI:
        return True

    # 3. Match parziale (parole in comune)
    parole_nome = nome_lower.split()
    for parola in parole_nome:
        if len(parola) > 2:
            for prodotto_db in PRODOTTI_ALIMENTARI:
                if parola in prodotto_db or prodotto_db in parola:
                    return True

    # 4. Euristica
    parole_cibo = [
        'kg', 'grammi', 'gr', 'pz',
        'bio', 'fresco', 'fresca',
        'integrale', 'naturale',
        'affumicato', 'affumicata',
        'piccante', 'mozzarella', 'formaggio', 'latte', 'burro'
    ]
    for parola in parole_cibo:
        if parola in nome_lower:
            return True

    return False

def trova_categoria_e_range(nome):
    """
    Dato un nome prodotto 'Finocchio', 'Mango', 'Mozzarella Multipack', ecc.
    prova a trovare la categoria (verdura, frutta...) e il range_scadenza associato.
    """
    nome_lower = nome.lower()
    # 1) match diretto
    if nome_lower in MAPPA_PRODOTTO_CATEGORIA:
        info = MAPPA_PRODOTTO_CATEGORIA[nome_lower]
        return info['categoria'], info.get('range_scadenza', '')

    # 2) match parziale: se una delle parole del nome è contenuta in un prodotto noto
    parole = nome_lower.split()
    for parola in parole:
        if len(parola) < 3:
            continue
        for prodotto_db, info in MAPPA_PRODOTTO_CATEGORIA.items():
            if parola in prodotto_db or prodotto_db in parola:
                return info['categoria'], info.get('range_scadenza', '')

    # fallback
    return 'altro', ''

def estrai_quantita_e_unita_da_nome(nome_originale):
    """
    Estrae quantità/unità dalla descrizione stessa (es: 'Patate 4Kg', 'Carote Igp 800G', 'Mango Pz').
    """
    n = nome_originale.lower()

    # Patate 4Kg → 4 kg
    match_kg = re.search(r'(\d+[,\.]?\d*)\s*kg', n, re.IGNORECASE)
    if match_kg:
        valore = match_kg.group(1).replace(',', '.')
        return float(valore), 'kg'

    # Carote 800G → 800 g
    match_g = re.search(r'(\d+)\s*g\b', n, re.IGNORECASE)
    if match_g:
        valore = int(match_g.group(1))
        return valore, 'g'

    # Mango Pz → 1 pz
    if 'pz' in n:
        return 1, 'pz'

    return None, None

def estrai_quantita_e_unita(riga_originale, nome_originale=None):
    """
    Estrae quantità e unità dalla riga tipo:
    - '0,510 kg x 1,79 EUR/kg'
    - '2,422 kg x 0,99 EUR/kg'
    - '1 x 800g = 800g'
    Se nome_originale è presente, prova anche a leggerlo da lì (Patate 4Kg, Carote 800G, Mango Pz).
    """
    r = riga_originale.lower()

    # 1) Prova prima dal nome (Patate 4Kg, Carote 800G, Mango Pz)
    if nome_originale:
        q_nome, u_nome = estrai_quantita_e_unita_da_nome(nome_originale)
        if q_nome is not None:
            return q_nome, u_nome

    # 2) Poi prova dalla riga di peso/prezzo
    # Pattern tipo: 0,510 kg
    match_kg = re.search(r'(\d+[,\.]\d+)\s*kg', r, re.IGNORECASE)
    if match_kg:
        peso = match_kg.group(1).replace(',', '.')
        return float(peso), 'kg'

    # Pattern tipo: 2 kg
    match_kg_int = re.search(r'(\d+)\s*kg', r, re.IGNORECASE)
    if match_kg_int:
        peso = int(match_kg_int.group(1))
        return float(peso), 'kg'

    # Pattern tipo: 1 x 800g = 800g → usiamo 800g
    match_g_eq = re.search(r'=\s*(\d+)\s*g', r, re.IGNORECASE)
    if match_g_eq:
        peso = int(match_g_eq.group(1))
        return peso, 'g'

    # Pattern tipo: 800g
    match_g = re.search(r'(\d+)\s*g\b', r, re.IGNORECASE)
    if match_g:
        peso = int(match_g.group(1))
        return peso, 'g'

    # Pattern tipo: "1 x" o "2 x" → interpretato come pezzi/pacchetti
    match_qty = re.search(r'(\d+)\s*x\b', r, re.IGNORECASE)
    if match_qty:
        qty = int(match_qty.group(1))
        return qty, 'pacchetti'

    # Default: 1 pacchetto
    return 1, 'pacchetti'

def identifica_prodotti(testo):
    """
    Identifica i prodotti dal testo dello scontrino usando coppie:
    - riga descrizione (FINOCCHIO, CAPPUCCIO, CAROTE...)
    - riga peso/prezzo subito sotto (0,510 kg x 1,79 EUR/kg...)
    """
    righe = [r.strip() for r in testo.split('\n') if r.strip()]
    prodotti = []

    pattern_prezzo = r'(\d+[,\.]\d{2})\s*€?'

    i = 0
    while i < len(righe):
        riga = righe[i]

        # Filtra intestazioni/footer e righe varie
        keywords_skip = [
            'totale', 'subtotale', 'resto', 'contante', 'carta',
            'iva', 'riepilogo', 'digitale', 'acquisto', 'documento',
            'pagamento', 'importo', 'lidl italia', 'roma', 'via',
            'raee', 'cdc', 'valore sconti', 'totale complessivo',
            'rt ', 'doc.', 'documento n.', 'importo pagato'
        ]
        if any(k in riga.lower() for k in keywords_skip):
            i += 1
            continue

        # Righe tecniche tipo "0,510 kg x 1,79 EUR/kg" NON devono essere trattate qui come prodotto
        if 'eur/kg' in riga.lower():
            i += 1
            continue

        # Se la riga NON contiene prezzo, la trattiamo come possibile descrizione prodotto
        if not re.search(pattern_prezzo, riga):
            nome_originale = riga
            nome_pulito = pulisci_nome_prodotto(riga)

            # Nome troppo corto → scarta
            if len(nome_pulito) < 3:
                i += 1
                continue

            # Non alimentare? → scarta
            if not e_prodotto_alimentare(nome_pulito):
                i += 1
                continue

            # Trova categoria e range scadenza dal JSON
            categoria, range_scadenza = trova_categoria_e_range(nome_pulito)
            scad_fresco, scad_surg = stima_scadenze_da_range(range_scadenza)

            # Default quantità / unità
            quantita = 1
            unita = 'pacchetti'

            # Controlla la riga successiva per peso/quantità
            if i + 1 < len(righe):
                riga_next = righe[i + 1]
                # Se contiene kg/g o la forma classica di peso, usiamo quella riga
                if ('kg' in riga_next.lower() or ' g' in riga_next.lower() or 'eur/kg' in riga_next.lower()):
                    q, u = estrai_quantita_e_unita(riga_next, nome_originale=nome_originale)
                    quantita, unita = q, u

                    prodotti.append({
                        'nome': nome_pulito.title(),
                        'quantita': quantita,
                        'unita': unita,
                        'categoria': categoria,
                        'range_scadenza': range_scadenza,
                        'scadenza_suggerita': scad_fresco,
                        'scadenza_surgelato': scad_surg
                    })

                    i += 2
                    continue

            # Se non c'è riga successiva utile, prova comunque a estrarre dal nome stesso
            q_nome, u_nome = estrai_quantita_e_unita_da_nome(nome_originale)
            if q_nome is not None:
                quantita, unita = q_nome, u_nome

            prodotti.append({
                'nome': nome_pulito.title(),
                'quantita': quantita,
                'unita': unita,
                'categoria': categoria,
                'range_scadenza': range_scadenza,
                'scadenza_suggerita': scad_fresco,
                'scadenza_surgelato': scad_surg
            })
            i += 1
            continue

        # Righe con prezzo che non abbiamo accoppiato: spesso sconti o righe tecniche
        i += 1

    return prodotti

def analizza_scontrino(image_path):
    """Funzione principale per analizzare lo scontrino"""
    try:
        testo = estrai_testo_da_scontrino(image_path)
        prodotti = identifica_prodotti(testo)

        return {
            'success': True,
            'prodotti': prodotti,
            'testo_completo': testo
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }