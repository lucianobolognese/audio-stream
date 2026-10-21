"""
Streaming dell'audio del PC (Windows) verso il browser di un altro dispositivo.

Installazione:
    pip install flask PyAudioWPatch lameenc numpy waitress

Uso:
    python audio_stream.py
"""
import hmac
import json
import os
import secrets
import socket
import time
import threading

import numpy as np
import pyaudiowpatch as pyaudio
from flask import Flask, Response, abort, request

app = Flask(__name__)

CHUNK = 2048
PORT = 5000

# ---------------------------------------------------------------- GESTIONE RISORSE GLOBALI
pa_instance = pyaudio.PyAudio()
pa_lock = threading.Lock()      
fails_lock = threading.Lock()   

PIN_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "audio_pin.txt")

def load_pin():
    env = os.environ.get("AUDIO_TOKEN")
    if env: return env
    if os.path.exists(PIN_FILE):
        with open(PIN_FILE) as f:
            pin = f.read().strip()
            if pin: return pin
    pin = f"{secrets.randbelow(10**6):06d}"
    with open(PIN_FILE, "w") as f: f.write(pin)
    return pin

TOKEN = load_pin()
_fails = {}  

@app.before_request
def check_token():
    if request.path == "/": return
    ip = request.remote_addr
    now = time.time()
    with fails_lock:
        cnt, ts = _fails.get(ip, (0, now))
        if now - ts > 60: cnt, ts = 0, now
        if cnt >= 10: abort(429)
        t = request.args.get("t", "")
        if not hmac.compare_digest(t.encode(), TOKEN.encode()):
            _fails[ip] = (cnt + 1, ts)
            abort(403)
        _fails.pop(ip, None)

# ---------------------------------------------------------------- AUDIO UTILS
def default_loopback(p):
    wasapi = p.get_host_api_info_by_type(pyaudio.paWASAPI)
    speakers = p.get_device_info_by_index(wasapi["defaultOutputDevice"])
    if speakers.get("isLoopbackDevice"): return speakers
    for lb in p.get_loopback_device_info_generator():
        if speakers["name"] in lb["name"]: return lb
    raise RuntimeError("Nessun loopback per: " + speakers["name"])

def get_device(p, index=None):
    if index: return p.get_device_info_by_index(int(index))
    return default_loopback(p)

def open_stream(p, d):
    return p.open(format=pyaudio.paInt16, channels=int(d["maxInputChannels"]),
                  rate=int(d["defaultSampleRate"]), input=True,
                  input_device_index=d["index"], frames_per_buffer=CHUNK)

@app.route("/devices")
def devices():
    with pa_lock:
        default_idx = default_loopback(pa_instance)["index"]
        out = [{"index": d["index"], "name": d["name"],
                "rate": int(d["defaultSampleRate"]), "channels": int(d["maxInputChannels"]),
                "default": d["index"] == default_idx}
               for d in pa_instance.get_loopback_device_info_generator()]
    return Response(json.dumps(out), mimetype="application/json")

@app.route("/info")
def info():
    with pa_lock:
        d = get_device(pa_instance, request.args.get("device"))
        res = {"rate": int(d["defaultSampleRate"]), "channels": int(d["maxInputChannels"]), "name": d["name"]}
    return Response(json.dumps(res), mimetype="application/json")

# ---------------------------------------------------------------- GENERATORI STREAMING
def generate_pcm(device_index):
    stream = None
    try:
        with pa_lock: stream = open_stream(pa_instance, get_device(pa_instance, device_index))
        while True: yield stream.read(CHUNK, exception_on_overflow=False)
    except GeneratorExit: pass
    finally:
        if stream:
            with pa_lock:
                if stream.is_active(): stream.stop_stream()
                stream.close()

def generate_mp3(device_index):
    import lameenc
    stream = None
    try:
        with pa_lock:
            d = get_device(pa_instance, device_index)
            ch = int(d["maxInputChannels"])
            rate = int(d["defaultSampleRate"])
            stream = open_stream(pa_instance, d)
            
        out_ch = 1 if ch == 1 else 2
        enc = lameenc.Encoder()
        enc.set_bit_rate(192)
        enc.set_in_sample_rate(rate)
        enc.set_channels(out_ch)
        enc.set_quality(5)

        while True:
            raw = stream.read(CHUNK, exception_on_overflow=False)
            if ch > 2: raw = np.frombuffer(raw, dtype=np.int16).reshape(-1, ch)[:, :2].tobytes()
            data = bytes(enc.encode(raw))
            if data: yield data
    except GeneratorExit: pass
    finally:
        if stream:
            with pa_lock:
                if stream.is_active(): stream.stop_stream()
                stream.close()

@app.route("/stream")
def stream():
    return Response(generate_pcm(request.args.get("device")), mimetype="application/octet-stream", headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})

@app.route("/mp3")
def mp3():
    return Response(generate_mp3(request.args.get("device")), mimetype="audio/mpeg", headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"})

# ---------------------------------------------------------------- HTML PAGINA
PAGE = """<!DOCTYPE html>
<html lang="it">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>PC Audio Stream</title>
<style>
  :root { --bg: #0f172a; --card: rgba(30, 41, 59, 0.7); --text: #f8fafc; --accent: #3b82f6; --accent-hover: #2563eb; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
    background: radial-gradient(circle at top, #1e293b, #020617);
    color: var(--text); display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0;
  }
  .card {
    background: var(--card); backdrop-filter: blur(12px); -webkit-backdrop-filter: blur(12px);
    padding: 2.5rem 2rem; border-radius: 1.5rem; text-align: center;
    box-shadow: 0 25px 50px -12px rgba(0,0,0,0.5), inset 0 1px 0 rgba(255,255,255,0.1);
    width: min(90vw, 400px); border: 1px solid rgba(255,255,255,0.05);
  }
  h2 { margin-top: 0; font-weight: 600; letter-spacing: -0.5px; }
  select, input {
    width: 100%; box-sizing: border-box; padding: 0.8rem; border-radius: 0.75rem;
    background: rgba(15, 23, 42, 0.6); color: var(--text); border: 1px solid rgba(255,255,255,0.1);
    font-size: 1rem; margin-top: 0.8rem; outline: none; transition: border-color 0.2s;
  }
  select:focus, input:focus { border-color: var(--accent); }
  button {
    background: var(--accent); color: #fff; border: none; padding: 1rem; width: 100%;
    font-size: 1.05rem; font-weight: 700; border-radius: 0.75rem; cursor: pointer;
    margin-top: 1.5rem; transition: all 0.2s; box-shadow: 0 4px 15px rgba(59, 130, 246, 0.3);
  }
  button:hover:not(:disabled) { background: var(--accent-hover); transform: translateY(-1px); }
  button:disabled { background: #475569; cursor: not-allowed; box-shadow: none; opacity: 0.7; }
  
  /* VU Meter Moderno */
  .vu-meter-container {
    height: 14px; background: rgba(0,0,0,0.5); border-radius: 7px; margin-top: 1.5rem;
    overflow: hidden; position: relative; box-shadow: inset 0 2px 4px rgba(0,0,0,0.5); border: 1px solid rgba(255,255,255,0.05);
  }
  #level {
    height: 100%; width: 0;
    /* Gradiente da Verde a Giallo a Rosso */
    background: linear-gradient(90deg, #22c55e 0%, #eab308 70%, #ef4444 100%);
    transition: width 0.05s ease-out; border-radius: 7px;
  }
  
  #status-container { margin-top: 1.5rem; display: flex; align-items: center; justify-content: center; gap: 8px; }
  .dot { height: 10px; width: 10px; background: #64748b; border-radius: 50%; display: inline-block; }
  .dot.active { background: #22c55e; box-shadow: 0 0 10px #22c55e; animation: pulse 2s infinite; }
  @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
  #status { font-size: 0.95rem; color: #cbd5e1; }
  
  audio { width: 100%; margin-top: 1.5rem; display: none; filter: invert(0.9) hue-rotate(180deg); }
  .hint { font-size: 0.85rem; color: #fbbf24; margin-top: 1rem; background: rgba(251, 191, 36, 0.1); padding: 0.5rem; border-radius: 0.5rem; }
</style>
</head>
<body>
<div class="card">
  <h2>🔊 Audio Stream</h2>
  <input id="pin" type="password" inputmode="numeric" autocomplete="off" placeholder="Inserisci il PIN">
  <select id="dev"></select>
  <select id="mode">
    <option value="low">Bassa latenza (Stop a schermo spento)</option>
    <option value="bg">Schermo bloccato (Ritardo 1-3 sec)</option>
  </select>
  <button id="playBtn" onclick="startAudio()">AVVIA CONNESSIONE</button>
  <div class="hint">⚠️ Su iPhone/iPad: disattiva il tasto laterale del Silenzioso per l'audio dalle casse.</div>
  
  <div class="vu-meter-container"><div id="level"></div></div>
  <audio id="player" controls playsinline></audio>
  
  <div id="status-container">
    <div id="statusDot" class="dot"></div>
    <div id="status">In attesa del PIN...</div>
  </div>
</div>
<script>
const statusEl = document.getElementById('status');
const statusDot = document.getElementById('statusDot');
const devSel = document.getElementById('dev');
const modeSel = document.getElementById('mode');
const pinEl = document.getElementById('pin');
const levelEl = document.getElementById('level');
const player = document.getElementById('player');
const btn = document.getElementById('playBtn');

let currentPeak = 0;
let meterRunning = false;

try { pinEl.value = localStorage.getItem('pin') || ''; modeSel.value = localStorage.getItem('mode') || 'low'; } catch (e) {}

function url(path, device) {
  const p = new URLSearchParams({ t: pinEl.value.trim() });
  if (device) p.set('device', device);
  return path + '?' + p.toString();
}

function updateStatus(msg, isPlaying = false) {
  statusEl.innerText = msg;
  if(isPlaying) statusDot.classList.add('active');
  else statusDot.classList.remove('active');
}

async function loadDevices() {
  if (!pinEl.value.trim()) return;
  try {
    const r = await fetch(url('/devices'));
    if (r.status === 403) { updateStatus("PIN errato"); return; }
    if (r.status === 429) { updateStatus("Troppi tentativi, attendi 1 min"); return; }
    const list = await r.json();
    devSel.innerHTML = '';
    list.forEach(d => {
      const o = document.createElement('option');
      o.value = d.index;
      o.textContent = d.name.replace(' [Loopback]', '') + (d.default ? ' (Predefinito)' : '');
      if (d.default) o.selected = true;
      devSel.appendChild(o);
    });
    try { localStorage.setItem('pin', pinEl.value.trim()); } catch (e) {}
    updateStatus("Dispositivi caricati. Pronto.");
  } catch (e) { updateStatus("Errore di rete"); }
}
pinEl.addEventListener('change', loadDevices);
loadDevices();

function updateMeter() {
  if (!meterRunning) {
      levelEl.style.width = '0%';
      return;
  }
  // Mappatura logaritmica per rendere il VU meter più reattivo
  let visualPeak = Math.pow(currentPeak, 0.5) * 100;
  levelEl.style.width = Math.min(100, visualPeak) + '%';
  currentPeak *= 0.80; 
  requestAnimationFrame(updateMeter);
}

async function startAudio() {
  const dev = devSel.value;
  const mode = modeSel.value;
  try { localStorage.setItem('mode', mode); } catch (e) {}
  btn.disabled = true; devSel.disabled = true; modeSel.disabled = true; pinEl.disabled = true;

  if (mode === 'bg') {
    player.style.display = 'block';
    player.src = url('/mp3', dev);
    player.play().then(() => {
      updateStatus("In riproduzione (MP3)", true);
    }).catch(err => {
      updateStatus("Errore: " + err.message);
    });
    if ('mediaSession' in navigator) {
      navigator.mediaSession.metadata = new MediaMetadata({ title: 'Audio del PC', artist: 'PC Audio Stream' });
      navigator.mediaSession.setActionHandler('play', () => player.play());
      navigator.mediaSession.setActionHandler('pause', () => player.pause());
    }
    return;
  }

  const audioCtx = new (window.AudioContext || window.webkitAudioContext)({ latencyHint: 'interactive' });
  audioCtx.resume();
  const unlock = audioCtx.createBufferSource();
  unlock.buffer = audioCtx.createBuffer(1, 1, 22050);
  unlock.connect(audioCtx.destination);
  unlock.start(0);
  
  meterRunning = true;
  requestAnimationFrame(updateMeter);

  updateStatus("Connessione in corso...");
  try {
    const info = await (await fetch(url('/info', dev))).json();
    const RATE = info.rate, CH = info.channels;

    const response = await fetch(url('/stream', dev));
    const reader = response.body.getReader();
    updateStatus("Ricezione audio (PCM)", true);

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
      
      let localPeak = 0;
      for (let c = 0; c < CH; c++) {
        const ch = buffer.getChannelData(c);
        for (let i = 0; i < frames; i++) {
          const s = pcm[i * CH + c] / 32768;
          ch[i] = s;
          if (Math.abs(s) > localPeak) localPeak = Math.abs(s);
        }
      }
      if (localPeak > currentPeak) currentPeak = localPeak; 

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
    meterRunning = false;
    updateStatus("Disconnesso / Errore");
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
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except OSError: return "IP_DEL_PC"
    finally: s.close()

if __name__ == "__main__":
    print("\n  ========================================")
    print("  🔊 PC AUDIO STREAM - Server in avvio")
    print("  ========================================")
    print(f"  🌐 Apri sull'altro dispositivo: http://{local_ip()}:{PORT}")
    print(f"  🔑 PIN di accesso: {TOKEN}")
    print("  ----------------------------------------")
    print("  ⏹  Premi CTRL+C per fermare il server.")
    print("  ========================================\n")
    
    try:
        try:
            from waitress import serve
            serve(app, host="0.0.0.0", port=PORT, threads=8)
        except ImportError:
            print("  [!] Waitress non trovato. Uso il server di sviluppo Flask.")
            print("      Installa waitress con 'pip install waitress' per performance ottimali.")
            app.run(host="0.0.0.0", port=PORT, debug=False, threaded=True)
    except KeyboardInterrupt:
        print("\n\n  [!] Ricevuto comando di spegnimento (CTRL+C)...")
    finally:
        print("  [✓] Rilascio le risorse audio di Windows...")
        pa_instance.terminate()
        print("  [✓] Server fermato. Arrivederci!\n")