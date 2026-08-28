"""Ritira dal pannello la configurazione salvata e la mette in config/.

Il tabellone su Vercel non scrive nel repository: scrive su Vercel Blob, che fa
da cassetta postale. Questo script e' il postino, e gira all'inizio di ogni
scansione, prima di run_once.py.

Le regole sono due e sono semplici:

  * se per un file c'e' una versione salvata dal pannello, quella vince e
    sostituisce il file in config/. Il workflow poi la committa, cosi' il
    repository resta lo specchio di cio' che sta davvero girando;

  * se non c'e', o se qualcosa va storto — Blob irraggiungibile, download
    corrotto, YAML illeggibile — non si tocca niente e la scansione parte con
    la configurazione che ha gia'. Un giro con le soglie di ieri e' un guaio
    molto piu' piccolo di un giro che non parte.

Per questo lo script non fallisce mai: esce sempre con zero, e racconta
nell'output cos'ha fatto.

Nessuna credenziale. L'indirizzo dello store e' pubblico — compare in ogni URL
che Blob restituisce — e i file di configurazione stanno gia' in chiaro in un
repository pubblico, quindi non c'e' niente di nuovo da nascondere.
"""

import os
import sys
import time
import urllib.error
import urllib.request

import yaml

STORE_HOST = os.environ.get(
    "BLOB_STORE_HOST", "vtfy61fbjjwabtsu.public.blob.vercel-storage.com")
CONFIG_DIR = "config"
FILES = ["config.yaml", "subito.yaml", "amazon.yaml", "northladder.yaml"]


def scarica(nome):
    """Il file salvato dal pannello, oppure None se non c'e' o non si puo'.

    La marca temporale in coda cambia la chiave di cache a ogni giro: gli
    indirizzi pubblici di Blob passano dalla CDN, e senza quella si rischia di
    riportare a casa la copia della scansione precedente invece di quella
    appena salvata.
    """
    url = f"https://{STORE_HOST}/{CONFIG_DIR}/{nome}?v={int(time.time())}"
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            return resp.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            print(f"  {nome}: mai salvato dal pannello, resta quello del repository")
        else:
            print(f"  {nome}: Blob ha risposto {e.code}, resta quello del repository")
    except Exception as e:
        print(f"  {nome}: {type(e).__name__} — resta quello del repository")
    return None


def main():
    print(f"Configurazione dal pannello — store {STORE_HOST}")
    aggiornati = []

    for nome in FILES:
        testo = scarica(nome)
        if testo is None:
            continue

        # Prima di sovrascrivere: si legge? Un file rotto qui fermerebbe la
        # scansione senza spiegare perche', e il pannello sarebbe gia' chiuso
        # da un pezzo quando qualcuno se ne accorge.
        try:
            if yaml.safe_load(testo) is None:
                raise ValueError("documento vuoto")
        except Exception as e:
            print(f"  {nome}: SCARTATO, non e' YAML valido ({e})")
            continue

        percorso = os.path.join(CONFIG_DIR, nome)
        try:
            with open(percorso, encoding="utf-8", newline="") as f:
                attuale = f.read()
        except FileNotFoundError:
            attuale = None

        # Il confronto ignora il tipo di fine riga. Il file scaricato le ha
        # sempre alla maniera di Unix, quello su disco dipende da come e' stata
        # fatta la checkout: senza questa normalizzazione una checkout Windows
        # troverebbe ogni file "diverso" a ogni giro e il workflow committerebbe
        # una configurazione identica ogni mezz'ora, per sempre.
        def righe(t):
            return t.replace("\r\n", "\n") if t else t

        if righe(testo) == righe(attuale):
            print(f"  {nome}: gia' allineato")
            continue

        with open(percorso, "w", encoding="utf-8", newline="") as f:
            f.write(testo)
        print(f"  {nome}: AGGIORNATO dal pannello ({len(testo)} caratteri)")
        aggiornati.append(nome)

    if aggiornati:
        print(f"\nAggiornati dal pannello: {', '.join(aggiornati)}")
    else:
        print("\nNessuna modifica dal pannello.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
