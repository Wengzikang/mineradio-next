# -*- coding: utf-8 -*-
"""Direct diagnostic: sample kick-band RMS from window.beatAnalyser and
window.analyser side by side, plus analyserMode / p3 lastKick."""
import sys

sys.path.insert(0, '/home/hatch/workspace/.venv-playwright/lib/python3.12/site-packages')
from playwright.sync_api import sync_playwright

JS = """() => {
  const a = window.audio;
  const beat = window.beatAnalyser, main = window.analyser;
  function rms(arr, lo, hi) {
    let sum = 0, n = 0;
    for (let i = lo; i <= hi; i++) { const v = arr[i] / 255; sum += v * v; n++; }
    return n ? Math.sqrt(sum / n) : 0;
  }
  let b = null, m = null;
  if (beat) { const arr = new Uint8Array(beat.frequencyBinCount); beat.getByteFrequencyData(arr); b = rms(arr, 2, 7); }
  if (main) { const arr = new Uint8Array(main.frequencyBinCount); main.getByteFrequencyData(arr); m = rms(arr, 2, 7); }
  return { mode: window.starwavePhase3.analyserMode(), beatExists: !!beat, mainExists: !!main,
           beatKick: b === null ? null : Math.round(b * 100) / 100,
           mainKick: m === null ? null : Math.round(m * 100) / 100,
           p3kick: Math.round(window.starwavePhase3.beatInfo().kick * 100) / 100,
           paused: a ? a.paused : null, ct: a ? Math.round(a.currentTime * 10) / 10 : null };
}"""

with sync_playwright() as pw:
    browser = pw.chromium.launch(args=[
        '--ignore-certificate-errors',
        '--proxy-server=http://127.0.0.1:18082',
        '--autoplay-policy=no-user-gesture-required',
        '--mute-audio',
    ])
    page = browser.new_page(viewport={'width': 1280, 'height': 800})
    page.goto('http://127.0.0.1:4174/', wait_until='load')
    page.wait_for_timeout(4000)
    page.set_input_files('#file-input', '/tmp/sw-kick90.wav')
    page.wait_for_timeout(3000)
    page.evaluate("() => { window.__sw3BeatTimer = setInterval(() => window.starwavePhase3.sampleBeat(), 100); }")
    for _ in range(25):
        page.wait_for_timeout(150)
        print(page.evaluate(JS))
    page.evaluate("() => { clearInterval(window.__sw3BeatTimer); }")
    browser.close()
