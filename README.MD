# Offerte Monitor

Segue il prezzo di alcuni telefoni su **Subito.it**, **Amazon.it** e la
valutazione di permuta **NorthLadder**. Quando ne compare uno entro la soglia
che hai deciso, arriva un messaggio su Telegram; tutti gli altri finiscono su un
tabellone che puoi guardare quando vuoi.

**Tabellone:** https://subito-it.vercel.app/

Il tuo computer non c'entra niente: gira tutto da solo, in cloud, anche a
macchina spenta.

---

## Chi fa cosa

Il sistema sta su **due servizi**, e la divisione è netta.

| | GitHub | Vercel |
|---|---|---|
| Scansiona i siti | ✅ | ✗ |
| Manda le notifiche Telegram | ✅ | ✗ |
| Conserva i dati delle scansioni | ✅ | ✗ |
| Mostra il tabellone | ✗ | ✅ |
| Salva la configurazione e i pulsanti | ✗ | ✅ |

### GitHub è il motore

`.github/workflows/scanner.yml` accende una macchina Ubuntu **ai minuti 7 e 37
di ogni ora**, ci installa Python e Chromium, e la fa lavorare per circa tredici
minuti:

```
sync_config.py     ritira dal pannello la configurazione salvata
run_once.py        scansiona, confronta con le soglie, notifica su Telegram
export_vercel.py   rigenera il tabellone se hai toccato template o CSS
git commit         riscrive data/*.json nel repository
```

**Perché i minuti 7 e 37 e non `*/30`:** GitHub non garantisce i cron, e quando i
runner sono carichi scarta le esecuzioni programmate. I minuti `:00` e `:30` sono
i due più affollati dell'ora, perché ci finisce il cron di chiunque scriva
`*/30`. Con quella scrittura, a fine agosto 2026, ne partivano sette al giorno su
quarantotto. Spostarsi di sette minuti non cambia niente per noi e toglie di
mezzo la coda.

### Vercel è la vetrina

Una sola funzione Python, `vercel/api/store.py`, che fa due cose:

* **in lettura** raccoglie gli annunci da `raw.githubusercontent.com` e la
  configurazione da Vercel Blob, e li serve al browser;
* **in scrittura** salva su Blob quello che cambi dal pannello — soglie, parole
  chiave, e i tre elenchi dei pulsanti di riga.

La pagina `vercel/index.html` **non contiene nessun dato**: li chiede a
`/api/store` quando la apri. Per questo non può invecchiare, e per questo non va
ricommittata a ogni scansione.

---

## Il giro completo

```
        tu, dal telefono o dal browser
                    │
                    ▼
        ┌───────────────────────┐
        │  subito-it.vercel.app │   il tabellone
        └───────────┬───────────┘
                    │ salvi qualcosa
                    ▼
        ┌───────────────────────┐
        │     Vercel Blob       │   la cassetta postale
        └───────────┬───────────┘
                    │ sync_config.py la svuota
                    ▼
        ┌───────────────────────┐
        │    GitHub Actions     │   la scansione, ogni 30 minuti
        └───────┬───────────┬───┘
                │           │
     Telegram ◄─┘           └─► data/*.json nel repository
                                        │
                                        ▼
                            raw.githubusercontent.com
                                        │
                                        └─► torna al tabellone
```

Il pannello **non scrive nel repository**: la funzione su Vercel non ha, di
proposito, nessuna credenziale GitHub. Scrive su Blob, e la scansione successiva
va a ritirare. Più lento di una scrittura diretta, ma non c'è nessun token con
permessi di scrittura in giro per il web.

Il repository resta comunque **lo specchio di ciò che sta girando**: il workflow
ricommitta `config/*.yaml` dopo averli ritirati dal Blob, così guardare il
repository per sapere cosa si sta cercando non dice una bugia.

---

## La configurazione

Si cambia **dal pannello**, nella scheda Configurazione, protetta da password.
C'è un modulo per le cose normali (soglie, prodotti, pagine da scorrere) e un
editor YAML per tutto il resto.

Modificare i file in `config/` a mano **non serve a niente**: dal primo
salvataggio in poi comanda il Blob, e la scansione successiva li sovrascrive.

| File | Cosa contiene |
|---|---|
| `config/config.yaml` | prodotti, soglie, parole chiave ed esclusioni |
| `config/subito.yaml` | scanner Subito: attivo, pagine da scorrere |
| `config/amazon.yaml` | scanner Amazon: attivo, pagine da scorrere |
| `config/northladder.yaml` | dispositivo da valutare e dati per il modulo |

---

## I tre pulsanti di riga

A destra di ogni annuncio, per chi ha la password:

| | Cosa fa |
|---|---|
| **⚠** | Lo segnala come truffa. Resta visibile, marcato, ma esce dal minimo e dalla media. |
| **⊘** | «Non mi interessa»: lo esclude dalla ricerca. Lo scanner smette di raccoglierlo. |
| **✕** | Lo toglie dal tabellone. Continua a esistere e a contare, semplicemente non lo vedi. |

La differenza fra ⊘ e ✕ è quella che conta: **✕ nasconde, ⊘ esclude.** Gli
esclusi non vengono più nemmeno raccolti, quindi non tornano in tabellone, non
contano per il minimo e non fanno scattare Telegram.

Nessuno dei tre cancella niente: sono tre elenchi di indirizzi su Blob, applicati
in lettura. Sempre reversibili, dai riquadri nella scheda Configurazione.

---

## I file

```
.github/workflows/scanner.yml   il cron e la catena della scansione

sync_config.py                  il postino: Blob → config/ e data/ignorati.json
run_once.py                     un giro di scansione, poi esce
scanner/base.py                 classificazione, storico, filtro degli esclusi
scanner/subito_scanner.py       Subito.it
scanner/amazon_scanner.py       Amazon.it
scanner/northladder_scanner.py  NorthLadder, via Chromium
notifier.py                     Telegram
reporter.py                     il riepilogo che finisce nel registro
export_vercel.py                templates/index.html → vercel/index.html

templates/index.html            il tabellone, sorgente unica
static/quadro-partenze.css      il design system
static/style.css                il livello applicativo

vercel/api/store.py             l'unica funzione: legge tutto, scrive su Blob
vercel/index.html               generato — non modificarlo a mano
vercel/README.md                come funziona il pannello, nel dettaglio

config/*.yaml                   lo specchio di ciò che sta girando
data/*.json                     i risultati, riscritti a ogni scansione
```

Per cambiare l'aspetto del tabellone si tocca `templates/index.html` o i fogli in
`static/`: `export_vercel.py` gira a ogni scansione, quindi la modifica arriva su
Vercel da sola.

---

## I segreti

Nessuno di questi sta nel repository, e nessuno dei due servizi vede quelli
dell'altro.

**Su GitHub** — Settings → Secrets and variables → Actions:

| | |
|---|---|
| `TELEGRAM_BOT_TOKEN` | il bot che manda i messaggi |
| `TELEGRAM_CHAT_ID` | a chi mandarli |

**Su Vercel** — Project Settings → Environment Variables:

| | |
|---|---|
| `BLOB_READ_WRITE_TOKEN` | l'accesso alla cassetta postale |
| `APP_PASSWORD` | la password del pannello |

Il token del Blob **può scrivere**, quindi non deve finire né nel repository né
in una pagina: vive solo fra le variabili d'ambiente, e la funzione lo usa lato
server.

---

## Perché non tutto su Vercel

Sarebbe più semplice avere un servizio solo. Non si può, e i numeri sono netti:
il piano gratuito di Vercel permette **un cron al giorno** — un `*/30` non si
deploya nemmeno, il deployment fallisce — e le funzioni hanno un tetto di
**300 secondi**. Una scansione ne vuole circa 780 e apre un browser vero.

Non è un carico serverless: serve una macchina che lavori tredici minuti, e
GitHub Actions la dà gratis con il cron al minuto. La documentazione di Vercel
stessa, come rimedio al limite del cron sul piano gratuito, suggerisce di
prendersi lo scheduler da un altro servizio.

---

## Se qualcosa non va

**Il tabellone è fermo da ore.** GitHub tiene *un solo* run in attesa per gruppo
di concorrenza: uno rimasto appeso in `queued` occupa quel posto per sempre, e da
quel momento il cron non parte più. I push continuano a funzionare, quindi il
guasto è silenzioso — sembra tutto a posto finché non guardi l'ora dell'ultima
scansione. Si controlla così:

```bash
gh api "repos/mich-de/subito/actions/runs?status=queued"
gh run cancel <id>
```

**Il tabellone si apre vuoto.** `/api/store` non ha raggiunto
`raw.githubusercontent.com`. Il registro in fondo alla pagina lo dice in chiaro.

**La configurazione non si salva.** Manca `BLOB_READ_WRITE_TOKEN` o
`APP_PASSWORD` fra le variabili d'ambiente su Vercel. Anche questo compare nel
registro.

**Le modifiche al pannello non hanno effetto.** Sono su Blob e aspettano la
scansione successiva: fino a mezz'ora. I tre pulsanti di riga invece si vedono
subito, perché vengono applicati anche in lettura.

---

Il dettaglio di come funziona il pannello — la cassetta postale, il gate della
password, l'API di Blob — sta in [`vercel/README.md`](vercel/README.md).
