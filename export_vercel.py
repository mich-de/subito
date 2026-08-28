"""Genera vercel/index.html a partire da templates/index.html.

Nella pagina non finisce nessun dato. Annunci, prodotti, configurazioni e
registro arrivano da /api/store al momento in cui il browser apre il
tabellone — al contrario di com'era su GitHub Pages, dove i risultati erano
cotti dentro l'HTML e la pagina invecchiava. Percio' questo file
va rigenerato solo quando cambiano il template o i fogli di stile, mai quando
cambiano i risultati di una scansione — ed e' anche il motivo per cui il
tabellone su Vercel non puo' invecchiare come faceva quello su Pages.
"""

import os

TEMPLATE = "templates/index.html"
FOGLI = ("quadro-partenze.css", "style.css")
USCITA = "vercel/index.html"

# Va nel <head>, prima del CSS e prima dello script principale: IS_STATIC e
# CAN_WRITE si calcolano all'analisi dello script, quindi decidere piu' tardi
# sarebbe troppo tardi. STATIC_* sono vuoti apposta — la pagina si disegna
# subito, i dati arrivano un istante dopo.
TESTA = """<script>
    window.API_WRITE = true;
    window.STATIC_ITEMS = [];
    window.STATIC_CONFIGS = {};
    window.STATIC_CONFIG_DATA = {};
    window.STATIC_LOGS = [];
    window.SCAN_CADENCE = 30;
    window.PANEL_HAS_PASSWORD = null;
    window.PANEL_UNLOCKED = false;
  </script>
"""

CODA = """
    <script>
      /* Il ponte verso il repository. Una sola richiesta per aprire il
         tabellone: annunci e registro. La configurazione non viene di qui —
         la chiede la scheda Configurazione, con la password. */
      (function () {
        function avvia() {
          fetch('/api/store', { cache: 'no-store' })
            .then(function (r) { return r.json(); })
            .then(function (d) {
              if (d.error) throw new Error(d.error);
              window.STATIC_ITEMS = d.items || [];
              window.STATIC_CONFIGS = d.configs || {};
              window.STATIC_CONFIG_DATA = d.config || {};
              window.STATIC_LOGS = d.logs || [];
              window.SCAN_CADENCE = d.cadence || 30;
              window.PANEL_HAS_PASSWORD = d.hasPassword !== false;
              window.PANEL_UNLOCKED = d.unlocked === true;
              window.HIDDEN_COUNT = d.hiddenCount || 0;
              if (!d.writable) {
                window.STATIC_LOGS.push({
                  message: 'Scrittura non disponibile: manca lo store Blob o '
                         + 'APP_PASSWORD fra le variabili d\\'ambiente su Vercel.',
                  level: 'error',
                  time: new Date().toTimeString().slice(0, 8)
                });
              }
              if (typeof state === 'object') state.items = window.STATIC_ITEMS;
              if (typeof renderItems === 'function') renderItems(window.STATIC_ITEMS);
              /* La configurazione non si carica qui: la chiede la scheda
                 Configurazione quando la si apre, con la password. */
              if (typeof fetchServerLogs === 'function') fetchServerLogs();
              if (typeof fetchStatus === 'function') fetchStatus();
            })
            .catch(function (e) {
              /* Un tabellone vuoto e muto e' peggio di un tabellone che
                 dichiara cosa non ha funzionato. */
              window.STATIC_LOGS = [{
                message: 'Nessuna risposta da /api/store: ' + e.message,
                level: 'error',
                time: new Date().toTimeString().slice(0, 8)
              }];
              if (typeof fetchServerLogs === 'function') fetchServerLogs();
            });
        }
        if (document.readyState === 'loading') {
          document.addEventListener('DOMContentLoaded', avvia);
        } else {
          avvia();
        }
      })();
    </script>
    </body>
"""


def build():
    os.makedirs("vercel", exist_ok=True)
    with open(TEMPLATE, encoding="utf-8") as f:
        html = f.read()

    # CSS in linea, nello stesso ordine di cascata del template: prima il
    # design system, poi il livello applicativo. In linea e non come file a
    # parte per non doversi inventare un meccanismo di invalidazione della
    # cache quando i fogli cambiano.
    for foglio in FOGLI:
        with open(f"static/{foglio}", encoding="utf-8") as f:
            css = f.read()
        tag = f"<style>\n{css}\n</style>"
        for href in (f"static/{foglio}", f"/static/{foglio}"):
            html = html.replace(f'<link rel="stylesheet" href="{href}">', tag)

    if "</head>" not in html or "</body>" not in html:
        raise SystemExit(f"{TEMPLATE}: manca </head> o </body>, non so dove iniettare.")

    html = html.replace("</head>", TESTA + "</head>", 1)
    html = html.replace("</body>", CODA, 1)

    with open(USCITA, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"{USCITA} pronto ({len(html)} byte). I dati arrivano da /api/store.")


if __name__ == "__main__":
    build()
