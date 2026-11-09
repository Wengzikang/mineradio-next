# -*- coding: utf-8 -*-
"""Focused probe: (1) BPM on the 90 BPM kick file with 10 Hz sampleBeat
driving, (2) NetEase public-playlist import notice text. Reuses relay 18082
and range server 4174 (must already be running).
"""
import json
import sys

sys.path.insert(0, '/home/hatch/workspace/.venv-playwright/lib/python3.12/site-packages')
from playwright.sync_api import sync_playwright

BASE_URL = 'http://127.0.0.1:4174/'


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=[
            '--ignore-certificate-errors',
            '--proxy-server=http://127.0.0.1:18082',
            '--autoplay-policy=no-user-gesture-required',
            '--mute-audio',
        ])
        page = browser.new_page(viewport={'width': 1280, 'height': 800})
        page.on('pageerror', lambda e: print('PAGEERROR', str(e)[:300]))
        page.goto(BASE_URL, wait_until='load')
        page.wait_for_timeout(4000)

        # (1) BPM: import the deterministic 90 BPM kick file
        page.set_input_files('#file-input', '/tmp/sw-kick90.wav')
        page.wait_for_timeout(3000)
        page.evaluate("() => { window.__sw3BeatTimer = setInterval(() => window.starwavePhase3.sampleBeat(), 100); }")
        beats = []
        for _ in range(24):
            page.wait_for_timeout(500)
            beats.append(page.evaluate("() => window.starwavePhase3.beatInfo()"))
        page.evaluate("() => { clearInterval(window.__sw3BeatTimer); }")
        print('BPM kick90: max_kick=%.3f max_onsets=%d last_bpm=%s conf=%s' % (
            max(b.get('kick', 0) for b in beats),
            max(b.get('onsets', 0) for b in beats),
            beats[-1].get('bpm'), beats[-1].get('bpmConfidence')))
        print('  bpm series:', [b.get('bpm') for b in beats])
        print('  onset series:', [b.get('onsets') for b in beats])

        # (2) import notice
        page.evaluate("() => { const i = document.getElementById('search-input'); if (i) { i.value = 'https://music.163.com/playlist?id=3778678'; } }")
        page.evaluate("() => { if (typeof runPlaylistImportFromSearch === 'function') runPlaylistImportFromSearch(); }")
        page.wait_for_timeout(3000)
        imp = page.evaluate(
            "() => ({ notice_shown: document.getElementById('source-fallback-notice').classList.contains('show'),"
            " notice_title: (document.getElementById('source-fallback-title')||{}).textContent || '',"
            " notice_body: (document.getElementById('source-fallback-body')||{}).textContent || '',"
            " has_3778678: (window.userPlaylists||[]).some(p => String(p.id) === '3778678') })")
        print('import notice:', json.dumps(imp, ensure_ascii=False))
        browser.close()


if __name__ == '__main__':
    main()
