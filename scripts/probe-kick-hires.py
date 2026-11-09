# -*- coding: utf-8 -*-
"""High-resolution in-page sampling: collect beat-analyser kick-band RMS
every 50 ms for 6 s (no round-trip jitter), then dump the series."""
import sys

sys.path.insert(0, '/home/hatch/workspace/.venv-playwright/lib/python3.12/site-packages')
from playwright.sync_api import sync_playwright

COLLECT_JS = """() => {
  window.__kickSeries = [];
  const beat = window.beatAnalyser;
  const arr = new Uint8Array(beat.frequencyBinCount);
  function rms(lo, hi) {
    let sum = 0, n = 0;
    for (let i = lo; i <= hi; i++) { const v = arr[i] / 255; sum += v * v; n++; }
    return n ? Math.sqrt(sum / n) : 0;
  }
  window.__kickTimer = setInterval(() => {
    beat.getByteFrequencyData(arr);
    window.__kickSeries.push({
      t: Math.round(window.audio.currentTime * 100) / 100,
      k: Math.round(rms(2, 7) * 100) / 100,
      bin2: arr[2], bin3: arr[3], bin7: arr[7]
    });
  }, 50);
  return true;
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
    page.evaluate(COLLECT_JS)
    page.wait_for_timeout(6000)
    series = page.evaluate("() => { clearInterval(window.__kickTimer); return window.__kickSeries; }")
    print('n=%d' % len(series))
    print('kick RMS 50ms:', ' '.join(str(s['k']) for s in series))
    print('times:', ' '.join(str(s['t']) for s in series))
    print('bin2:', ' '.join(str(s['bin2']) for s in series))
    browser.close()
