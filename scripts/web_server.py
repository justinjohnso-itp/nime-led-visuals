"""Lightweight zero-dependency HTTP + SSE web server for live LED & audio control."""

from __future__ import annotations

import json
import socket
import threading
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from config import (
    DEFAULT_LIVE_PARAMS,
    NUM_LEDS_PER_STRIP,
    NUM_SPECTRUM_BANDS,
    NUM_STRIPS,
    PRESETS,
    SPECTRUM_FREQS,
    WEB_PORT,
    get_active_preset,
    get_live_params,
    reset_live_params,
    update_live_params,
)
from effects import LEDEffects


HTML_PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>NIME // LIVE LIGHT ENGINE</title>
<style>
  :root {
    --bg: #08090c;
    --panel: #11131a;
    --panel-hi: #181b24;
    --border: #252a38;
    --text: #eef0f6;
    --muted: #828a9f;
    --accent: #ff3b30;
    --accent-cool: #00b4ff;
    --ok: #30d158;
    --font-mono: "JetBrains Mono", "SF Mono", "Menlo", "Consolas", monospace;
    --font-sans: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; -webkit-tap-highlight-color: transparent; }
  body {
    background: radial-gradient(circle at 50% 0%, #191322 0%, var(--bg) 55%);
    color: var(--text);
    font-family: var(--font-sans);
    min-height: 100vh;
    padding: 12px;
    max-width: 980px;
    margin: 0 auto;
  }
  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 10px 14px;
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 10px;
    margin-bottom: 12px;
  }
  .brand {
    display: flex;
    align-items: center;
    gap: 10px;
  }
  .status-dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: var(--ok);
    box-shadow: 0 0 10px var(--ok);
    transition: background 0.2s;
  }
  .status-dot.offline {
    background: #ff453a;
    box-shadow: 0 0 10px #ff453a;
  }
  h1 {
    font-family: var(--font-mono);
    font-size: 0.95rem;
    letter-spacing: 0.08em;
    text-transform: uppercase;
  }
  .telemetry {
    display: flex;
    gap: 14px;
    font-family: var(--font-mono);
    font-size: 0.8rem;
    color: var(--muted);
  }
  .telemetry b {
    color: var(--text);
    font-weight: 600;
  }
  .viz-card {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 12px;
    margin-bottom: 12px;
    position: sticky;
    top: 8px;
    z-index: 20;
    backdrop-filter: blur(12px);
    box-shadow: 0 10px 30px rgba(0, 0, 0, 0.55);
  }
  .viz-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-family: var(--font-mono);
    font-size: 0.72rem;
    color: var(--muted);
    margin-bottom: 8px;
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }
  canvas {
    width: 100%;
    display: block;
    border-radius: 8px;
    background: #050608;
  }
  #stageCanvas {
    height: 132px;
    margin-bottom: 8px;
    border: 1px solid #1c202c;
  }
  #spectrumCanvas {
    height: 88px;
    border: 1px solid #1c202c;
  }
  .presets-bar {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
    gap: 8px;
    margin-bottom: 12px;
  }
  .preset-btn {
    background: var(--panel);
    border: 1px solid var(--border);
    color: var(--text);
    padding: 10px 12px;
    border-radius: 9px;
    cursor: pointer;
    text-align: left;
    transition: all 0.15s ease;
    position: relative;
  }
  .preset-btn:hover, .preset-btn:active {
    background: var(--panel-hi);
    border-color: var(--accent);
  }
  .preset-btn.active {
    background: rgba(48, 209, 88, 0.11);
    border-color: var(--ok);
    box-shadow: 0 0 16px rgba(48, 209, 88, 0.18);
  }
  .preset-btn .p-head {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 6px;
    margin-bottom: 3px;
  }
  .preset-btn .p-title {
    font-family: var(--font-mono);
    font-size: 0.78rem;
    font-weight: 700;
    color: #fff;
  }
  .preset-btn .p-badge {
    font-family: var(--font-mono);
    font-size: 0.62rem;
    font-weight: 700;
    padding: 2px 6px;
    border-radius: 4px;
    background: var(--ok);
    color: #050806;
    display: none;
    letter-spacing: 0.04em;
  }
  .preset-btn.active .p-badge {
    display: inline-block;
  }
  .preset-btn .p-desc {
    font-size: 0.68rem;
    color: var(--muted);
    line-height: 1.25;
  }
  .controls-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(290px, 1fr));
    gap: 12px;
  }
  .group-card {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 12px;
    padding: 14px;
  }
  .group-title {
    font-family: var(--font-mono);
    font-size: 0.78rem;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--muted);
    margin-bottom: 12px;
    display: flex;
    justify-content: space-between;
    align-items: center;
    border-bottom: 1px solid var(--border);
    padding-bottom: 8px;
  }
  .control-row {
    margin-bottom: 14px;
  }
  .control-row:last-child {
    margin-bottom: 0;
  }
  .control-label {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    margin-bottom: 5px;
    font-size: 0.85rem;
  }
  .control-name {
    font-weight: 600;
  }
  .control-val {
    font-family: var(--font-mono);
    font-size: 0.8rem;
    color: var(--accent-cool);
  }
  .control-hint {
    font-size: 0.7rem;
    color: var(--muted);
    margin-top: 3px;
  }
  input[type=range] {
    -webkit-appearance: none;
    appearance: none;
    width: 100%;
    height: 26px;
    background: transparent;
    cursor: pointer;
  }
  input[type=range]::-webkit-slider-runnable-track {
    height: 6px;
    border-radius: 4px;
    background: #232836;
  }
  input[type=range]::-webkit-slider-thumb {
    -webkit-appearance: none;
    appearance: none;
    width: 22px;
    height: 22px;
    border-radius: 50%;
    background: #fff;
    border: 2px solid var(--accent);
    margin-top: -8px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.5);
  }
  .footer-actions {
    margin-top: 14px;
    display: flex;
    justify-content: flex-end;
    gap: 10px;
  }
  .btn-reset {
    background: #1c1f2b;
    color: var(--text);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 9px 14px;
    font-family: var(--font-mono);
    font-size: 0.78rem;
    cursor: pointer;
  }
  .btn-reset:hover {
    border-color: #ff453a;
    color: #ff453a;
  }
</style>
</head>
<body>
  <header>
    <div class="brand">
      <div id="statusDot" class="status-dot"></div>
      <h1>NIME // LIVE LIGHT ENGINE</h1>
    </div>
    <div class="telemetry">
      <span>PRESET <b id="activePresetLabel" style="color: var(--ok);">--</b></span>
      <span>ROOT <b id="domFreq">-- Hz</b></span>
      <span>TONAL <b id="tonalVal">0.00</b></span>
      <span>RMS <b id="rmsVal">0.00</b></span>
    </div>
  </header>

  <section class="viz-card">
    <div class="viz-header">
      <span>Physical 3-Strip Stage Layout (432 LEDs)</span>
      <span id="litStats">0 / 432 LEDs Active</span>
    </div>
    <canvas id="stageCanvas" width="900" height="150"></canvas>
    <div class="viz-header" style="margin-top: 6px;">
      <span>32-Band Logarithmic Audio Spectrum (20 Hz — 7040 Hz) &bull; Root Zone Highlighted</span>
      <span id="gateIndicator">GATE OPEN</span>
    </div>
    <canvas id="spectrumCanvas" width="900" height="100"></canvas>
  </section>

  <section class="presets-bar" id="presetsBar"></section>

  <section class="controls-grid">
    <div class="group-card">
      <div class="group-title">
        <span>Root Focus &amp; Strip Real Estate</span>
        <span>LIVE MIX</span>
      </div>
      <div class="control-row">
        <div class="control-label">
          <span class="control-name">Bass Frequency Floor</span>
          <span class="control-val" id="val_bass_floor_hz">55 Hz</span>
        </div>
        <input type="range" id="ctrl_bass_floor_hz" min="20.0" max="150.0" step="2.0" data-key="bass_floor_hz">
        <div class="control-hint">Lowest frequency mapped to the exact middle of the center strip (raise if center is dark)</div>
      </div>
      <div class="control-row">
        <div class="control-label">
          <span class="control-name">Center Strip Boost &amp; Fill</span>
          <span class="control-val" id="val_center_strip_boost">1.65x</span>
        </div>
        <input type="range" id="ctrl_center_strip_boost" min="0.5" max="3.0" step="0.05" data-key="center_strip_boost">
        <div class="control-hint">Extra brightness &amp; downward bass bloom into the physical center strip</div>
      </div>
      <div class="control-row">
        <div class="control-label">
          <span class="control-name">Audible Root Weighting</span>
          <span class="control-val" id="val_root_focus">0.85</span>
        </div>
        <input type="range" id="ctrl_root_focus" min="0.0" max="1.5" step="0.05" data-key="root_focus">
        <div class="control-hint">Emphasizes musical root notes (45–900 Hz) &amp; suppresses background spectral wash</div>
      </div>
      <div class="control-row">
        <div class="control-label">
          <span class="control-name">Root Strip Real Estate</span>
          <span class="control-val" id="val_root_real_estate">1.65</span>
        </div>
        <input type="range" id="ctrl_root_real_estate" min="1.0" max="2.8" step="0.05" data-key="root_real_estate">
        <div class="control-hint">Expands physical LED strip space dedicated to low/mid root frequencies</div>
      </div>
      <div class="control-row">
        <div class="control-label">
          <span class="control-name">Harmonic Suppression</span>
          <span class="control-val" id="val_harmonic_suppression">0.85</span>
        </div>
        <input type="range" id="ctrl_harmonic_suppression" min="0.0" max="1.0" step="0.05" data-key="harmonic_suppression">
        <div class="control-hint">1.0 = isolate single fundamental note; lower = allow upper chord/cymbal harmonics</div>
      </div>
      <div class="control-row">
        <div class="control-label">
          <span class="control-name">Cluster Spread Width</span>
          <span class="control-val" id="val_cluster_width">1.10</span>
        </div>
        <input type="range" id="ctrl_cluster_width" min="0.0" max="2.5" step="0.05" data-key="cluster_width">
        <div class="control-hint">Size of each illuminated note blob across neighboring LEDs</div>
      </div>
    </div>

    <div class="group-card">
      <div class="group-title">
        <span>Output &amp; Easing Curve</span>
        <span>INTENSITY</span>
      </div>
      <div class="control-row">
        <div class="control-label">
          <span class="control-name">Master Brightness</span>
          <span class="control-val" id="val_brightness">0.85</span>
        </div>
        <input type="range" id="ctrl_brightness" min="0.0" max="1.0" step="0.02" data-key="brightness">
        <div class="control-hint">Overall LED strip output ceiling</div>
      </div>
      <div class="control-row">
        <div class="control-label">
          <span class="control-name">Response Intensity</span>
          <span class="control-val" id="val_response_intensity">1.15</span>
        </div>
        <input type="range" id="ctrl_response_intensity" min="0.2" max="3.0" step="0.05" data-key="response_intensity">
        <div class="control-hint">Pre-curve visual drive multiplier</div>
      </div>
      <div class="control-row">
        <div class="control-label">
          <span class="control-name">Easing Curve (Gamma)</span>
          <span class="control-val" id="val_easing_exponent">1.25</span>
        </div>
        <input type="range" id="ctrl_easing_exponent" min="0.25" max="3.5" step="0.05" data-key="easing_exponent">
        <div class="control-hint">&lt;1.0 = soft wide glow, 1.0 = linear, &gt;1.0 = punchy high-contrast peaks</div>
      </div>
      <div class="control-row">
        <div class="control-label">
          <span class="control-name">Sub-Bass Boost</span>
          <span class="control-val" id="val_bass_boost">2.20</span>
        </div>
        <input type="range" id="ctrl_bass_boost" min="0.5" max="5.0" step="0.1" data-key="bass_boost">
        <div class="control-hint">Extra lift for deep kick &amp; sub-bass fundamentals (20–80 Hz)</div>
      </div>
      <div class="control-row">
        <div class="control-label">
          <span class="control-name">Idle Floor-Guard Brightness</span>
          <span class="control-val" id="val_idle_brightness">0.35</span>
        </div>
        <input type="range" id="ctrl_idle_brightness" min="0.0" max="1.0" step="0.02" data-key="idle_brightness">
        <div class="control-hint">Safety perimeter &amp; wave/comet motion when no band is playing so nobody steps on the strips</div>
      </div>
      <div class="control-row">
        <div class="control-label">
          <span class="control-name">Auto Floor-Guard Delay</span>
          <span class="control-val" id="val_idle_timeout">4.0s</span>
        </div>
        <input type="range" id="ctrl_idle_timeout" min="0.5" max="30.0" step="0.5" data-key="idle_timeout">
        <div class="control-hint">Seconds of silence before Floor Guard automatically fades in</div>
      </div>
    </div>

    <div class="group-card">
      <div class="group-title">
        <span>Audio Input &amp; Anti-Spike</span>
        <span>ENVELOPE</span>
      </div>
      <div class="control-row">
        <div class="control-label">
          <span class="control-name">Spike / Flash Suppression</span>
          <span class="control-val" id="val_spike_suppression">0.80</span>
        </div>
        <input type="range" id="ctrl_spike_suppression" min="0.0" max="1.0" step="0.05" data-key="spike_suppression">
        <div class="control-hint">Rejects isolated 1-frame noise pops &amp; softens near-gate flashes during chill audio</div>
      </div>
      <div class="control-row">
        <div class="control-label">
          <span class="control-name">Input Gain</span>
          <span class="control-val" id="val_input_gain">15.0</span>
        </div>
        <input type="range" id="ctrl_input_gain" min="0.5" max="60.0" step="0.5" data-key="input_gain">
        <div class="control-hint">USB audio input level multiplier from mixer</div>
      </div>
      <div class="control-row">
        <div class="control-label">
          <span class="control-name">Noise Gate Threshold</span>
          <span class="control-val" id="val_noise_gate">0.025</span>
        </div>
        <input type="range" id="ctrl_noise_gate" min="0.0" max="0.15" step="0.002" data-key="noise_gate">
        <div class="control-hint">Mutes audio reactivity below this RMS level (transitions to Floor Guard)</div>
      </div>
      <div class="control-row">
        <div class="control-label">
          <span class="control-name">Attack Speed</span>
          <span class="control-val" id="val_attack_speed">0.65</span>
        </div>
        <input type="range" id="ctrl_attack_speed" min="0.05" max="1.0" step="0.05" data-key="attack_speed">
        <div class="control-hint">How fast LEDs snap to new notes and drum hits</div>
      </div>
      <div class="control-row">
        <div class="control-label">
          <span class="control-name">Decay Speed</span>
          <span class="control-val" id="val_decay_speed">0.22</span>
        </div>
        <input type="range" id="ctrl_decay_speed" min="0.02" max="0.90" step="0.02" data-key="decay_speed">
        <div class="control-hint">How quickly notes fade out (lower = longer trails)</div>
      </div>
      <div class="control-row">
        <div class="control-label">
          <span class="control-name">Peak Auto-Gain Hold</span>
          <span class="control-val" id="val_peak_hold_decay">0.82</span>
        </div>
        <input type="range" id="ctrl_peak_hold_decay" min="0.50" max="0.99" step="0.01" data-key="peak_hold_decay">
        <div class="control-hint">Running peak memory (lower = adapts faster to quiet passages)</div>
      </div>
    </div>

    <div class="group-card">
      <div class="group-title">
        <span>Color Palette</span>
        <span>HUE</span>
      </div>
      <div class="control-row">
        <div class="control-label">
          <span class="control-name">Center Root Hue (Bass)</span>
          <span class="control-val" id="val_bass_hue">0&deg;</span>
        </div>
        <input type="range" id="ctrl_bass_hue" min="0" max="360" step="2" data-key="bass_hue">
        <div class="control-hint">0&deg; = Red, 30&deg; = Orange, 120&deg; = Green, 240&deg; = Blue, 300&deg; = Magenta</div>
      </div>
      <div class="control-row">
        <div class="control-label">
          <span class="control-name">Outer Edge Hue (Treble)</span>
          <span class="control-val" id="val_treble_hue">240&deg;</span>
        </div>
        <input type="range" id="ctrl_treble_hue" min="0" max="360" step="2" data-key="treble_hue">
        <div class="control-hint">Outer wing color for high frequencies</div>
      </div>
      <div class="control-row">
        <div class="control-label">
          <span class="control-name">Perceptual Luminance Balance</span>
          <span class="control-val" id="val_perceptual_correction">1.00</span>
        </div>
        <input type="range" id="ctrl_perceptual_correction" min="0.0" max="1.0" step="0.05" data-key="perceptual_correction">
        <div class="control-hint">1.0 = ITU BT.709 eye-balanced brightness (boosts reds vs blues)</div>
      </div>
    </div>
  </section>

  <div class="footer-actions">
    <button class="btn-reset" id="resetBtn">Reset to Live Music Defaults</button>
  </div>

<script>
  const stageCanvas = document.getElementById('stageCanvas');
  const stageCtx = stageCanvas.getContext('2d');
  const specCanvas = document.getElementById('spectrumCanvas');
  const specCtx = specCanvas.getContext('2d');

  let bandFreqs = [];
  let presetsCatalog = {};
  let activePresetId = null;
  let currentParams = {};
  let isDragging = false;
  let updateTimer = null;

  function formatVal(key, val) {
    if (key === 'bass_hue' || key === 'treble_hue') return Math.round(val) + '°';
    if (key === 'bass_floor_hz') return Math.round(val) + ' Hz';
    if (key === 'center_strip_boost') return Number(val).toFixed(2) + 'x';
    if (key === 'idle_timeout') return Number(val).toFixed(1) + 's';
    if (key === 'noise_gate') return Number(val).toFixed(3);
    if (key === 'input_gain') return Number(val).toFixed(1) + 'x';
    return Number(val).toFixed(2);
  }

  function syncActivePreset(presetId, presetLabel) {
    activePresetId = presetId || null;
    const badge = document.getElementById('activePresetLabel');
    if (badge) {
      badge.textContent = presetLabel || (presetId && presetsCatalog[presetId] ? presetsCatalog[presetId].label : 'Custom');
      badge.style.color = activePresetId ? 'var(--ok)' : 'var(--accent-cool)';
    }
    document.querySelectorAll('.preset-btn[data-preset-id]').forEach(btn => {
      const id = btn.getAttribute('data-preset-id');
      btn.classList.toggle('active', id === activePresetId);
    });
  }

  function syncSliders(params, presetId, presetLabel) {
    currentParams = Object.assign({}, params);
    document.querySelectorAll('input[type=range][data-key]').forEach(el => {
      const k = el.getAttribute('data-key');
      if (k in params && !isDragging) {
        el.value = params[k];
        const valEl = document.getElementById('val_' + k);
        if (valEl) valEl.textContent = formatVal(k, params[k]);
      }
    });
    if (presetId !== undefined || presetLabel !== undefined) {
      syncActivePreset(presetId, presetLabel);
    }
  }

  function sendParamUpdate(patch) {
    fetch('/api/params', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(patch)
    }).then(r => r.json()).then(data => {
      if (data.params) syncSliders(data.params, data.active_preset, data.active_preset_label);
    }).catch(() => {});
  }

  document.querySelectorAll('input[type=range][data-key]').forEach(el => {
    const key = el.getAttribute('data-key');
    el.addEventListener('pointerdown', () => { isDragging = true; });
    el.addEventListener('pointerup', () => { isDragging = false; });
    el.addEventListener('input', () => {
      const v = parseFloat(el.value);
      const valEl = document.getElementById('val_' + key);
      if (valEl) valEl.textContent = formatVal(key, v);
      if (updateTimer) clearTimeout(updateTimer);
      updateTimer = setTimeout(() => sendParamUpdate({ [key]: v }), 25);
    });
  });

  document.getElementById('resetBtn').addEventListener('click', () => {
    fetch('/api/reset', { method: 'POST' })
      .then(r => r.json())
      .then(data => { if (data.params) syncSliders(data.params, data.active_preset, data.active_preset_label); });
  });

  function renderPresets(presets) {
    presetsCatalog = presets || {};
    const bar = document.getElementById('presetsBar');
    bar.innerHTML = '';
    Object.entries(presets).forEach(([id, preset]) => {
      const btn = document.createElement('button');
      btn.className = 'preset-btn';
      btn.setAttribute('data-preset-id', id);
      btn.innerHTML = `<div class="p-head"><div class="p-title">${preset.label}</div><span class="p-badge">ACTIVE</span></div><div class="p-desc">${preset.description}</div>`;
      btn.addEventListener('click', () => {
        isDragging = false;
        // If clicking Force Floor Guard while it is already active, toggle back to Live Music Roots
        if (id === 'floor_safety_standby' && activePresetId === 'floor_safety_standby' && presets.live_roots) {
          sendParamUpdate(presets.live_roots.params);
          syncSliders(presets.live_roots.params, 'live_roots', presets.live_roots.label);
        } else {
          sendParamUpdate(preset.params);
          syncSliders(preset.params, id, preset.label);
        }
      });
      bar.appendChild(btn);
    });
    syncActivePreset(activePresetId);
  }

  function drawStageLEDs(leds) {
    const w = stageCanvas.width;
    const h = stageCanvas.height;
    stageCtx.clearRect(0, 0, w, h);

    if (!leds || leds.length === 0) return;

    // Draw the 3 physical strips in the angled U/trapezoid stage layout from the floor setup:
    // Left Wing (0..47): bottom-left (40, 128) -> top-left-center (285, 34)
    // Center Bar (48..95): (305, 30) -> (595, 30)
    // Right Wing (96..143): (615, 34) -> (860, 128)
    const segments = [
      { start: 0, count: 48, x0: 45, y0: 126, x1: 285, y1: 34, label: 'LEFT STRIP' },
      { start: 48, count: 48, x0: 308, y0: 30, x1: 592, y1: 30, label: 'CENTER STRIP (ROOT BASS)' },
      { start: 96, count: 48, x0: 615, y0: 34, x1: 855, y1: 126, label: 'RIGHT STRIP' }
    ];

    let litCount = 0;

    segments.forEach(seg => {
      // Draw wood/diffuser backing bar
      stageCtx.strokeStyle = '#1d202a';
      stageCtx.lineWidth = 14;
      stageCtx.lineCap = 'round';
      stageCtx.beginPath();
      stageCtx.moveTo(seg.x0, seg.y0);
      stageCtx.lineTo(seg.x1, seg.y1);
      stageCtx.stroke();

      for (let i = 0; i < seg.count; i++) {
        const idx = seg.start + i;
        const rgb = leds[idx] || [0, 0, 0];
        const r = rgb[0], g = rgb[1], b = rgb[2];
        if (r > 2 || g > 2 || b > 2) litCount += 3;

        const t = i / (seg.count - 1);
        const x = seg.x0 + (seg.x1 - seg.x0) * t;
        const y = seg.y0 + (seg.y1 - seg.y0) * t;

        if (r > 0 || g > 0 || b > 0) {
          stageCtx.fillStyle = `rgba(${r}, ${g}, ${b}, 0.28)`;
          stageCtx.beginPath();
          stageCtx.arc(x, y, 11, 0, Math.PI * 2);
          stageCtx.fill();
        }

        stageCtx.fillStyle = (r === 0 && g === 0 && b === 0) ? '#141720' : `rgb(${r}, ${g}, ${b})`;
        stageCtx.beginPath();
        stageCtx.arc(x, y, 4.2, 0, Math.PI * 2);
        stageCtx.fill();
      }
    });

    document.getElementById('litStats').textContent = `${Math.min(432, litCount)} / 432 LEDs Active`;
  }

  function drawSpectrum(spectrum, domBand) {
    const w = specCanvas.width;
    const h = specCanvas.height;
    specCtx.clearRect(0, 0, w, h);

    if (!spectrum || spectrum.length === 0) return;

    // Highlight audible root zone (bands 0..20, ~20-950 Hz)
    const rootZoneWidth = (21 / 32) * w;
    specCtx.fillStyle = 'rgba(255, 59, 48, 0.07)';
    specCtx.fillRect(0, 0, rootZoneWidth, h);

    const n = spectrum.length;
    const pad = 6;
    const barW = (w - pad * 2) / n;

    for (let i = 0; i < n; i++) {
      const val = Math.max(0, Math.min(1, spectrum[i]));
      const bh = val * (h - 22);
      const x = pad + i * barW;
      const y = h - 16 - bh;

      const isRoot = i < 20;
      const isDom = i === domBand;
      if (isDom) {
        specCtx.fillStyle = '#ffffff';
      } else if (isRoot) {
        specCtx.fillStyle = `hsl(${Math.round((i / 20) * 28)}, 95%, 55%)`;
      } else {
        specCtx.fillStyle = `hsl(${Math.round(185 + ((i - 20) / 12) * 55)}, 90%, 55%)`;
      }

      specCtx.fillRect(x + 2, y, Math.max(4, barW - 4), Math.max(2, bh));

      if (i % 4 === 0 && bandFreqs[i]) {
        specCtx.fillStyle = '#687086';
        specCtx.font = '10px monospace';
        const f = bandFreqs[i];
        const lbl = f >= 1000 ? (f / 1000).toFixed(1) + 'k' : Math.round(f) + '';
        specCtx.fillText(lbl, x + 2, h - 4);
      }
    }
  }

  fetch('/api/init').then(r => r.json()).then(data => {
    if (data.band_freqs) bandFreqs = data.band_freqs;
    if (data.presets) renderPresets(data.presets);
    if (data.params) syncSliders(data.params, data.active_preset, data.active_preset_label);
  });

  function connectSSE() {
    const dot = document.getElementById('statusDot');
    const es = new EventSource('/api/stream');
    es.onopen = () => { dot.classList.remove('offline'); };
    es.onmessage = (ev) => {
      try {
        const d = JSON.parse(ev.data);
        document.getElementById('domFreq').textContent = d.dominant_freq > 0 ? Math.round(d.dominant_freq) + ' Hz' : '-- Hz';
        document.getElementById('tonalVal').textContent = Number(d.tonalness || 0).toFixed(2);
        document.getElementById('rmsVal').textContent = Number(d.raw_volume || d.volume || 0).toFixed(3);
        const gateEl = document.getElementById('gateIndicator');
        if (d.audio_connected === false) {
          gateEl.textContent = 'FLOOR GUARD (WAITING FOR AUDIO)';
          gateEl.style.color = '#ff9f0a';
        } else if (d.idle_active) {
          gateEl.textContent = (d.params && d.params.force_idle >= 0.5)
            ? 'FLOOR GUARD LOCKED (MANUAL)'
            : 'FLOOR GUARD STANDBY (NO BAND)';
          gateEl.style.color = '#ff9f0a';
        } else if ((d.volume || 0) <= 0.0001) {
          const sil = Number(d.silence_duration || 0).toFixed(1);
          const tout = Number((d.params && d.params.idle_timeout) || 4.0).toFixed(1);
          gateEl.textContent = `SILENT ${sil}s / ${tout}s → FLOOR GUARD`;
          gateEl.style.color = '#828a9f';
        } else {
          gateEl.textContent = 'LIVE AUDIO ACTIVE';
          gateEl.style.color = '#30d158';
        }
        drawStageLEDs(d.leds);
        drawSpectrum(d.spectrum, d.dominant_band);
        if (d.params && !isDragging) syncSliders(d.params, d.active_preset, d.active_preset_label);
      } catch (e) {}
    };
    es.onerror = () => {
      dot.classList.add('offline');
      es.close();
      setTimeout(connectSSE, 1500);
    };
  }

  connectSSE();
</script>
</body>
</html>
"""


def build_state_payload(shared_features: dict[str, Any]) -> dict[str, Any]:
    """Build compact telemetry + LED preview snapshot for web clients."""
    spectrum = shared_features.get("spectrum")
    if spectrum is not None and hasattr(spectrum, "tolist"):
        spec_list = [round(float(x), 4) for x in spectrum.tolist()]
    elif isinstance(spectrum, list):
        spec_list = [round(float(x), 4) for x in spectrum]
    else:
        spec_list = [0.0] * NUM_SPECTRUM_BANDS

    raw_leds = LEDEffects.last_leds
    total_leds = NUM_LEDS_PER_STRIP * NUM_STRIPS
    if not raw_leds or len(raw_leds) < total_leds:
        raw_leds = [(0, 0, 0)] * total_leds

    # Downsample 432 LEDs -> 144 LEDs (3:1, 48 per strip) for fast 20fps mobile rendering
    step = 3
    sampled_leds = [
        [int(raw_leds[i][0]), int(raw_leds[i][1]), int(raw_leds[i][2])]
        for i in range(0, total_leds, step)
    ]

    params = get_live_params()
    active_preset = get_active_preset(params)
    active_preset_label = PRESETS[active_preset]["label"] if active_preset in PRESETS else "Custom"

    return {
        "audio_connected": bool(shared_features.get("audio_connected", True)),
        "audio_device": str(shared_features.get("audio_device", "")),
        "idle_active": bool(LEDEffects.idle_active),
        "silence_duration": round(float(LEDEffects.silence_duration), 1),
        "active_preset": active_preset,
        "active_preset_label": active_preset_label,
        "volume": round(float(shared_features.get("volume", 0.0)), 4),
        "raw_volume": round(float(shared_features.get("raw_volume", shared_features.get("volume", 0.0))), 4),
        "dominant_freq": round(float(shared_features.get("dominant_freq", 0.0)), 1),
        "dominant_band": int(shared_features.get("dominant_band", -1)),
        "tonalness": round(float(shared_features.get("tonalness", 0.0)), 3),
        "spectrum": spec_list,
        "leds": sampled_leds,
        "params": params,
    }


def start_web_server(
    shared_features: dict[str, Any],
    stop_event: threading.Event,
    host: str = "0.0.0.0",
    port: int = WEB_PORT,
) -> ThreadingHTTPServer:
    """Start background HTTP + SSE server for live lighting visualization & control."""

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format: str, *args: Any) -> None:
            pass

        def _send_json(self, payload: dict[str, Any], status: int = HTTPStatus.OK) -> None:
            body = json.dumps(payload).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:
            if self.path in ("/", "/index.html"):
                body = HTML_PAGE.encode("utf-8")
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return

            if self.path == "/api/init":
                band_freqs = [
                    round(float(0.5 * (SPECTRUM_FREQS[i] + SPECTRUM_FREQS[i + 1])), 1)
                    for i in range(NUM_SPECTRUM_BANDS)
                ]
                params = get_live_params()
                active_preset = get_active_preset(params)
                active_preset_label = (
                    PRESETS[active_preset]["label"] if active_preset in PRESETS else "Custom"
                )
                self._send_json(
                    {
                        "params": params,
                        "active_preset": active_preset,
                        "active_preset_label": active_preset_label,
                        "defaults": DEFAULT_LIVE_PARAMS,
                        "presets": PRESETS,
                        "band_freqs": band_freqs,
                    }
                )
                return

            if self.path == "/api/state":
                self._send_json(build_state_payload(shared_features))
                return

            if self.path == "/api/stream":
                self.send_response(HTTPStatus.OK)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "keep-alive")
                self.end_headers()
                try:
                    while not stop_event.is_set():
                        data = json.dumps(build_state_payload(shared_features))
                        self.wfile.write(f"data: {data}\n\n".encode("utf-8"))
                        self.wfile.flush()
                        time.sleep(0.06)
                except (BrokenPipeError, ConnectionResetError, OSError):
                    return
                return

            self.send_error(HTTPStatus.NOT_FOUND)

        def do_POST(self) -> None:
            if self.path == "/api/params":
                length = int(self.headers.get("Content-Length", "0"))
                raw = self.rfile.read(length) if length > 0 else b"{}"
                try:
                    updates = json.loads(raw.decode("utf-8"))
                    if not isinstance(updates, dict):
                        raise ValueError("Expected JSON object")
                except Exception as e:
                    self._send_json({"error": str(e) or type(e).__name__}, status=HTTPStatus.BAD_REQUEST)
                    return
                updated = update_live_params(updates)
                active_preset = get_active_preset(updated)
                active_preset_label = (
                    PRESETS[active_preset]["label"] if active_preset in PRESETS else "Custom"
                )
                self._send_json(
                    {
                        "ok": True,
                        "params": updated,
                        "active_preset": active_preset,
                        "active_preset_label": active_preset_label,
                    }
                )
                return

            if self.path == "/api/reset":
                updated = reset_live_params()
                active_preset = get_active_preset(updated)
                active_preset_label = (
                    PRESETS[active_preset]["label"] if active_preset in PRESETS else "Custom"
                )
                self._send_json(
                    {
                        "ok": True,
                        "params": updated,
                        "active_preset": active_preset,
                        "active_preset_label": active_preset_label,
                    }
                )
                return

            self.send_error(HTTPStatus.NOT_FOUND)

    class ReusableThreadingHTTPServer(ThreadingHTTPServer):
        allow_reuse_address = True
        daemon_threads = True

    server = ReusableThreadingHTTPServer((host, port), Handler)

    def serve() -> None:
        try:
            server.serve_forever(poll_interval=0.25)
        except Exception:
            pass

    thread = threading.Thread(target=serve, daemon=True, name="WebServerThread")
    thread.start()

    hostname = socket.gethostname().removesuffix(".local")
    print(f"🌐 Live control UI available at: http://{hostname}.local:{port}/")

    # When running as root on Raspberry Pi (via systemd), also bind port 80
    # so http://nime-visuals.local works without typing :8080
    if port == WEB_PORT and port != 80:
        try:
            server80 = ReusableThreadingHTTPServer((host, 80), Handler)
            thread80 = threading.Thread(
                target=lambda: server80.serve_forever(poll_interval=0.25),
                daemon=True,
                name="WebServerThreadPort80",
            )
            thread80.start()
            print(f"🌐 Also listening on port 80:   http://{hostname}.local/")
        except Exception:
            pass

    return server
