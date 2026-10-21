"""
Streaming dell'audio del PC (Windows) verso il browser di un altro dispositivo.

Installazione:
    pip install flask PyAudioWPatch lameenc numpy

Uso:
    python pc_audio_stream.py
Sull'altro dispositivo apri l'indirizzo stampato (http://IP:5000) e inserisci il PIN.
Il PIN è salvato in audio_pin.txt (modificalo pure) oppure imposta la variabile AUDIO_TOKEN.
"""
import hmac
import json
import os
import secrets
import socket
import time

import numpy as np
import pyaudiowpatch as pyaudio
from flask import Flask, Response, abort, request

app = Flask(__name__)

CHUNK = 2048   # ~21 ms a 48 kHz. Se senti scatti sali a 2048.
PORT = 5000

# ---------------------------------------------------------------- PIN
PIN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audio_pin.txt")


def load_pin():
    env = os.environ.get("AUDIO_TOKEN")
    if env:
        return env
    if os.path.exists(PIN_FILE):
        with open(PIN_FILE) as f:
            pin = f.read().strip()
            if pin:
                return pin
    pin = f"{secrets.randbelow(10**6):06d}"
    with open(PIN_FILE, "w") as f:
        f.write(pin)
    return pin


TOKEN = load_pin()
_fails = {}  # ip -> (tentativi, timestamp primo errore)


@app.before_request
def check_token():
    if request.path == "/":      # la pagina in sé non contiene nulla di sensibile
        return
    ip = request.remote_addr
    now = time.time()
    cnt, ts = _fails.get(ip, (0, now))
    if now - ts > 60:
        cnt, ts = 0, now
    if cnt >= 10:                # troppi PIN sbagliati: blocco 60 s
        abort(429)
    t = request.args.get("t", "")
    if not hmac.compare_digest(t.encode(), TOKEN.encode()):
        _fails[ip] = (cnt + 1, ts)
        abort(403)
    _fails.pop(ip, None)


# ---------------------------------------------------------------- audio
def default_loopback(p):
    wasapi = p.get_host_api_info_by_type(pyaudio.paWASAPI)
    speakers = p.get_device_info_by_index(wasapi["defaultOutputDevice"])
    if speakers.get("isLoopbackDevice"):
        return speakers
    for lb in p.get_loopback_device_info_generator():
        if speakers["name"] in lb["name"]:
            return lb
    raise RuntimeError("Nessun loopback per: " + speakers["name"])


def get_device(p, index=None):
    if index:
        return p.get_device_info_by_index(int(index))
    return default_loopback(p)


def open_stream(p, d):
    return p.open(
        format=pyaudio.paInt16,
        channels=int(d["maxInputChannels"]),
        rate=int(d["defaultSampleRate"]),
        input=True,
        input_device_index=d["index"],
        frames_per_buffer=CHUNK,
    )


@app.route("/devices")
def devices():
    p = pyaudio.PyAudio()
    try:
        default_idx = default_loopback(p)["index"]
        out = [{"index": d["index"], "name": d["name"],
                "rate": int(d["defaultSampleRate"]),
                "channels": int(d["maxInputChannels"]),
                "default": d["index"] == default_idx}
               for d in p.get_loopback_device_info_generator()]
        return Response(json.dumps(out), mimetype="application/json")
    finally:
        p.terminate()


@app.route("/info")
def info():
    p = pyaudio.PyAudio()
    try:
        d = get_device(p, request.args.get("device"))
        return Response(json.dumps({"rate": int(d["defaultSampleRate"]),
                                    "channels": int(d["maxInputChannels"]),
                                    "name": d["name"]}),
                        mimetype="application/json")
    finally:
        p.terminate()


def generate_pcm(device_index):
    """PCM grezzo: bassa latenza, per la modalità Web Audio."""
    p = pyaudio.PyAudio()
    stream = None
    try:
        stream = open_stream(p, get_device(p, device_index))
        while True:
            yield stream.read(CHUNK, exception_on_overflow=False)
    finally:
        if stream:
            stream.stop_stream()
            stream.close()
        p.terminate()


def generate_mp3(device_index):
    """MP3 live: per l'elemento <audio>, che continua anche a schermo bloccato."""
    import lameenc
    p = pyaudio.PyAudio()
    stream = None
    try:
        d = get_device(p, device_index)
        ch = int(d["maxInputChannels"])
        rate = int(d["defaultSampleRate"])
        out_ch = 1 if ch == 1 else 2

        enc = lameenc.Encoder()
        enc.set_bit_rate(192)
        enc.set_in_sample_rate(rate)
        enc.set_channels(out_ch)
        enc.set_quality(5)

        stream = open_stream(p, d)
        while True:
            raw = stream.read(CHUNK, exception_on_overflow=False)
            if ch > 2:  # downmix semplice: prime due casse
                raw = np.frombuffer(raw, dtype=np.int16).reshape(-1, ch)[:, :2].tobytes()
            data = bytes(enc.encode(raw))
            if data:
                yield data
    finally:
        if stream:
            stream.stop_stream()
            stream.close()
        p.terminate()


@app.route("/stream")
def stream():
    return Response(generate_pcm(request.args.get("device")),
                    mimetype="application/octet-stream",
                    headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


@app.route("/mp3")
def mp3():
    return Response(generate_mp3(request.args.get("device")),
                    mimetype="audio/mpeg",
                    headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})


# ---------------------------------------------------------------- pagina
PAGE = """<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PC Audio Stream</title>
<style>
  body{font-family:system-ui,sans-serif;background:#0f172a;color:#f8fafc;display:flex;
       align-items:center;justify-content:center;min-height:100vh;margin:0}
  .card{background:#1e293b;padding:2rem;border-radius:1rem;text-align:center;
        box-shadow:0 10px 25px rgba(0,0,0,.5);width:min(92vw,380px)}
  select,input{width:100%;box-sizing:border-box;padding:.6rem;border-radius:.5rem;background:#0f172a;
         color:#f8fafc;border:1px solid #334155;font-size:1rem;margin-top:.6rem}
  button{background:#3b82f6;color:#fff;border:none;padding:.8rem 1.8rem;font-size:1rem;
         font-weight:bold;border-radius:.5rem;cursor:pointer;margin-top:1rem}
  button:hover{background:#2563eb}
  #status{margin-top:1rem;font-size:.9rem;color:#94a3b8}
  .bar{height:8px;background:#0f172a;border-radius:4px;margin-top:.8rem;overflow:hidden}
  #level{height:100%;width:0;background:#22c55e;transition:width .1s}
  audio{width:100%;margin-top:1rem;display:none}
  .hint{font-size:.78rem;color:#64748b;margin-top:.4rem}
</style>
</head>
<body>
<div class="card">
  <h2>🔊 Audio Stream dal PC</h2>
  <input id="pin" type="password" inputmode="numeric" autocomplete="off" placeholder="PIN">
  <select id="dev"></select>
  <select id="mode">
    <option value="low">Bassa latenza (si ferma a schermo bloccato)</option>
    <option value="bg">Schermo bloccato OK (ritardo di 1-3 s)</option>
  </select>
  <button id="playBtn" onclick="startAudio()">AVVIA AUDIO</button>
  <div class="bar"><div id="level"></div></div>
  <audio id="player" controls></audio>
  <div id="status">Inserisci il PIN</div>
</div>
<script>
const statusEl = document.getElementById('status');
const devSel = document.getElementById('dev');
const modeSel = document.getElementById('mode');
const pinEl = document.getElementById('pin');
const levelEl = document.getElementById('level');
const player = document.getElementById('player');

try { pinEl.value = localStorage.getItem('pin') || ''; modeSel.value = localStorage.getItem('mode') || 'low'; } catch (e) {}

function url(path, device) {
  const p = new URLSearchParams({ t: pinEl.value.trim() });
  if (device) p.set('device', device);
  return path + '?' + p.toString();
}

async function loadDevices() {
  if (!pinEl.value.trim()) return;
  try {
    const r = await fetch(url('/devices'));
    if (r.status === 403) { statusEl.innerText = "PIN errato"; return; }
    if (r.status === 429) { statusEl.innerText = "Troppi tentativi, riprova tra 1 minuto"; return; }
    const list = await r.json();
    devSel.innerHTML = '';
    list.forEach(d => {
      const o = document.createElement('option');
      o.value = d.index;
      o.textContent = d.name.replace(' [Loopback]', '') + (d.default ? ' (predefinito)' : '');
      if (d.default) o.selected = true;
      devSel.appendChild(o);
    });
    try { localStorage.setItem('pin', pinEl.value.trim()); } catch (e) {}
    statusEl.innerText = "Pronto";
  } catch (e) { statusEl.innerText = "Errore: " + e.message; }
}
pinEl.addEventListener('change', loadDevices);
loadDevices();

async function startAudio() {
  const btn = document.getElementById('playBtn');
  const dev = devSel.value;
  const mode = modeSel.value;
  try { localStorage.setItem('mode', mode); } catch (e) {}
  btn.disabled = true; devSel.disabled = true; modeSel.disabled = true; pinEl.disabled = true;

  // ---------- Modalità schermo bloccato: <audio> con stream MP3 ----------
  if (mode === 'bg') {
    player.style.display = 'block';
    player.src = url('/mp3', dev);
    player.play().then(() => {
      statusEl.innerText = "In riproduzione (modalità schermo bloccato)";
    }).catch(err => {
      statusEl.innerText = "Errore: " + err.message;
    });
    if ('mediaSession' in navigator) {
      navigator.mediaSession.metadata = new MediaMetadata({ title: 'Audio del PC', artist: 'PC Audio Stream' });
      navigator.mediaSession.setActionHandler('play', () => player.play());
      navigator.mediaSession.setActionHandler('pause', () => player.pause());
    }
    return;
  }

  // ---------- Modalità bassa latenza: Web Audio con PCM ----------
  // AudioContext creato e sbloccato subito, dentro il click (prima di qualsiasi await)
  const audioCtx = new (window.AudioContext || window.webkitAudioContext)({ latencyHint: 'interactive' });
  audioCtx.resume();
  const unlock = audioCtx.createBufferSource();
  unlock.buffer = audioCtx.createBuffer(1, 1, 22050);
  unlock.connect(audioCtx.destination);
  unlock.start(0);

  statusEl.innerText = "Connessione...";
  try {
    const info = await (await fetch(url('/info', dev))).json();
    const RATE = info.rate, CH = info.channels;

    const response = await fetch(url('/stream', dev));
    const reader = response.body.getReader();
    statusEl.innerText = "Ricevo audio da: " + info.name.replace(' [Loopback]', '');

    const frameBytes = CH * 2;
    let leftover = new Uint8Array(0);
    let nextStart = 0;
    const START_BUFFER = 0.08;
    const MAX_LEAD = 0.30;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = new Uint8Array(leftover.length + value.length);
      chunk.set(leftover);
      chunk.set(value, leftover.length);

      const frames = Math.floor(chunk.length / frameBytes);
      const used = frames * frameBytes;
      leftover = chunk.slice(used);
      if (frames === 0) continue;

      const pcm = new Int16Array(chunk.buffer, 0, frames * CH);
      const buffer = audioCtx.createBuffer(CH, frames, RATE);
      let peak = 0;
      for (let c = 0; c < CH; c++) {
        const ch = buffer.getChannelData(c);
        for (let i = 0; i < frames; i++) {
          const s = pcm[i * CH + c] / 32768;
          ch[i] = s;
          if (Math.abs(s) > peak) peak = Math.abs(s);
        }
      }
      levelEl.style.width = Math.min(100, peak * 140) + '%';

      if (audioCtx.state !== 'running') audioCtx.resume();
      const now = audioCtx.currentTime;
      if (nextStart < now) nextStart = now + START_BUFFER;
      if (nextStart - now > MAX_LEAD) continue;

      const src = audioCtx.createBufferSource();
      src.buffer = buffer;
      src.connect(audioCtx.destination);
      src.start(nextStart);
      nextStart += buffer.duration;
    }
  } catch (err) {
    statusEl.innerText = "Errore: " + err.message;
    btn.disabled = false; devSel.disabled = false; modeSel.disabled = false; pinEl.disabled = false;
  }
}
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return Response(PAGE, mimetype="text/html")


def local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))  # nessun pacchetto inviato, serve solo a scoprire l'IP locale
        return s.getsockname()[0]
    except OSError:
        return "IP_DEL_PC"
    finally:
        s.close()


if __name__ == "__main__":
    print("\n  Apri sull'altro dispositivo:")
    print(f"  http://{local_ip()}:{PORT}")
    print(f"  PIN: {TOKEN}\n")
    app.run(host="0.0.0.0", port=PORT, debug=False, threaded=True)