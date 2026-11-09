# -*- coding: utf-8 -*-
"""Dump the kick envelope at 100 ms resolution + onset times on the 90 BPM
kick file, to see why ~1/3 of kicks are missed."""
import json
import sys

sys.path.insert(0, '/home/hatch/workspace/.venv-playwright/lib/python3.12/site-packages')
from playwright.sync_api import sync_playwright

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
    series = []
    for _ in range(60):
        page.wait_for_timeout(100)
        series.append(page.evaluate("() => { const b = window.starwavePhase3.beatInfo(); return { k: Math.round(b.kick * 100) / 100, o: b.onsets, t: Math.round(b.lastOnsetAt * 100) / 100 }; }"))
    page.evaluate("() => { clearInterval(window.__sw3BeatTimer); }")
    print('kick envelope (100ms steps, 6s):')
    print(' '.join(str(s['k']) for s in series))
    print('onsets over time:', [(i, s['o'], s['t']) for i, s in enumerate(series) if i == 0 or s['o'] != series[i - 1]['o']])
    browser.close()
