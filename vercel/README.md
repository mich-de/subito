# Tabellone su Vercel

Questa cartella e' il sito, e il sito e' **https://subito-it.vercel.app/**.
Non c'e' un secondo indirizzo: quello e' il tabellone.

Sta su Vercel per una ragione precisa — perche' un sito di soli file statici
non puo' **salvare la configurazione dal pannello**. Qui si cambia una soglia e
si preme Salva, senza copiare YAML a mano e senza fare commit dal computer.

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
       │                 ├────────────┤   pubblico        ▼
       └───────────────► │ state/     │             run_once.py
        annunci tolti e  │  nascosti  │                   │
          segnalati      │  segnalati │                   │
                         └─────┬──────┘                   │
                               │ filtro in lettura        │
   tabellone ◄─────────────────┴─── raw.githubusercontent.com ◄── data/*.json
```

`state/` sta fuori da `config/` apposta: `sync_config.py` ritira solo i quattro
YAML, e gli elenchi non devono finire in mezzo.

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

`index.html` non contiene nessun annuncio: non c'e' niente, dentro, che possa
invecchiare. Se i dati fossero cotti nella pagina, basterebbe una ricostruzione
del sito non partita perche' Telegram dicesse una cosa e il tabellone un'altra.
Invece li chiede a `/api/store` quando lo apri, e
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

### Cosa protegge la password

Non solo la scrittura: **anche la lettura della configurazione**.

| Chi apre il tabellone | Cosa vede |
|---|---|
| Chiunque | Gli annunci, i filtri, la stampa. |
| Chi ha la password | In piu': prodotti, soglie, parole chiave, esclusioni, editor YAML, i pulsanti di riga, le segnalazioni di truffa, e le soglie sugli annunci. |

**Chiudere la scheda non bastava.** Vale la pena scriverlo perche' e' il tipo
di falla che si rifa': ogni annuncio in `data/*_results.json` si porta dietro
il `max_price` del prodotto che l'ha trovato. La configurazione era chiusa a
chiave e gli stessi numeri uscivano dalla finestra accanto, una riga per
annuncio, con `product_name` a fianco.

Da anonimo gli annunci escono ora senza `max_price` **ne' `near_miss`**: il
secondo da solo e' un booleano, ma insieme al prezzo stringe la soglia fra il
piu' caro «in soglia» e il piu' economico «oltre», e due annunci bastano per
inquadrarla a poche decine di euro.

Di conseguenza, a tabellone bloccato il badge di riserva dice **«trovato»** e
non «in soglia» — che sarebbe una dichiarazione falsa su un dato nascosto — e
il contatore dei fuori soglia mostra un trattino invece di zero: non sono zero,
sono ignoti. Appena si sblocca, la pagina richiede gli annunci completi e i
badge si correggono da soli.

**Se aggiungi un campo agli annunci, chiediti se racconta la soglia.** Il posto
dove si decide e' `SOGLIE_NEGLI_ANNUNCI` in `api/store.py`.

Prima la configurazione usciva da `/api/store` a chiunque aprisse la pagina, e
la password copriva solo il salvataggio. Ma quei dati sono soglie e parole
chiave: dicono in chiaro cosa si sta cercando e a quanto si e' disposti a
comprarlo. Ora la scheda **Configurazione** la chiede quando la si apre, e il
registro non rivela nemmeno quanti prodotti sono monitorati a chi non l'ha —
sarebbe gia' un'informazione.

Il tabellone degli annunci resta pubblico: quello e' il suo mestiere.

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

## Le tre azioni di riga: togliere, segnalare, escludere

A destra di ogni riga, per chi ha la password, ci sono tre pulsanti:

| | Cosa fa |
|---|---|
| **⚠** | Lo segnala come truffa. Resta visibile, marcato. Si preme di nuovo per ritirare la segnalazione. |
| **⊘** | «Non mi interessa»: lo esclude dalla ricerca. Sparisce, e lo scanner smette di raccoglierlo. Chiede conferma. |
| **✕** | Toglie l'annuncio dal tabellone. Chiede conferma. |

Sono **grigi finche' non ci passi sopra**, non invisibili: prima la ✕ compariva
solo al passaggio del mouse, ed e' un modo eccellente per avere una funzione che
non usa nessuno perche' nessuno sa che c'e'.

Solo due dei tre prendono un colore al passaggio — rosso la ✕, ambra il ⚠. Il ⊘
si limita a scurirsi: un terzo colore qui farebbe sembrare urgenti tutte e tre
le azioni, che e' il modo piu' rapido per non farne notare nessuna.

### ⊘ e ✕ non sono la stessa cosa

È la distinzione che vale la pena tenere a mente:

* **✕ nasconde.** L'annuncio esiste ancora, lo scanner continua a trovarlo, e
  continua a contare per il minimo e per la media. Semplicemente non lo vedi.
* **⊘ esclude.** Questi non vengono piu' nemmeno raccolti: lo scanner li scarta
  appena li rivede, quindi non tornano in tabellone, non contano per il minimo e
  non fanno scattare Telegram.

La ✕ e' per «ho gia' guardato questo». Il ⊘ e' per «questo non e' quello che
cerco, smetti di propormelo».

### Perche' non cancellano davvero

Non potrebbero: gli annunci stanno in `data/*_results.json`, che lo scanner
riscrive da capo a ogni giro, e la funzione su Vercel non ha — di proposito —
nessuna credenziale per scrivere nel repository. Un annuncio cancellato
tornerebbe alla scansione successiva.

Quindi si tengono tre elenchi di indirizzi e si applicano **in lettura**:

```
state/nascosti.json    chi sparisce dal tabellone
state/segnalati.json   chi resta ma e' marcato come truffa
state/ignorati.json    chi non va piu' nemmeno cercato
```

Tre file e non uno: una scrittura andata male rovina un elenco solo. Stanno
fuori dal prefisso `config/` cosi' `sync_config.py` non li ritira insieme agli
YAML. Il filtro sopravvive a qualunque riscrittura dei risultati, vale per tutti
e non solo per chi ha premuto il pulsante, ed e' reversibile: l'annuncio non e'
distrutto, e' escluso o qualificato. Nella scheda **Configurazione** ci sono i
riquadri con i conteggi e i pulsanti **Rimetti tutti**, **Ritira tutte** e
**Rimetti in ricerca**.

### Il terzo elenco e' l'unico che esce dal pannello

`state/ignorati.json` non si ferma alla lettura: `sync_config.py` se lo porta a
casa a ogni giro — e' l'unico file di `state/` che ritira, e lo chiede per nome —
e lo scrive in `data/ignorati.json`. Da li' `scanner/base.py` lo carica una volta
all'avvio e scarta quegli indirizzi **in cima a `classify_results`**, prima di
qualunque altro controllo: cosi' non entrano nei risultati salvati, non arrivano
a `is_new` e quindi non finiscono su Telegram, e non contano per il minimo ne'
per la media. Lo scanner NorthLadder non passa da `classify_results` — costruisce
il suo unico risultato da se' — quindi ha il filtro anche a casa sua.

Se lo store non risponde, `data/ignorati.json` resta quello del giro prima; se
manca del tutto, si scansiona tutto. Un giro con un annuncio di troppo e' un
guaio molto piu' piccolo di un giro che non parte.

Il filtro c'e' comunque anche in lettura su `/api/store`, e non e' una
ridondanza: la scansione successiva puo' essere fra mezz'ora, e un pulsante che
per mezz'ora sembra non aver fatto niente e' un pulsante che verra' premuto
cinque volte.

### Cosa cambia per un annuncio segnalato

Resta in tabella, con il badge **truffa** e la riga velata di rosso — nasconderlo
sarebbe la ✕, e serve poterlo rivedere per ricordarsi perche' era sospetto.

Ma **esce dal minimo e dalla media**. È il punto della funzione: un prezzo finto
e' finto verso il basso, quindi diventa sempre il minimo del tabellone e sposta
la media. Una volta segnalato, le statistiche tornano a descrivere gli annunci
onesti.

Su Telegram non arriva niente di nuovo: lo scanner tiene gia' il conto di cosa
ha notificato (`is_new` / `mark_sent` in `run_once.py`), quindi un annuncio gia'
visto non viene rimandato, segnalato o no.

**La segnalazione non e' pubblica.** Il campo `scam` viaggia solo verso chi ha
la password, e chi apre il tabellone da anonimo non vede ne' il badge ne' il
conteggio. Accusare di truffa un annuncio identificabile su un indirizzo aperto
a chiunque e' un'affermazione su una persona vera, fatta senza contraddittorio:
resta una nota di lavoro.

## I file

```
vercel/
├─ index.html        generato da export_vercel.py — non modificarlo a mano
├─ api/store.py      GET: annunci a tutti, configurazione solo con password.
│                    POST: scrive su Blob (config, nascosti, segnalati,
│                    ignorati), con password.
├─ vercel.json       intestazioni e salto della build sui commit di soli dati
└─ requirements.txt  ruamel.yaml, per non perdere i commenti

../sync_config.py    il postino: Blob -> config/ e data/ignorati.json,
                     all'inizio di ogni scansione
../scanner/base.py   legge data/ignorati.json e scarta gli esclusi alla fonte
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
