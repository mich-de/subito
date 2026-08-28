"""Ponte fra il tabellone e il repository GitHub.

    GET  /api/store   tutto cio' che serve alla pagina: annunci, prodotti,
                      configurazioni, registro. Nessuna password: sono gli
                      stessi dati che il repository pubblica gia'.

    POST /api/store   riscrive config/config.yaml, subito.yaml e amazon.yaml
                      in un solo commit. Password obbligatoria.

Il token GitHub vive in una variabile d'ambiente e non lascia mai il server.
E' l'unica ragione per cui questo file esiste invece di far parlare il
browser direttamente con l'API di GitHub: su una pagina pubblica il token
sarebbe leggibile da chiunque apra gli strumenti di sviluppo.

Un solo file e non due (uno per leggere, uno per scrivere) perche' su Vercel
ogni file in api/ e' una funzione a se': tenerli insieme evita di duplicare
il codice di dialogo con GitHub, che e' la parte grossa.
"""

import base64
import hmac
import json
import os
import re
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler
from io import StringIO

from ruamel.yaml import YAML

REPO = os.environ.get("GITHUB_REPO", "mich-de/subito")
BRANCH = os.environ.get("GITHUB_BRANCH", "main")
TOKEN = os.environ.get("GITHUB_TOKEN", "")
PASSWORD = os.environ.get("APP_PASSWORD", "")

CONFIG_FILES = ["config.yaml", "subito.yaml", "amazon.yaml", "northladder.yaml"]
WORKFLOW = ".github/workflows/scanner.yml"

# Round-trip: senza questo i commenti dentro config.yaml — quelli che spiegano
# perche' esiste la keyword "256gb" o l'esclusione "custodi" — sparirebbero al
# primo salvataggio dal browser.
_yaml = YAML()
_yaml.preserve_quotes = True
# Misura larga: a 80 colonne ruamel manda a capo dopo i due punti i valori
# lunghi e inspezzabili (search_url, l'header Accept) lasciandoci pure uno
# spazio in coda. Allargando restano su una riga, come li scriverebbe una
# persona. In cambio lo User-Agent, che nel file e' piegato su due righe, si
# ricompatta: succede una volta sola e solo quando quel file cambia davvero.
_yaml.width = 4096


# ---------------------------------------------------------------- GitHub ---

def gh(path, method="GET", body=None):
    url = path if path.startswith("http") else "https://api.github.com" + path
    payload = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=payload, method=method)
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "offerte-monitor")
    if TOKEN:
        req.add_header("Authorization", "Bearer " + TOKEN)
    if payload is not None:
        req.add_header("Content-Type", "application/json")
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def read_file(path):
    """Contenuto testuale di un file del repository, None se non esiste."""
    try:
        node = gh(f"/repos/{REPO}/contents/{path}?ref={BRANCH}")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    if node.get("encoding") != "base64":
        return None
    return base64.b64decode(node["content"]).decode("utf-8")


def list_dir(path):
    try:
        return gh(f"/repos/{REPO}/contents/{path}?ref={BRANCH}")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return []
        raise


def parallel(fn, keys):
    with ThreadPoolExecutor(max_workers=8) as pool:
        return dict(zip(keys, pool.map(fn, keys)))


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

def build_payload():
    """Ricostruisce quello che export_pages.py inietta nel build statico.

    Stessi nomi e stessa forma: cosi' la pagina usa il percorso di lettura che
    aveva gia', e l'unica differenza fra il tabellone su Pages e questo e' da
    dove arrivano i dati.
    """
    fissi = [f"config/{n}" for n in CONFIG_FILES] + [WORKFLOW]
    testi = parallel(read_file, fissi)

    elenco = [n["path"] for n in list_dir("data")
              if n.get("type") == "file" and n["name"].endswith("scanner_results.json")]
    grezzi = parallel(read_file, sorted(elenco))

    items = []
    conteggi = {}
    for path, testo in sorted(grezzi.items()):
        try:
            dati = json.loads(testo or "[]")
        except json.JSONDecodeError:
            dati = []
        if isinstance(dati, list):
            items.extend(dati)
            conteggi[os.path.basename(path)] = len(dati)

    cfg = load_yaml(testi.get("config/config.yaml")) or {}
    scanner = cfg.get("scanner", {}) or {}
    telegram = cfg.get("telegram", {}) or {}

    config_data = {
        "general": {
            "interval_minutes": scanner.get("interval_minutes", 10),
            "shipping_required": scanner.get("shipping_required", True),
        },
        "telegram": {
            # Il token Telegram non esce da qui: sul server vive nei secret di
            # GitHub Actions, e in config.yaml c'e' solo un segnaposto. Mandarlo
            # al browser non servirebbe a niente e sarebbe solo un rischio.
            "enabled": telegram.get("enabled", True),
            "bot_token": "",
            "chat_id": "",
        },
        "products": json.loads(json.dumps(scanner.get("products", []) or [])),
    }
    for chiave in ("subito", "amazon"):
        s = load_yaml(testi.get(f"config/{chiave}.yaml")) or {}
        config_data[chiave] = {
            "enabled": s.get("enabled", True),
            "max_pages": s.get("max_pages", 3),
        }

    cadenza = 30
    m = re.search(r"cron:\s*['\"]\*/(\d+)", testi.get(WORKFLOW) or "")
    if m:
        cadenza = int(m.group(1))

    ora = datetime.now(timezone(timedelta(hours=2))).strftime("%H:%M:%S")
    logs = [{"message": f"Dati letti dal repository {REPO} — "
                        f"{len(config_data['products'])} prodotti monitorati.",
             "level": "info", "time": ora}]
    for etichetta, nome in (("SUBITO.IT", "subitoscanner_results.json"),
                            ("AMAZON.IT", "amazonscanner_results.json"),
                            ("NORTHLADDER", "northladderscanner_results.json")):
        n = conteggi.get(nome)
        if n is None:
            logs.append({"message": f"[{etichetta}] Nessun risultato nel repository.",
                         "level": "error", "time": ora})
        else:
            logs.append({"message": f"[{etichetta}] {n} annunci dall'ultima scansione.",
                         "level": "found" if n else "scan", "time": ora})
    logs.append({"message": f"Scansione via GitHub Actions ogni {cadenza} minuti. "
                            f"Il pannello configurazione scrive sul repository.",
                 "level": "info", "time": ora})

    return {
        "items": items,
        "config": config_data,
        "configs": {n: testi.get(f"config/{n}") or "" for n in CONFIG_FILES
                    if testi.get(f"config/{n}")},
        "logs": logs,
        "cadence": cadenza,
        "writable": bool(TOKEN and PASSWORD),
    }


# ----------------------------------------------------------------- POST ----

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

    Confrontare il nuovo testo con quello del repository direbbe «cambiato»
    anche quando non si e' toccato niente, perche' la resa di ruamel non
    coincide riga per riga con quella di PyYAML che ha scritto i file. Il
    paragone giusto e' fra due rese dello stesso strumento: quella del file
    com'era e quella del file com'e' adesso.
    """
    reso = dump_yaml(nodo)
    return (reso != dump_yaml(load_yaml(originale))), reso


def apply_changes(testi, dati):
    """Restituisce {percorso: nuovo contenuto} per i soli file che cambiano."""
    fuori = {}

    cfg = load_yaml(testi["config/config.yaml"])
    if cfg is None:
        raise ValueError("config/config.yaml illeggibile nel repository")

    generale = dati.get("general") or {}
    if "interval_minutes" in generale:
        cfg["scanner"]["interval_minutes"] = int(generale["interval_minutes"])
    if "shipping_required" in generale:
        cfg["scanner"]["shipping_required"] = bool(generale["shipping_required"])

    telegram = dati.get("telegram") or {}
    if "enabled" in telegram:
        cfg["telegram"]["enabled"] = bool(telegram["enabled"])
    # bot_token e chat_id non si toccano: vivono nei secret di GitHub Actions e
    # il browser non li riceve nemmeno, quindi riscriverli significherebbe
    # sovrascrivere il segnaposto con una stringa vuota.

    prodotti = dati.get("products")
    if isinstance(prodotti, list) and prodotti:
        cfg["scanner"]["products"] = merge_products(cfg["scanner"].get("products"), prodotti)

    diverso, reso = cambiato(testi["config/config.yaml"], cfg)
    if diverso:
        fuori["config/config.yaml"] = reso

    for chiave in ("subito", "amazon"):
        blocco = dati.get(chiave)
        if not blocco:
            continue
        percorso = f"config/{chiave}.yaml"
        nodo = load_yaml(testi.get(percorso))
        if nodo is None:
            continue
        if "enabled" in blocco:
            nodo["enabled"] = bool(blocco["enabled"])
        if "max_pages" in blocco:
            nodo["max_pages"] = int(blocco["max_pages"])
        diverso, reso = cambiato(testi[percorso], nodo)
        if diverso:
            fuori[percorso] = reso

    return fuori


def commit(files, messaggio):
    """Un commit solo per tutti i file.

    Tre PUT su /contents sarebbero tre commit, e fra il primo e il terzo il
    repository resterebbe in uno stato che nessuno ha mai chiesto. Con l'API
    Git l'aggiornamento e' unico e atomico.
    """
    ref = gh(f"/repos/{REPO}/git/ref/heads/{BRANCH}")
    padre = ref["object"]["sha"]
    base = gh(f"/repos/{REPO}/git/commits/{padre}")["tree"]["sha"]

    albero = gh(f"/repos/{REPO}/git/trees", "POST", {
        "base_tree": base,
        "tree": [{"path": p, "mode": "100644", "type": "blob", "content": c}
                 for p, c in files.items()],
    })
    nuovo = gh(f"/repos/{REPO}/git/commits", "POST", {
        "message": messaggio,
        "tree": albero["sha"],
        "parents": [padre],
    })
    gh(f"/repos/{REPO}/git/refs/heads/{BRANCH}", "PATCH", {"sha": nuovo["sha"]})
    return nuovo["sha"]


# -------------------------------------------------------------- handler ----

class handler(BaseHTTPRequestHandler):

    def _send(self, code, payload, cache=None):
        corpo = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(corpo)))
        self.send_header("Cache-Control", cache or "no-store")
        self.end_headers()
        self.wfile.write(corpo)

    def _autorizzato(self):
        if not PASSWORD:
            return False
        fornita = self.headers.get("x-auth-token") or ""
        return hmac.compare_digest(fornita, PASSWORD)

    def do_GET(self):
        try:
            # Un minuto di cache al bordo: la scansione gira ogni trenta, quindi
            # ricaricare la pagina due volte di fila non deve ricontattare
            # GitHub sei volte.
            self._send(200, build_payload(), "public, max-age=0, s-maxage=60")
        except urllib.error.HTTPError as e:
            self._send(502, {"error": f"GitHub ha risposto {e.code}"})
        except Exception as e:
            self._send(500, {"error": str(e)})

    def do_POST(self):
        if not TOKEN:
            self._send(503, {"error": "GITHUB_TOKEN non configurato su Vercel."})
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
            # L'editor YAML manda un file intero gia' scritto a mano: si
            # controlla solo che sia analizzabile, perche' committare un YAML
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
                percorso = f"config/{nome}"
                if testo == (read_file(percorso) or ""):
                    self._send(200, {"ok": True, "changed": False,
                                     "message": "Nessuna modifica da salvare."})
                    return
                sha = commit({percorso: testo},
                             f"Aggiorna {percorso} dall'editor del pannello")
                self._send(200, {
                    "ok": True, "changed": True, "commit": sha[:7], "files": [percorso],
                    "url": f"https://github.com/{REPO}/commit/{sha}",
                    "message": "Salvato. La scansione riparte da sola.",
                })
                return

            percorsi = [f"config/{n}" for n in ("config.yaml", "subito.yaml", "amazon.yaml")]
            testi = parallel(read_file, percorsi)
            if not testi.get("config/config.yaml"):
                self._send(502, {"error": "config/config.yaml non trovato nel repository."})
                return

            files = apply_changes(testi, dati)
            if not files:
                self._send(200, {"ok": True, "changed": False,
                                 "message": "Nessuna modifica da salvare."})
                return

            sha = commit(files, "Aggiorna la configurazione dal pannello\n\n"
                                "Scritto da " + ", ".join(sorted(files)) + " via /api/store.")
            self._send(200, {
                "ok": True, "changed": True, "commit": sha[:7],
                "files": sorted(files),
                "url": f"https://github.com/{REPO}/commit/{sha}",
                "message": "Salvato. La scansione riparte da sola con i nuovi prodotti.",
            })
        except urllib.error.HTTPError as e:
            dettaglio = ""
            try:
                dettaglio = json.loads(e.read().decode()).get("message", "")
            except Exception:
                pass
            self._send(502, {"error": f"GitHub ha risposto {e.code}. {dettaglio}".strip()})
        except Exception as e:
            self._send(500, {"error": str(e)})
