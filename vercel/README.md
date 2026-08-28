# Tabellone su Vercel

Questa cartella e' il sito da pubblicare su Vercel. Serve a una cosa sola che
GitHub Pages non poteva fare: **salvare la configurazione dal pannello**, senza
copiare YAML a mano e senza fare commit dal computer.

Di GitHub qui non si usa **nessuna credenziale**: niente personal access token,
niente da creare, niente da incollare. Solo servizi gratuiti di Vercel.

## Come sono divisi i compiti

| Chi | Cosa fa |
|---|---|
| **Vercel** (hosting + funzione + Blob) | Mostra il tabellone e riceve i salvataggi del pannello. |
| **GitHub Actions** | Scansiona ogni 30 minuti, manda le notifiche Telegram, committa i risultati. |

Lo scanner **non** puo' girare su Vercel: il piano gratuito lancia i cron una
volta al giorno, le funzioni hanno pochi secondi di tempo, e Amazon e
NorthLadder vogliono Playwright con Chromium — un giro completo ne prende
tredici, di minuti. Quel lavoro resta ad Actions, che lo fa gratis e senza
limiti di durata. Actions non chiede nessun token: quello con cui committa se
lo crea GitHub da solo a ogni esecuzione.

## La cassetta postale

Il pannello e lo scanner non si parlano direttamente: si lasciano i messaggi in
uno store **Vercel Blob** (`subito-config`, gratuito fino a 1 GB, qui si usano
sei kilobyte).

```
   browser                Vercel Blob               GitHub Actions
  ┌────────┐   POST      ┌────────────┐   GET      ┌──────────────┐
  │pannello│ ──────────► │ config/    │ ─────────► │sync_config.py│
  └────────┘ /api/store  │  *.yaml    │  indirizzo └──────┬───────┘
                         └────────────┘   pubblico        ▼
                                                    run_once.py
                                                          │
   tabellone ◄──── raw.githubusercontent.com ◄── data/*.json (commit)
```

1. Premi **Salva e applica**: `/api/store` riscrive gli YAML e li mette su Blob.
2. Alla scansione successiva `sync_config.py` li ritira e li mette in `config/`.
3. Il workflow li committa nel repository, cosi' guardando il repository si
   vede sempre cosa sta girando davvero.

**Il prezzo di questo disegno:** una modifica non ha effetto subito, ma **al
giro seguente — fino a mezz'ora**. Il pannello mostra il nuovo valore appena
salvato; lo scanner lo adotta al turno dopo.

**Chi comanda sulla configurazione:** il Blob. Dal primo salvataggio in poi la
versione buona e' quella del pannello, e una modifica fatta a mano nel
repository verrebbe riportata indietro alla scansione successiva. Se devi
cambiare le soglie, cambiale dal pannello.

## Perche' il tabellone non invecchia

Su Pages i dati erano cotti dentro `index.html`: se la ricostruzione del sito
non partiva, Telegram diceva una cosa e il tabellone un'altra. Qui `index.html`
non contiene nessun annuncio. Li chiede a `/api/store` quando lo apri, e
`/api/store` li legge in quel momento da `raw.githubusercontent.com` — file
pubblici via CDN, senza token.

Via CDN e non via API di GitHub apposta: l'API senza credenziali concede
sessanta richieste l'ora **per indirizzo IP**, e su Vercel l'indirizzo e'
condiviso con mezzo mondo. Sarebbe finito presto e senza spiegazioni.

## Cosa fare su Vercel, una volta sola

### 1. Lo store Blob

**Storage → Create Database → Blob**, e collegalo al progetto. Da riga di
comando e' gia' fatto:

```
vercel blob create-store subito-config --access public --environment production
```

Collegandolo, Vercel inietta da solo `BLOB_READ_WRITE_TOKEN` nel progetto.
**Non c'e' nessun token da creare ne' da copiare.**

Se rifai lo store, l'indirizzo pubblico cambia: va aggiornato `STORE_HOST` in
`sync_config.py`, oppure impostata la variabile `BLOB_STORE_HOST` nel workflow.

### 2. La password

**Settings → Environment Variables → Production**:

| Nome | Valore | Obbligatoria |
|---|---|---|
| `APP_PASSWORD` | una password scelta da te | si', per salvare |
| `GITHUB_REPO` | `mich-de/subito` | no (e' il default) |
| `GITHUB_BRANCH` | `main` | no (e' il default) |

`APP_PASSWORD` non e' un dettaglio. Il piano gratuito non ha la protezione con
password del deployment, quindi l'indirizzo e' pubblico: senza quella variabile
chiunque lo indovinasse potrebbe riscrivere la tua configurazione. La password
si digita una volta nel browser e resta li'; il confronto avviene sul server.

Senza `APP_PASSWORD` o senza store Blob il tabellone funziona lo stesso in
lettura, e il registro in fondo alla pagina dice che la scrittura e' spenta.

Le variabili d'ambiente Vercel le legge **al momento del deploy**: dopo averle
aggiunte serve un `vercel --prod` perche' esistano davvero.

## Come si usa

Apri il tabellone, scheda **Configurazione**, modifica prodotti e soglie,
**Salva e applica**. La prima volta chiede la password.

Anche l'editor YAML salva. Prima di scrivere, il file viene analizzato: se non
e' YAML valido il salvataggio si ferma li'. E `sync_config.py` lo rianalizza
prima di usarlo, perche' un file rotto fermerebbe la scansione senza spiegare
perche'.

## Cosa succede ai commenti

I `config/*.yaml` sono pieni di commenti che spiegano scelte non ovvie —
perche' esiste la keyword `256gb`, perche' l'esclusione dice `custodi` e non
`custodia`. Il salvataggio li conserva: i prodotti che non tocchi restano
identici, riga per riga, commenti compresi. Perdono i commenti solo i prodotti
che aggiungi tu dal pannello, che non ne hanno.

Salvare senza aver cambiato niente non scrive niente.

## I file

```
vercel/
├─ index.html        generato da export_vercel.py — non modificarlo a mano
├─ api/store.py      GET: legge tutto. POST: scrive su Blob, con password.
├─ vercel.json       intestazioni e salto della build sui commit di soli dati
└─ requirements.txt  ruamel.yaml, per non perdere i commenti

../sync_config.py    il postino: Blob -> config/, all'inizio di ogni scansione
```

`index.html` si rigenera con `python export_vercel.py` dalla radice del
progetto. Lo fa gia' GitHub Actions a ogni scansione, quindi cambiando
`templates/index.html` o i fogli in `static/` il tabellone si aggiorna da solo.

`ignoreCommand` in `vercel.json` salta la ricostruzione quando il commit non
tocca questa cartella. Serve: le scansioni committano dati quarantotto volte al
giorno, e ricostruire un sito che non e' cambiato consumerebbe il monte
deployment del piano gratuito per niente.

## Una fragilita' dichiarata

L'API HTTP di Vercel Blob **non e' documentata pubblicamente**: Vercel pubblica
solo l'SDK JavaScript, e per Python non ne esiste uno ufficiale. Le chiamate in
`api/store.py` seguono il contratto usato dai client in circolazione
(`x-api-version: 10`). Se un giorno Vercel lo cambia, **il salvataggio smette
di funzionare e lo dice** in chiaro nel pannello; la lettura del tabellone e lo
scanner continuano, perche' passano dagli indirizzi pubblici, che sono normali
URL su CDN.
