"""Ponte fra il tabellone e i dati, tutto dentro i servizi gratuiti di Vercel.

    GET  /api/store   senza password: annunci e registro, e basta.
                      con password: in piu' prodotti, configurazioni, YAML,
                      e gli annunci completi di soglia.
    POST /api/store   riscrive i config/*.yaml su Vercel Blob, oppure aggiorna
                      l'elenco degli annunci nascosti. Password obbligatoria.

La password non protegge piu' soltanto la scrittura: la configurazione non esce
da qui senza. Prima usciva a chiunque aprisse il tabellone, e chiunque poteva
leggere soglie, parole chiave ed esclusioni di tutti i prodotti — cioe' esporre
in chiaro cosa si sta cercando e a quanto si e' disposti a comprarlo.

Chiudere la scheda Configurazione pero' non bastava, e vale la pena scriverlo
perche' e' il tipo di falla che si rifa': ogni annuncio in data/*_results.json
si porta dietro il max_price del prodotto che l'ha trovato. La configurazione
era chiusa a chiave e gli stessi numeri uscivano dalla finestra accanto,
annuncio per annuncio. Da anonimo gli annunci ora escono spogliati (vedi
`spoglia`).

Il tabellone degli annunci resta pubblico: quello e' il suo mestiere.

Di GitHub qui non si usa nessuna credenziale. Le due sorgenti sono:

  * **Vercel Blob** per la configurazione. E' la cassetta postale fra il
    pannello e lo scanner: il browser scrive qui, il workflow legge da qui a
    ogni giro. Il token lo inietta Vercel da solo quando lo store e' collegato
    al progetto, quindi non c'e' niente da creare ne' da incollare.

  * **raw.githubusercontent.com** per i dati delle scansioni, che nascono su
    Actions e vivono nel repository. E' una lettura di file pubblici via CDN:
    nessun token, e soprattutto nessun limite di 60 richieste l'ora come
    sull'API di GitHub — che su Vercel, dove l'indirizzo IP e' condiviso con
    mezzo mondo, si sarebbe esaurito in fretta e senza spiegazioni.

Sulla configurazione comanda il Blob: se un file e' stato salvato dal pannello,
quella e' la versione buona e il workflow la riporta nel repository a ogni
scansione. Finche' non salvi mai dal pannello vale quella del repository, che
serve anche da primo riempimento.
"""

import hmac
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler
from io import StringIO

from ruamel.yaml import YAML

REPO = os.environ.get("GITHUB_REPO", "mich-de/subito")
BRANCH = os.environ.get("GITHUB_BRANCH", "main")
PASSWORD = os.environ.get("APP_PASSWORD", "")

# Iniettato da Vercel quando lo store Blob e' collegato al progetto. Se manca,
# il tabellone resta in sola lettura e lo dice nel registro.
BLOB_TOKEN = os.environ.get("BLOB_READ_WRITE_TOKEN", "")

RAW = f"https://raw.githubusercontent.com/{REPO}/{BRANCH}/"
CONFIG_FILES = ["config.yaml", "subito.yaml", "amazon.yaml", "northladder.yaml"]
# Elenco fisso invece di chiedere l'indice della cartella: quello richiederebbe
# l'API di GitHub, cioe' proprio la cosa a cui vogliamo smettere di appoggiarci.
DATA_FILES = ["subitoscanner_results.json", "amazonscanner_results.json",
              "northladderscanner_results.json"]
WORKFLOW = ".github/workflows/scanner.yml"
# Le due annotazioni che il tabellone tiene sugli annunci: quelli tolti di
# mezzo e quelli marcati come truffa. Stanno fuori da config/ perche' l'indice
# dei config si legge per prefisso e non devono finirci in mezzo; sync_config.py,
# che ritira solo i quattro YAML, non li vede nemmeno.
#
# Sono due elenchi separati e non un file solo con due chiavi: un salvataggio
# che va storto rovina una sola delle due cose, e nascondere resta possibile
# anche se le segnalazioni sono illeggibili.
NASCOSTI = "state/nascosti.json"
SEGNALATI = "state/segnalati.json"
ELENCHI = (NASCOSTI, SEGNALATI)

# Round-trip: senza questo i commenti dentro config.yaml — quelli che spiegano
# perche' esiste la keyword "256gb" o l'esclusione "custodi" — sparirebbero al
# primo salvataggio dal browser.
_yaml = YAML()
_yaml.preserve_quotes = True
# Misura larga: a 80 colonne ruamel manda a capo dopo i due punti i valori
# lunghi e inspezzabili (search_url, l'header Accept) lasciandoci pure uno
# spazio in coda. Allargando restano su una riga, come li scriverebbe una
# persona.
_yaml.width = 4096


def fetch(url, headers=None, data=None, method="GET", timeout=20):
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("User-Agent", "offerte-monitor")
    for chiave, valore in (headers or {}).items():
        req.add_header(chiave, valore)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def parallel(fn, chiavi):
    with ThreadPoolExecutor(max_workers=8) as pool:
        return dict(zip(chiavi, pool.map(fn, chiavi)))


# ------------------------------------------------------------ repository ---

def raw_file(path):
    """Contenuto di un file pubblico del repository, None se non c'e'."""
    try:
        return fetch(RAW + path).decode("utf-8")
    except urllib.error.HTTPError as e:
        if e.code in (403, 404):
            return None
        raise
    except Exception:
        return None


# ------------------------------------------------------------------ blob ---

BLOB_API = "https://blob.vercel-storage.com"
# L'API HTTP di Blob non e' documentata da Vercel, che pubblica solo l'SDK
# JavaScript. Questa versione e' quella che usano i client in circolazione; se
# un giorno Vercel la cambia, il salvataggio smette di funzionare e lo dice —
# la lettura, che passa dagli indirizzi pubblici, continua comunque.
BLOB_API_VERSION = "10"


def blob_headers(extra=None):
    intestazioni = {"authorization": "Bearer " + BLOB_TOKEN,
                    "x-api-version": BLOB_API_VERSION}
    intestazioni.update(extra or {})
    return intestazioni


def blob_index(prefisso="config/"):
    """{pathname: (url pubblico, data di caricamento)} dei blob gia' salvati.

    L'elenco arriva dall'API autenticata, che non passa dalla CDN: e' sempre
    aggiornato, ed e' da qui che si prende la marca temporale con cui rileggere
    il contenuto senza incappare nella copia in cache.
    """
    if not BLOB_TOKEN:
        return {}
    try:
        url = f"{BLOB_API}?prefix={urllib.parse.quote(prefisso)}&limit=100"
        risposta = json.loads(fetch(url, blob_headers()).decode("utf-8"))
    except Exception:
        # Blob irraggiungibile o token scaduto: si continua col repository.
        # Meglio una configurazione vecchia di un tabellone bianco.
        return {}
    return {b["pathname"]: (b["url"], str(b.get("uploadedAt") or ""))
            for b in risposta.get("blobs", [])
            if b.get("pathname") and b.get("url")}


def blob_get(url, versione=""):
    """Contenuto di un blob dal suo indirizzo pubblico.

    Gli indirizzi pubblici passano dalla CDN, che tiene il file in cache per il
    minuto dichiarato alla scrittura. Un minuto e' niente per il tabellone, ma
    e' abbastanza per fare danni al salvataggio: due modifiche a distanza di
    trenta secondi e la seconda partirebbe da una copia vecchia, riportando
    indietro la prima. La marca temporale in coda cambia la chiave di cache e
    costringe a rileggere davvero. Se dovesse dare fastidio si ripiega
    sull'indirizzo nudo, che nel caso peggiore e' vecchio di un minuto.
    """
    for tentativo in ([f"{url}?v={urllib.parse.quote(versione)}"] if versione else []) + [url]:
        try:
            return fetch(tentativo).decode("utf-8")
        except Exception:
            continue
    return None


def blob_put(pathname, testo, tipo="text/yaml; charset=utf-8"):
    intestazioni = blob_headers({
        "access": "public",
        "x-content-type": tipo,
        # Un minuto, non un anno com'e' il default: questo file cambia quando
        # tocchi il pannello, e la scansione successiva deve vedere il nuovo.
        "x-cache-control-max-age": "60",
        # Senza questo Blob rifiuta di riscrivere un percorso che esiste gia',
        # e qui si riscrive sempre lo stesso.
        "x-allow-overwrite": "1",
    })
    url = f"{BLOB_API}/?pathname={urllib.parse.quote(pathname)}"
    risposta = fetch(url, intestazioni, data=testo.encode("utf-8"),
                     method="PUT")
    return json.loads(risposta.decode("utf-8"))


def leggi_config():
    """I quattro YAML: dal Blob se ci sono, altrimenti dal repository."""
    indice = blob_index()
    testi = parallel(raw_file, [f"config/{n}" for n in CONFIG_FILES])
    fuori = {n: testi.get(f"config/{n}") for n in CONFIG_FILES}

    da_blob = [n for n in CONFIG_FILES if f"config/{n}" in indice]
    if da_blob:
        salvati = parallel(lambda n: blob_get(*indice[f"config/{n}"]), da_blob)
        for nome, testo in salvati.items():
            if testo:
                fuori[nome] = testo
            else:
                # Il blob c'e' ma non si e' riuscito a leggerlo: resta la
                # versione del repository, gia' in "fuori", e il nome esce
                # dall'elenco per non dichiarare una provenienza falsa.
                da_blob = [x for x in da_blob if x != nome]
    return fuori, set(da_blob)


def _indirizzi(testo):
    """Gli URL dentro un elenco JSON. Insieme vuoto per qualunque guaio.

    Un elenco illeggibile non deve fermare il tabellone: nel peggiore dei casi
    si perde un'annotazione, e questo e' meglio di una pagina che non si apre.
    """
    if not testo:
        return set()
    try:
        dati = json.loads(testo)
    except json.JSONDecodeError:
        return set()
    if not isinstance(dati, list):
        return set()
    return {u for u in dati if isinstance(u, str)}


def leggi_elenchi():
    """I due elenchi che il tabellone tiene su Blob: {percorso: set(url)}.

    Nascondere o segnalare un annuncio non puo' voler dire scriverlo in
    data/*_results.json: quei file li riscrive lo scanner da capo a ogni giro,
    e la funzione non ha — di proposito — nessuna credenziale per scrivere nel
    repository. Un'annotazione messa li' sparirebbe alla scansione successiva.

    Quindi le annotazioni stanno da parte e si applicano in lettura:
    sopravvivono a qualunque riscrittura dei risultati e sono reversibili —
    l'annuncio non e' toccato, gli si mette accanto un cartellino.

    Un solo giro di indice per tutti e due: stanno sotto lo stesso prefisso, e
    chiederlo due volte sarebbe una richiesta buttata a ogni apertura.
    """
    indice = blob_index("state/")
    voci = {p: indice[p] for p in ELENCHI if p in indice}
    testi = parallel(lambda p: blob_get(*voci[p]), list(voci)) if voci else {}
    return {p: _indirizzi(testi.get(p)) for p in ELENCHI}


def scrivi_elenco(percorso, urls):
    blob_put(percorso, json.dumps(sorted(urls), ensure_ascii=False),
             "application/json; charset=utf-8")


def load_yaml(text):
    if not text:
        return None
    try:
        return _yaml.load(text)
    except Exception:
        return None


def dump_yaml(node):
    buf = StringIO()
    _yaml.dump(node, buf)
    return buf.getvalue()


# ------------------------------------------------------------------ GET ----

# Chiudere la scheda Configurazione non bastava: ogni annuncio in
# data/*_results.json si porta dietro la soglia del prodotto che l'ha trovato.
# Con product_name accanto, il tabellone pubblico diceva per esteso cosa si
# cerca e a quanto si e' disposti a comprarlo — cioe' esattamente il segreto che
# la password doveva proteggere, servito dalla porta di servizio.
#
# near_miss se ne va con lui. Da solo e' un booleano, ma insieme al prezzo
# stringe la soglia fra il piu' caro "in soglia" e il piu' economico "oltre":
# due annunci bastano per inquadrarla a poche decine di euro.
SOGLIE_NEGLI_ANNUNCI = ("max_price", "near_miss")


def spoglia(annuncio):
    """L'annuncio senza i campi che raccontano la soglia. Vale solo da anonimo."""
    if not isinstance(annuncio, dict):
        return annuncio
    return {k: v for k, v in annuncio.items() if k not in SOGLIE_NEGLI_ANNUNCI}


def forma_config(configs):
    """Dai quattro YAML alla forma che il modulo Configurazione compila.

    Sta fuori da build_payload perche' la costruzione e' abbastanza lunga da
    meritare un nome, e perche' il giorno che serva anche altrove non nasca una
    seconda versione che col tempo dice cose diverse.
    """
    cfg = load_yaml(configs.get("config.yaml")) or {}
    scanner = cfg.get("scanner", {}) or {}
    telegram = cfg.get("telegram", {}) or {}

    dati = {
        "general": {
            "interval_minutes": scanner.get("interval_minutes", 10),
            "shipping_required": scanner.get("shipping_required", True),
        },
        "telegram": {
            # Il token Telegram non esce da qui: vive nei secret di Actions e
            # in config.yaml c'e' solo un segnaposto. Mandarlo al browser non
            # servirebbe a niente e sarebbe solo un rischio.
            "enabled": telegram.get("enabled", True),
            "bot_token": "",
            "chat_id": "",
        },
        "products": json.loads(json.dumps(scanner.get("products", []) or [])),
    }
    for chiave in ("subito", "amazon"):
        s = load_yaml(configs.get(f"{chiave}.yaml")) or {}
        dati[chiave] = {
            "enabled": s.get("enabled", True),
            "max_pages": s.get("max_pages", 3),
        }
    return dati


def build_payload(autorizzato):
    """Ricostruisce quello che il build statico iniettava nella pagina.

    Stessi nomi e stessa forma, cosi' la pagina usa il percorso di lettura che
    aveva gia' e l'unica differenza e' da dove arrivano i dati.

    Senza password escono solo annunci e registro. La parte di configurazione
    non viene nemmeno letta: sono quattro richieste in meno, quindi il
    tabellone pubblico si apre anche piu' in fretta.
    """
    grezzi = parallel(raw_file, [f"data/{n}" for n in DATA_FILES] + [WORKFLOW])

    elenchi = leggi_elenchi()
    # Il filtro vale per tutti, non solo per chi ha la password: un annuncio
    # tolto dal tabellone deve sparire dal tabellone, non solo dal tuo.
    nascosti = elenchi[NASCOSTI]
    # La segnalazione invece no. Dire «questa e' una truffa» e' un'accusa a un
    # annuncio identificabile, e non ha motivo di comparire su una pagina che
    # apre chiunque: e' un appunto per chi cerca, non un cartello per la
    # strada. Chi ha la password la vede, gli altri vedono l'annuncio e basta.
    segnalati = elenchi[SEGNALATI] if autorizzato else set()

    items = []
    conteggi = {}
    for nome in DATA_FILES:
        try:
            dati = json.loads(grezzi.get(f"data/{nome}") or "[]")
        except json.JSONDecodeError:
            dati = []
        if isinstance(dati, list):
            visibili = [i for i in dati
                        if not (isinstance(i, dict) and i.get("url") in nascosti)]
            if autorizzato:
                visibili = [dict(i, scam=True) if i.get("url") in segnalati else i
                            for i in visibili]
            else:
                visibili = [spoglia(i) for i in visibili]
            items.extend(visibili)
            conteggi[nome] = len(visibili)

    configs, dal_blob, config_data = {}, set(), {}
    if autorizzato:
        configs, dal_blob = leggi_config()
        config_data = forma_config(configs)

    cadenza = 30
    m = re.search(r"cron:\s*['\"]\*/(\d+)", grezzi.get(WORKFLOW) or "")
    if m:
        cadenza = int(m.group(1))

    ora = datetime.now(timezone(timedelta(hours=2))).strftime("%H:%M:%S")
    if autorizzato:
        origine = "Vercel Blob" if dal_blob else "repository"
        logs = [{"message": f"Configurazione letta da {origine} — "
                            f"{len(config_data['products'])} prodotti monitorati.",
                 "level": "info", "time": ora}]
    else:
        # Nemmeno il numero di prodotti: sarebbe gia' un'informazione su cosa
        # si sta cercando, e questa riga la legge chiunque apra la pagina.
        logs = [{"message": "Configurazione protetta da password — "
                            "apri la scheda Configurazione per sbloccarla.",
                 "level": "info", "time": ora}]
    for etichetta, nome in (("SUBITO.IT", "subitoscanner_results.json"),
                            ("AMAZON.IT", "amazonscanner_results.json"),
                            ("NORTHLADDER", "northladderscanner_results.json")):
        n = conteggi.get(nome)
        if n is None:
            logs.append({"message": f"[{etichetta}] Nessun risultato pubblicato.",
                         "level": "error", "time": ora})
        else:
            logs.append({"message": f"[{etichetta}] {n} annunci dall'ultima scansione.",
                         "level": "found" if n else "scan", "time": ora})
    if nascosti:
        logs.append({"message": f"{len(nascosti)} annunci nascosti dal pannello — "
                                "si ripristinano dalla scheda Configurazione.",
                     "level": "info", "time": ora})
    if segnalati:
        logs.append({"message": f"{len(segnalati)} annunci segnalati come truffa: "
                                "restano sul tabellone marcati, ma non contano "
                                "per il minimo e la media.",
                     "level": "warning", "time": ora})
    scrivibile = bool(BLOB_TOKEN and PASSWORD)
    logs.append({"message": f"Scansione ogni {cadenza} minuti. " + (
        "Il pannello salva su Vercel Blob e la scansione seguente lo raccoglie."
        if scrivibile else
        "Salvataggio spento: manca lo store Blob o la password."),
        "level": "info", "time": ora})

    return {
        "items": items,
        "config": config_data,
        "configs": {n: t for n, t in configs.items() if t},
        "logs": logs,
        "cadence": cadenza,
        "writable": scrivibile,
        # La pagina deve sapere se le manca la password o se la password non
        # esiste proprio: nel primo caso la chiede, nel secondo dice che il
        # pannello e' spento e non fa comparire un prompt inutile.
        "hasPassword": bool(PASSWORD),
        "unlocked": autorizzato,
        "hiddenCount": len(nascosti),
        "scamCount": len(segnalati),
    }


# ----------------------------------------------------------------- POST ----

# Le due annotazioni si comportano allo stesso modo — aggiungi, togli, azzera —
# e la sola differenza e' come si raccontano. Descriverle in una tabella invece
# di scrivere due rami gemelli: quando ne servira' una terza, si aggiunge una
# riga qui e non si copia niente.
ANNOTAZIONI = {
    "hide": {
        "elenco": NASCOSTI,
        "togli": "unhide",
        "azzera": "unhideAll",
        "conteggio": "hiddenCount",
        "aggiunti": "{n} annunci tolti dal tabellone.",
        "tolti": "{n} annunci rimessi. Ne restano {resto} nascosti.",
        "vuoto": "Tabellone ripristinato: nessun annuncio nascosto.",
    },
    "scam": {
        "elenco": SEGNALATI,
        "togli": "unscam",
        "azzera": "unscamAll",
        "conteggio": "scamCount",
        "aggiunti": "{n} annunci segnalati come truffa.",
        "tolti": "{n} segnalazioni ritirate. Ne restano {resto}.",
        "vuoto": "Nessun annuncio segnalato come truffa.",
    },
}


def applica_annotazione(dati):
    """Aggiorna nascosti o segnalati. None se la richiesta non ne parla.

    Restituire None invece di sollevare tiene il POST leggibile: chi chiama
    prova, e se la richiesta era per gli YAML prosegue per la sua strada.
    """
    def indirizzi(chiave):
        valore = dati.get(chiave) or []
        if isinstance(valore, str):
            valore = [valore]
        return {u for u in valore if isinstance(u, str) and u.strip()}

    for aggiungi, regole in ANNOTAZIONI.items():
        if not (aggiungi in dati or regole["togli"] in dati
                or dati.get(regole["azzera"])):
            continue

        prima = leggi_elenchi()[regole["elenco"]]
        if dati.get(regole["azzera"]):
            dopo = set()
        else:
            dopo = (prima | indirizzi(aggiungi)) - indirizzi(regole["togli"])

        if dopo == prima:
            return {"ok": True, "changed": False,
                    regole["conteggio"]: len(prima), "message": "Nessuna modifica."}

        scrivi_elenco(regole["elenco"], dopo)
        quanti = len(dopo) - len(prima)
        if quanti > 0:
            messaggio = regole["aggiunti"].format(n=quanti)
        elif dopo:
            messaggio = regole["tolti"].format(n=-quanti, resto=len(dopo))
        else:
            messaggio = regole["vuoto"]
        return {"ok": True, "changed": True,
                regole["conteggio"]: len(dopo), "message": messaggio}
    return None


def merge_products(esistenti, in_arrivo):
    """Aggiorna la lista dei prodotti sul posto invece di sostituirla.

    Sostituirla in blocco funzionerebbe, ma cancellerebbe i commenti di tutti i
    prodotti — anche di quelli che nessuno ha toccato. Qui i nodi gia' presenti
    vengono modificati campo per campo, quindi i loro commenti restano attaccati
    dove sono; perdono i commenti solo i prodotti davvero nuovi, che non ne
    hanno.
    """
    per_nome = {p.get("name"): p for p in (esistenti or []) if isinstance(p, dict)}
    ordinati = []
    for voce in in_arrivo:
        nome = voce.get("name")
        nodo = per_nome.get(nome)
        if nodo is None:
            ordinati.append(voce)
            continue
        for chiave, valore in voce.items():
            # Solo se cambia davvero. Riassegnare una lista identica la
            # sostituirebbe con una lista semplice arrivata dal browser, e con
            # lei se ne andrebbero i commenti che stanno fra le sue voci —
            # quello sulla keyword "256gb", per dirne uno.
            if chiave in nodo and nodo[chiave] == valore:
                continue
            nodo[chiave] = valore
        for chiave in [k for k in nodo if k not in voce]:
            del nodo[chiave]
        ordinati.append(nodo)
    return ordinati


def cambiato(originale, nodo):
    """Il file e' davvero cambiato, o e' solo ruamel che riscrive a modo suo?

    Confrontare il nuovo testo con quello di partenza direbbe «cambiato» anche
    quando non si e' toccato niente, perche' la resa di ruamel non coincide
    riga per riga con quella di PyYAML che ha scritto i file. Il paragone
    giusto e' fra due rese dello stesso strumento: quella del file com'era e
    quella del file com'e' adesso.
    """
    reso = dump_yaml(nodo)
    return (reso != dump_yaml(load_yaml(originale))), reso


def apply_changes(testi, dati):
    """Restituisce {nome file: nuovo contenuto} per i soli file che cambiano."""
    fuori = {}

    cfg = load_yaml(testi.get("config.yaml"))
    if cfg is None:
        raise ValueError("config.yaml illeggibile")

    generale = dati.get("general") or {}
    if "interval_minutes" in generale:
        cfg["scanner"]["interval_minutes"] = int(generale["interval_minutes"])
    if "shipping_required" in generale:
        cfg["scanner"]["shipping_required"] = bool(generale["shipping_required"])

    telegram = dati.get("telegram") or {}
    if "enabled" in telegram:
        cfg["telegram"]["enabled"] = bool(telegram["enabled"])
    # bot_token e chat_id non si toccano: vivono nei secret di Actions e il
    # browser non li riceve nemmeno, quindi riscriverli significherebbe
    # sovrascrivere il segnaposto con una stringa vuota.

    prodotti = dati.get("products")
    if isinstance(prodotti, list) and prodotti:
        cfg["scanner"]["products"] = merge_products(cfg["scanner"].get("products"), prodotti)

    diverso, reso = cambiato(testi["config.yaml"], cfg)
    if diverso:
        fuori["config.yaml"] = reso

    for chiave in ("subito", "amazon"):
        blocco = dati.get(chiave)
        if not blocco:
            continue
        nome = f"{chiave}.yaml"
        nodo = load_yaml(testi.get(nome))
        if nodo is None:
            continue
        if "enabled" in blocco:
            nodo["enabled"] = bool(blocco["enabled"])
        if "max_pages" in blocco:
            nodo["max_pages"] = int(blocco["max_pages"])
        diverso, reso = cambiato(testi[nome], nodo)
        if diverso:
            fuori[nome] = reso

    return fuori


def salva(files):
    """Scrive i file cambiati sul Blob e restituisce i nomi salvati.

    Prima li carica tutti e poi risponde: se uno fallisce si solleva, e il
    pannello lo dice invece di far credere che sia andato tutto a posto.
    """
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda kv: blob_put(f"config/{kv[0]}", kv[1]),
                      sorted(files.items())))
    return sorted(files)


# -------------------------------------------------------------- handler ----

class handler(BaseHTTPRequestHandler):

    def _send(self, code, payload, cache=None):
        corpo = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", cache or "no-store")
        # Da quando la configurazione dipende dalla password, due richieste
        # allo stesso indirizzo possono meritare due risposte diverse. Senza
        # questo, la cache di bordo potrebbe servire a un anonimo la copia
        # preparata per chi la password ce l'aveva.
        self.send_header("Vary", "x-auth-token")
        self.end_headers()
        self.wfile.write(corpo)

    def _autorizzato(self):
        if not PASSWORD:
            return False
        fornita = self.headers.get("x-auth-token") or ""
        return hmac.compare_digest(fornita, PASSWORD)

    def do_GET(self):
        autorizzato = self._autorizzato()
        try:
            # Senza password si risponde lo stesso, ma con meno dentro: niente
            # configurazione, e gli annunci spogliati della soglia. Non un 401,
            # perche' il tabellone deve aprirsi per chiunque — a chiudersi e'
            # solo la parte che racconta cosa si cerca.
            #
            # Un minuto di cache al bordo: la scansione gira ogni trenta, quindi
            # ricaricare la pagina due volte di fila non deve rileggere tutto.
            # La risposta autorizzata invece non si mette in cache da nessuna
            # parte: contiene la configurazione, e la cache di bordo di Vercel
            # e' condivisa fra tutti quelli che aprono l'indirizzo.
            self._send(200, build_payload(autorizzato),
                       "no-store" if autorizzato
                       else "public, max-age=0, s-maxage=60")
        except urllib.error.HTTPError as e:
            self._send(502, {"error": f"La sorgente ha risposto {e.code}"})
        except Exception as e:
            self._send(500, {"error": str(e)})

    def do_POST(self):
        if not BLOB_TOKEN:
            self._send(503, {"error": "Store Blob non collegato al progetto su Vercel."})
            return
        if not PASSWORD:
            self._send(503, {"error": "APP_PASSWORD non configurata: scrittura disattivata."})
            return
        if not self._autorizzato():
            self._send(401, {"error": "Password errata."})
            return

        try:
            lunghezza = int(self.headers.get("Content-Length") or 0)
            dati = json.loads(self.rfile.read(lunghezza).decode("utf-8") or "{}")
        except (ValueError, json.JSONDecodeError):
            self._send(400, {"error": "Corpo della richiesta non valido."})
            return

        try:
            # Annotare annunci non c'entra con gli YAML, quindi sta prima di
            # leggi_config(): non deve pagarne le quattro letture.
            esito = applica_annotazione(dati)
            if esito is not None:
                self._send(200, esito)
                return

            configs, _ = leggi_config()

            # L'editor YAML manda un file intero gia' scritto a mano: si
            # controlla solo che sia analizzabile, perche' salvare un YAML
            # rotto fermerebbe la scansione successiva senza dire perche'.
            grezzo = dati.get("yaml")
            if grezzo:
                nome = os.path.basename(str(grezzo.get("name") or ""))
                if nome not in CONFIG_FILES:
                    self._send(400, {"error": f"File non modificabile: {nome or '(vuoto)'}"})
                    return
                testo = grezzo.get("content") or ""
                try:
                    _yaml.load(testo)
                except Exception as e:
                    self._send(400, {"error": f"YAML non valido: {e}"})
                    return
                if testo == (configs.get(nome) or ""):
                    self._send(200, {"ok": True, "changed": False,
                                     "message": "Nessuna modifica da salvare."})
                    return
                salva({nome: testo})
                self._send(200, {
                    "ok": True, "changed": True, "files": [nome],
                    "message": "Salvato. La scansione lo raccoglie al giro seguente.",
                })
                return

            if not configs.get("config.yaml"):
                self._send(502, {"error": "config.yaml non trovato ne' su Blob ne' nel repository."})
                return

            files = apply_changes(configs, dati)
            if not files:
                self._send(200, {"ok": True, "changed": False,
                                 "message": "Nessuna modifica da salvare."})
                return

            salvati = salva(files)
            self._send(200, {
                "ok": True, "changed": True, "files": salvati,
                "message": "Salvato su Vercel Blob. La scansione seguente parte "
                           "con i nuovi prodotti.",
            })
        except urllib.error.HTTPError as e:
            dettaglio = ""
            try:
                dettaglio = (e.read().decode() or "")[:200]
            except Exception:
                pass
            self._send(502, {"error": f"Vercel Blob ha risposto {e.code}. {dettaglio}".strip()})
        except Exception as e:
            self._send(500, {"error": str(e)})
