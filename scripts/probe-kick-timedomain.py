# -*- coding: utf-8 -*-
"""Time-domain check: is the waveform itself sustained between kicks
(double playback) or silent (analyser/FFT artefact)?"""
import sys

sys.path.insert(0, '/home/hatch/workspace/.venv-playwright/lib/python3.12/site-packages')
from playwright.sync_api import sync_playwright

JS = """() => {
  const a = window.audio;
  const beat = window.beatAnalyser;
  const arr = new Uint8Array(beat.fftSize);
  beat.getByteTimeDomainData(arr);
  let min = 255, max = 0, sum = 0;
  for (let i = 0; i < arr.length; i++) {
    if (arr[i] < min) min = arr[i];
    if (arr[i] > max) max = arr[i];
    const d = arr[i] - 128; sum += d * d;
  }
  const rms = Math.sqrt(sum / arr.length) / 128;
  return { ct: a ? Math.round(a.currentTime * 100) / 100 : null,
           tdMin: min, tdMax: max, tdRms: Math.round(rms * 1000) / 1000 };
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
    for _ in range(20):
        page.wait_for_timeout(200)
        print(page.evaluate(JS))
    browser.close()
