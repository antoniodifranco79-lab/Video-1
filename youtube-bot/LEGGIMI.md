# Curiosità al Minuto: il canale gestito dai bot

Una squadra di 6 bot gestisce un canale YouTube Shorts di curiosità. Girano da soli su
GitHub Actions, gratis.

| Bot | File | Cosa fa | Quando |
|---|---|---|---|
| 1. Scrittore | `scrittore.py` | scrive nuovi video con Claude, scegliendo gli argomenti che funzionano meglio | lunedì |
| 2. Verificatore | `scrittore.py` | ricontrolla ogni fatto e scarta i video con anche un solo dubbio | lunedì |
| 3. Regista | `genera_video.py` | crea il video: voce, testo animato, musica | ogni giorno |
| 4. Pubblicatore | `pubblica_oggi.py` | carica il video su YouTube | ogni giorno, verso le 17:30 / 18:30 |
| 5. Analista | `analista.py` | legge visualizzazioni, like e iscritti | lunedì |
| 6. Segretario | `segretario.py` | ti manda il riepilogo settimanale (Issue su GitHub, arriva per email) | lunedì |

I dati stanno in `contenuti.json` (testi), `pubblicati.json` (video caricati) e
`statistiche.json` (numeri). L'automazione è in `.github/workflows/youtube-bot.yml`.

---

## Configurazione (una volta sola)

### Passo 1: canale YouTube
Crea il canale da youtube.com, poi Impostazioni, "Aggiungi o gestisci i tuoi canali" e "Crea un canale".
Logo, copertina e descrizione sono nella cartella `canale/`.

### Passo 2: chiave Google (console.cloud.google.com)
1. Crea un progetto e attiva **YouTube Data API v3**.
2. **Google Auth Platform**, poi **Inizia**: tipo *Esterno*, la tua email. Non caricare un logo.
3. **Pubblico**, poi **Pubblica app**. Se non si riesce, aggiungi la tua email in *Utenti di test*;
   in quel caso il permesso scade ogni 7 giorni e il Passo 4 va rifatto ogni settimana.
4. **Client**, poi **Crea client**, tipo **Applicazione web**. Come URI di reindirizzamento metti
   `https://developers.google.com/oauthplayground`. Salva **ID client** e **Client secret**.

### Passo 3: chiave Claude (console.anthropic.com)
Crea un account, aggiungi un po' di credito e crea una **API key**. Lo Scrittore costa pochi euro al mese.

### Passo 4: permesso al bot (developers.google.com/oauthplayground)
1. Ingranaggio ⚙️, spunta "Use your own OAuth credentials" e incolla ID client e Client secret.
2. Nella casella "Input your own scopes" incolla **tutte e due** le righe, separate da uno spazio:
   `https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly`
3. **Authorize APIs**, scegli il canale e clicca **Consenti**. Se compare "app non verificata",
   clicca Avanzate e poi "Vai a ...": l'app è tua.
4. **Exchange authorization code for tokens** e copia il **Refresh token**.

### Passo 5: cassaforte di GitHub
Nel repository vai su **Settings → Secrets and variables → Actions → New repository secret** e crea:

| Nome | Valore |
|---|---|
| `YT_CLIENT_ID` | ID client (Passo 2) |
| `YT_CLIENT_SECRET` | Client secret (Passo 2) |
| `YT_REFRESH_TOKEN` | Refresh token (Passo 4) |
| `ANTHROPIC_API_KEY` | API key di Claude (Passo 3) |

Non scrivere mai questi valori in chat, nel codice o nelle Issue.

### Passo 6: video pubblici
Google tiene **privati** i video caricati da app nuove finché non le approva. Richiedi l'approvazione
con il modulo "YouTube API Services - Audit and Quota Extension Form"
(support.google.com/youtube/contact/yt_api_form). Finché la richiesta è in attesa, rendi pubblici
i video da YouTube Studio: il riepilogo del lunedì ti dice quanti sono.

### Passo 7: accendi i bot
Nel repository vai su **Actions → YouTube bot → Run workflow**:
- `settimanale` per una prima prova di Analista, Scrittore e Segretario;
- `pubblica` per pubblicare subito il primo video.

Da quel momento parte tutto da solo.

---

## Uso sul computer (facoltativo)

```bash
pip install -r requirements.txt
python genera_video.py --id squali     # crea un video in uscita/ (la voce va in voices/, vedi il workflow)
python -m pytest -q test_bot.py         # test automatici
```

## Regole di YouTube
- YouTube paga solo con il Programma Partner: 1.000 iscritti e 10 milioni di visualizzazioni Shorts
  in 90 giorni (oppure 4.000 ore di visione in 12 mesi). Prima di allora non si guadagna.
- I video ripetitivi o "fatti in serie" non vengono pagati: per questo lo Scrittore cambia sempre argomento
  e il Verificatore scarta i fatti dubbi. Ogni tanto guardane qualcuno.
