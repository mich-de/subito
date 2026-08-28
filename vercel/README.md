# Tabellone su Vercel

Questa cartella e' il sito da pubblicare su Vercel. Serve a una cosa sola che
GitHub Pages non puo' fare: **salvare la configurazione dal pannello**, senza
copiare YAML a mano e senza fare commit dal computer.

## Come sono divisi i compiti

| Chi | Cosa fa |
|---|---|
| **GitHub Actions** | Scansiona ogni 30 minuti, manda le notifiche Telegram, committa `data/*.json`. Resta dov'e'. |
| **Vercel** | Mostra il tabellone e riscrive `config/*.yaml` sul repository quando premi «Salva e applica». |

Lo scanner **non** puo' girare su Vercel: il piano gratuito lancia i cron una
volta al giorno, le funzioni hanno pochi secondi di tempo, e Amazon e
NorthLadder vogliono Playwright con Chromium. Quel lavoro resta ad Actions,
che lo fa gratis e senza limiti di durata.

## Perche' il tabellone non invecchia piu'

Su Pages i dati erano cotti dentro `index.html`: se la ricostruzione del sito
non partiva, Telegram diceva una cosa e il tabellone un'altra. Qui
`index.html` non contiene nessun annuncio. Li chiede a `/api/store` quando lo
apri, e `/api/store` li legge dal repository in quel momento. Il file non ha
niente da invecchiare.

## Cosa fare su Vercel, una volta sola

### 1. Il token GitHub

Su GitHub: **Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token**.

- **Repository access**: *Only select repositories* → `mich-de/subito`
- **Permissions → Repository permissions → Contents**: `Read and write`
- Nient'altro. Nessun permesso su altri repository, nessun accesso all'account.
- Scadenza: quella che preferisci. Quando scade il pannello smette di salvare
  e lo dice; il tabellone continua a leggere.

Copia il token: GitHub lo mostra una volta sola.

### 2. Il progetto

Su **vercel.com → Add New → Project**, importa `mich-de/subito`, e nelle
impostazioni:

- **Root Directory**: `vercel`
- **Framework Preset**: `Other`
- Build e Install command: lasciali vuoti.

### 3. Le variabili d'ambiente

**Settings → Environment Variables**, tutte e quattro su *Production*:

| Nome | Valore | Obbligatoria |
|---|---|---|
| `GITHUB_TOKEN` | il token del punto 1 | si', per salvare |
| `APP_PASSWORD` | una password scelta da te | si', per salvare |
| `GITHUB_REPO` | `mich-de/subito` | no (e' il default) |
| `GITHUB_BRANCH` | `main` | no (e' il default) |

Senza `GITHUB_TOKEN` o `APP_PASSWORD` il tabellone funziona lo stesso in
lettura, e il registro in fondo alla pagina dice che la scrittura e' spenta.

`APP_PASSWORD` non e' un dettaglio. Il piano gratuito di Vercel non ha la
protezione con password del deployment, quindi l'indirizzo e' pubblico: senza
quella variabile chiunque lo indovinasse potrebbe riscrivere la tua
configurazione. La password si digita una volta nel browser e resta li'; il
confronto avviene sul server, che e' anche l'unico posto dove sta il token.

## Come si usa

Apri il tabellone, scheda **Configurazione**, modifica prodotti e soglie,
**Salva e applica**. La prima volta chiede la password. Poi:

1. `/api/store` riscrive `config/config.yaml` (e `subito.yaml`/`amazon.yaml`
   se hai toccato quelli) in **un solo commit**.
2. Il commit su `main` fa partire il workflow.
3. La scansione successiva usa i nuovi prodotti.

Il pannello ti risponde con il numero del commit, cosi' puoi controllarlo su
GitHub.

Anche l'editor YAML salva. Prima di committare il file viene analizzato: se
non e' YAML valido il salvataggio si ferma li', perche' un file rotto
fermerebbe la scansione seguente senza spiegare perche'.

## Cosa succede ai commenti

I `config/*.yaml` sono pieni di commenti che spiegano scelte non ovvie —
perche' esiste la keyword `256gb`, perche' l'esclusione dice `custodi` e non
`custodia`. Il salvataggio li conserva: i prodotti che non tocchi restano
identici, riga per riga, commenti compresi. Perdono i commenti solo i prodotti
che aggiungi tu dal pannello, che non ne hanno.

Salvare senza aver cambiato niente non produce nessun commit.

## I file

```
vercel/
├─ index.html        generato da export_vercel.py — non modificarlo a mano
├─ api/store.py      GET: legge tutto dal repository. POST: scrive, con password.
├─ vercel.json       intestazioni e salto della build sui commit di soli dati
└─ requirements.txt  ruamel.yaml, per non perdere i commenti
```

`index.html` si rigenera con `python export_vercel.py` dalla radice del
progetto. Lo fa gia' GitHub Actions a ogni scansione, quindi cambiando
`templates/index.html` o i fogli in `static/` il tabellone su Vercel si
aggiorna da solo.

`ignoreCommand` in `vercel.json` salta la ricostruzione quando il commit non
tocca questa cartella. Serve: le scansioni committano dati quarantotto volte
al giorno, e ricostruire un sito che non e' cambiato consumerebbe il monte
deployment del piano gratuito per niente.

## Quando spegnere GitHub Pages

Quando Vercel funziona, in `.github/workflows/scanner.yml` si possono togliere
i passi che esistono solo per Pages — sono segnati da commenti nel file:
la copia di `public/index.html` in radice, «Rebuild GitHub Pages from Branch»,
`index.html` nella riga `git add -f`, e l'intero job `deploy`. Finche' non lo
fai i due tabelloni convivono senza darsi fastidio.
