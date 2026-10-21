# audio-stream
Trasmetti l'audio del tuo PC Windows via browser su qualsiasi altro dispositivo della stessa rete (telefono, tablet, altro PC). Basta uno script Python: niente app da installare sul dispositivo che ascolta.

## Funzionalità

- Cattura di tutto l'audio in uscita dal PC tramite **loopback WASAPI** (Windows)
- Pagina web integrata, apribile da qualsiasi browser moderno
- **Due modalità di riproduzione**
  - *Bassa latenza*: PCM + Web Audio API, circa 150-300 ms di ritardo
  - *Schermo bloccato*: stream MP3 live su elemento `<audio>`, continua a suonare anche con lo schermo del telefono spento (ritardo di 1-3 s)
- Scelta del dispositivo audio da catturare direttamente dalla pagina
- Indicatore di livello per capire se arriva audio
- Accesso protetto da **PIN a 6 cifre**, con blocco temporaneo dopo troppi tentativi errati

## Requisiti

- Windows 10/11 (il loopback WASAPI è specifico di Windows)
- Python 3.9 o superiore
- PC e dispositivo di ascolto sulla stessa rete locale

## Installazione

```bash
git clone https://github.com/<tuo-utente>/audio-stream.git
cd audio-stream
pip install flask PyAudioWPatch lameenc numpy
```

## Utilizzo

1. Avvia lo script:
   ```bash
   python pc_audio_stream.py
   ```
2. Allo avvio vengono stampati l'indirizzo e il PIN:
   ```
   Apri sull'altro dispositivo:
   http://192.168.1.20:5000
   PIN: 123456
   ```
3. Sull'altro dispositivo apri l'indirizzo, inserisci il PIN (verrà ricordato dal browser), scegli il dispositivo audio e la modalità, poi premi **AVVIA AUDIO**.

Alla prima esecuzione Windows chiederà di consentire l'accesso al firewall: accetta **solo per le reti private**.

## Modalità di riproduzione

| Modalità | Ritardo | Schermo bloccato | Consigliata per |
|---|---|---|---|
| Bassa latenza | ~150-300 ms | Si ferma (iOS e molti Android sospendono Web Audio) | Video, giochi |
| Schermo bloccato | ~1-3 s | Continua a suonare | Musica, podcast |

## Configurazione

| Cosa | Come |
|---|---|
| Cambiare il PIN | Modifica `audio_pin.txt` (creato al primo avvio) oppure imposta la variabile d'ambiente `AUDIO_TOKEN` |
| Cambiare la porta | Modifica `PORT` in cima allo script |
| Ridurre la latenza | Abbassa `CHUNK` (es. `512`) e, nel codice JS, `START_BUFFER` e `MAX_LEAD` |
| Eliminare scatti/crepitii | Alza `CHUNK` (es. `2048`) e `START_BUFFER` |

## Sicurezza

- La porta è raggiungibile solo dalla rete locale, **a meno che tu non faccia port forwarding sul router: non farlo**.
- Il traffico è in **HTTP non cifrato**: chi è sulla tua stessa rete e intercetta i pacchetti potrebbe ascoltare l'audio. Non usare lo script su Wi-Fi pubblici o condivisi.
- Per usarlo fuori casa in modo sicuro, usa una VPN come [Tailscale](https://tailscale.com/) invece di esporre la porta su internet.
- Aggiungi `audio_pin.txt` al `.gitignore` per non pubblicare il tuo PIN.

## Risoluzione dei problemi

**Lo stato dice "In riproduzione" ma non si sente nulla**
- Controlla che il dispositivo selezionato nel menu sia quello da cui esce davvero il suono del PC (cuffie, Bluetooth, casse...), non una uscita digitale inutilizzata.
- Guarda la barra del livello: se resta ferma mentre il PC suona, hai scelto il dispositivo sbagliato. Se si muove, controlla volume, tasto silenzioso (iPhone) e scheda muta del browser.

**Non riesco a connettermi dall'altro dispositivo**
- Verifica di essere sulla stessa rete e che il firewall di Windows consenta la porta 5000 sulle reti private.

**Audio a scatti**
- Alza `CHUNK` e `START_BUFFER`, oppure usa il Wi-Fi a 5 GHz o un cavo Ethernet sul PC.

**Nessun suono quando il PC è in silenzio**
- Normale: il loopback invia dati solo quando qualcosa sta suonando.

## Struttura del progetto

```
audio-stream/
├── audio_stream.py   # server Flask + pagina web
├── audio_pin.txt        # PIN (generato al primo avvio, non committare)
└── README.md
```

## Licenza

Scegli una licenza (ad esempio [MIT](https://choosealicense.com/licenses/mit/)) e aggiungi un file `LICENSE`.