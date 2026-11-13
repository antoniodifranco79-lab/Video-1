# Assistente WhatsApp per saloni: il servizio vero

Un solo server gestisce tutti i saloni. Per ognuno:
- risponde ai clienti su WhatsApp (prezzi, orari, informazioni) usando Claude;
- prende, sposta e annulla appuntamenti in un'agenda online, rispettando orari, pause e postazioni;
- manda il promemoria il giorno prima alle 10:00 e la richiesta di recensione la sera della visita (piano Completo);
- gira al titolare le domande che non sa gestire ("Clienti da richiamare").

| Pagina | Per chi | Indirizzo |
|---|---|---|
| Amministrazione | tu | `/admin` (utente `admin`, password = `ADMIN_PASSWORD`) |
| Agenda e impostazioni | ogni titolare | `/s/<codice segreto>` (lo trovi in `/admin`) |
| Webhook | Meta | `/webhook` |

---

## 1. Metti online il server (una volta)

Serve un servizio che resti acceso sempre, con un indirizzo `https://`. Vanno bene Railway, Render o Fly.io
(circa 5–10 € al mese). Con Railway, per esempio:
1. Nuovo progetto, poi "Deploy from GitHub repo": scegli questo repository, cartella `assistente-attivita/server`.
   Il `Dockerfile` è già pronto.
2. Aggiungi un **Volume** montato su `/data`: lì vive il database. Senza volume, a ogni aggiornamento perdi tutto.
3. Imposta le variabili:

| Variabile | Valore |
|---|---|
| `ANTHROPIC_API_KEY` | chiave da console.anthropic.com |
| `WA_TOKEN` | token permanente di Meta (passo 2) |
| `WA_APP_SECRET` | "Chiave segreta dell'app" di Meta (passo 2) |
| `WA_VERIFY_TOKEN` | una parola lunga inventata da te |
| `ADMIN_PASSWORD` | una password lunga (almeno 10 caratteri) |
| `MODELLO` | facoltativo, vedi "Costi" |

4. Apri `https://<tuo-indirizzo>/salute`: deve rispondere `ok`.

## 2. Collega WhatsApp (Meta), una volta
1. Crea un account su **business.facebook.com**, poi su **developers.facebook.com** crea un'app di tipo
   *Business* e aggiungi il prodotto **WhatsApp**.
2. In **Configurazione → Webhook** metti:
   - URL di callback `https://<tuo-indirizzo>/webhook`;
   - token di verifica uguale a `WA_VERIFY_TOKEN`;
   - iscriviti al campo **messages**.
3. In **Impostazioni app → Di base** copia la **Chiave segreta dell'app** e mettila in `WA_APP_SECRET`.
4. In **Impostazioni business → Utenti di sistema** crea un utente amministratore e genera un token **senza scadenza**
   con i permessi `whatsapp_business_messaging` e `whatsapp_business_management`. Mettilo in `WA_TOKEN`.
5. Aggiungi un metodo di pagamento in WhatsApp Manager: Meta fa pagare i promemoria (vedi "Costi").
6. Completa la **verifica dell'azienda** su Meta: senza, i limiti di invio sono bassi.
7. In **WhatsApp Manager → Modelli di messaggio** crea due modelli in **italiano**, con questi nomi esatti:
   - `promemoria_appuntamento`, categoria **Utilità**:
     `Ciao {{1}}, ti ricordiamo l'appuntamento di {{2}} alle {{3}} da {{4}}. Se non puoi venire, rispondi a questo messaggio.`
   - `richiesta_recensione`, categoria **Marketing**:
     `Grazie {{1}} per la visita da {{2}}! Se ti è piaciuto il risultato, lasciaci una recensione qui: {{3}} Ci aiuta tantissimo.`

   Meta rifiuta i modelli che iniziano o finiscono con una variabile: copia i testi così come sono.

   Aspetta che Meta li approvi (di solito poche ore).

**Prova prima con il numero di test** che Meta ti dà gratis: crea in `/admin` un "Salone di prova" con quel
Phone number ID e scrivigli dal tuo telefono.

## 3. Aggiungi ogni salone (circa 20 minuti a salone)
1. **Il numero WhatsApp del salone.** Un numero collegato al servizio **non si può più usare nell'app WhatsApp normale**.
   Le strade sono due:
   - **un numero nuovo** solo per le prenotazioni (una SIM da pochi euro): è la più semplice e il salone non perde nulla;
   - **il numero attuale del salone**: va prima tolto dall'app WhatsApp Business. Il titolare deve essere d'accordo,
     perché da quel momento i messaggi li legge solo il bot, e quelli da gestire gli arrivano nel pannello.
2. In WhatsApp Manager aggiungi il numero, con il nome visualizzato del salone, e copia il suo **Phone number ID**.
3. In `/admin` crea il salone con quel Phone number ID e scegli il piano.
4. Apri il suo pannello, poi **Prezzi e orari**: inserisci servizi, orari, postazioni e link per le recensioni.
   Oppure manda il link al titolare e lo fa lui.
5. Fai una prova scrivendo al numero dal tuo telefono, poi consegna il link del pannello al titolare.

## Costi (stime da verificare con l'uso reale)
- **Server:** 5–10 € al mese in tutto.
- **Claude:** dipende da quanti messaggi arrivano. Con il modello predefinito (`claude-opus-5-5`) e 10 saloni con
  circa 40 messaggi al giorno ciascuno, l'ordine di grandezza è **100–200 € al mese**. Mettendo `MODELLO=claude-haiku-5-5`
  si scende a **pochi euro al mese**, con risposte un po' meno precise. La scelta è tua: guarda i costi reali su
  console.anthropic.com dopo la prima settimana.
- **Meta:** le risposte ai clienti che scrivono sono gratuite. Promemoria e richieste di recensione si pagano a messaggio
  (pochi centesimi: le recensioni, che sono "Marketing", costano di più). Per un salone con 200 appuntamenti al mese
  sono circa **10–20 € al mese**. Tienine conto nel prezzo.

## Prima di incassare
- Un contratto semplice con ogni salone e la **nomina a responsabile del trattamento dei dati** (GDPR):
  gestisci i numeri e gli appuntamenti dei loro clienti.
- La **partita IVA**: chiedi a un commercialista quale regime ti conviene.
- I clienti dei saloni devono sapere che rispondono a un assistente automatico: aggiungilo nella descrizione
  del profilo WhatsApp del salone.

## Sviluppo
```bash
pip install -r requirements.txt pytest
python -m pytest -q test_server.py                       # 29 test, senza chiamate reali
DB_PATH=prova.sqlite3 ADMIN_PASSWORD=password-lunga-1 uvicorn app:app --reload
```
