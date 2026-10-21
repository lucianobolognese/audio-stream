# audio-stream
Trasmetti l'audio del tuo PC Windows via browser su qualsiasi altro dispositivo della stessa rete (telefono, tablet, altro PC). Basta uno script Python: niente app da installare sul dispositivo che ascolta.

## Funzionalità

- **Sincronizzazione Multi-Dispositivo (Multi-Room)**: connetti più dispositivi contemporaneamente alla stessa pagina per un audio diffuso.
- Cattura di tutto l'audio in uscita dal PC tramite **loopback WASAPI** (Windows).
- Pagina web integrata con interfaccia moderna (glassmorphism) e **VU-meter dinamico**, apribile da qualsiasi browser.
- **Due modalità di riproduzione**
  - *Bassa latenza*: PCM + Web Audio API, circa 150-300 ms di ritardo.
  - *Schermo bloccato*: stream MP3 live su elemento `<audio>`, continua a suonare anche con lo schermo del telefono spento (ritardo di 1-3 s).
- Spegnimento sicuro del server (Graceful shutdown) per non bloccare i driver audio del PC.
- Scelta del dispositivo audio da catturare direttamente dalla pagina.
- Accesso protetto da **PIN a 6 cifre**, con blocco temporaneo dopo troppi tentativi errati.

## Requisiti

- Windows 10/11 (il loopback WASAPI è specifico di Windows)
- Python 3.9 o superiore
- PC e dispositivo di ascolto sulla stessa rete locale

## Installazione

```bash
git clone repo-link
cd audio-stream
pip install flask PyAudioWPatch lameenc numpy waitress

```

## Utilizzo

1. Avvia lo script:
```bash
python audio_stream.py

```


2. All'avvio vengono stampati l'indirizzo, il PIN e le istruzioni:
```text
========================================
🔊 AUDIO STREAM - Server in avvio
========================================
🌐 Apri sull'altro dispositivo: [http://192.168.1.20:5000](http://192.168.1.20:5000)
🔑 PIN di accesso: 123456
----------------------------------------
⏹  Premi CTRL+C per fermare il server.
========================================

```


3. Sull'altro dispositivo apri l'indirizzo, inserisci il PIN (verrà ricordato dal browser), scegli il dispositivo audio e la modalità, poi premi **AVVIA CONNESSIONE**.
4. Per chiudere correttamente lo stream e rilasciare la scheda audio, torna sul terminale del PC e premi `CTRL+C`.

*Nota: alla prima esecuzione Windows chiederà di consentire l'accesso al firewall. Accetta **solo per le reti private**.*

## Modalità di riproduzione

| Modalità | Ritardo | Schermo bloccato | Consigliata per |
| --- | --- | --- | --- |
| Bassa latenza | ~150-300 ms | Si ferma (iOS e molti Android sospendono Web Audio) | Video, giochi |
| Schermo bloccato | ~1-3 s | Continua a suonare | Musica, podcast |

## Configurazione

| Cosa | Come |
| --- | --- |
| Cambiare il PIN | Modifica `audio_pin.txt` (creato al primo avvio) oppure imposta la variabile d'ambiente `AUDIO_TOKEN` |
| Cambiare la porta | Modifica `PORT` in cima allo script |
| Ridurre la latenza | Abbassa `CHUNK` (es. `512`) e, nel codice JS, `START_BUFFER` e `MAX_LEAD` |
| Eliminare scatti/crepitii | Alza `CHUNK` (es. `2048` o `4096`) e `START_BUFFER` |

## Sicurezza

* La porta è raggiungibile solo dalla rete locale, **a meno che tu non faccia port forwarding sul router: non farlo**.
* Il traffico è in **HTTP non cifrato**: chi è sulla tua stessa rete e intercetta i pacchetti potrebbe ascoltare l'audio. Non usare lo script su Wi-Fi pubblici o condivisi.
* Per usarlo fuori casa in modo sicuro, usa una VPN come [Tailscale](https://tailscale.com/) invece di esporre la porta su internet.
* Aggiungi `audio_pin.txt` al `.gitignore` per non pubblicare il tuo PIN.

## Risoluzione dei problemi

**Lo stato dice "In riproduzione" ma non si sente nulla**

* Controlla che il dispositivo selezionato nel menu sia quello da cui esce davvero il suono del PC (cuffie, Bluetooth, casse...), non una uscita digitale inutilizzata.
* Guarda il VU-meter: se resta fermo a zero mentre il PC suona, hai scelto il dispositivo sbagliato. Se si muove colorandosi, controlla volume, **tasto silenzioso laterale (iPhone)** e scheda muta del browser.

**Non riesco a connettermi dall'altro dispositivo**

* Verifica di essere sulla stessa rete e che il firewall di Windows consenta la porta 5000 sulle reti private.

**Audio a scatti**

* Alza `CHUNK` e `START_BUFFER`, oppure usa il Wi-Fi a 5 GHz o un cavo Ethernet sul PC.

**Nessun suono quando il PC è in silenzio**

* Normale: il loopback invia dati solo quando qualcosa sta suonando.

## Struttura del progetto

```text
audio-stream/
├── audio_stream.py   # server Flask/Waitress + pagina web
├── audio_pin.txt        # PIN (generato al primo avvio, non committare)
└── README.md

```

## Licenza

Apache License 2.0