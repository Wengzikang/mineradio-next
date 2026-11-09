# -*- coding: utf-8 -*-
"""Follow-up part 2: playlist detail view + MusicKit load.
Uses JS clicks (Playwright hit-testing is blocked by the canvas once audio
is playing and home hides — same pre-existing overlay behaviour)."""
import json
import os
import socket
import subprocess
import sys
import time

from playwright.sync_api import sync_playwright

RELAY_PORT = 18082
RELAY_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'verify-relay-proxy.py')


def ensure_relay():
    s = socket.socket()
    try:
        s.connect(('127.0.0.1', RELAY_PORT))
        s.close()
        return None
    except OSError:
        pass
    proc = subprocess.Popen([sys.executable, RELAY_SCRIPT],
                            stdout=open('/tmp/sw-relay.log', 'w'), stderr=subprocess.STDOUT)
    for _ in range(30):
        try:
            s = socket.socket()
            s.connect(('127.0.0.1', RELAY_PORT))
            s.close()
            return proc
        except OSError:
            time.sleep(0.2)
    raise RuntimeError('relay did not start')


report = {}
with sync_playwright() as pw:
    relay_proc = ensure_relay()
    proxy_cfg = {'server': 'http://127.0.0.1:%d' % RELAY_PORT,
                 'bypass': 'localhost,127.0.0.1,::1'}
    browser = pw.chromium.launch(
        args=['--autoplay-policy=no-user-gesture-required', '--ignore-certificate-errors'],
        proxy=proxy_cfg)
    page = browser.new_page(viewport={'width': 1280, 'height': 900})
    page.on('pageerror', lambda e: report.setdefault('page_errors', []).append(str(e)))
    page.goto('http://127.0.0.1:4173/', wait_until='load', timeout=60000)
    page.wait_for_timeout(2000)
    try:
        page.wait_for_selector('#splash.ready', state='attached', timeout=30000)
        page.click('#splash', timeout=5000)
    except Exception:
        page.evaluate("() => { if (typeof dismissSplash === 'function') dismissSplash(); }")
    page.wait_for_timeout(1200)
    page.evaluate("() => { if (typeof loadHomeDiscover === 'function') loadHomeDiscover(true); }")
    page.wait_for_timeout(1500)
    # play demo track via JS click, then collect it into a new playlist
    page.evaluate("() => { const el = document.querySelector('#home-preview-list .home-preview-track'); if (el) el.click(); }")
    page.wait_for_timeout(4000)
    print('playing:', page.evaluate("() => { const a = window.audio; return a ? !a.paused : 'no-audio'; }"))
    page.evaluate("() => { if (typeof openCollectModalForCurrent === 'function') openCollectModalForCurrent(); }")
    page.wait_for_timeout(800)
    print('collect modal shown:',
          page.evaluate("() => { const m = document.getElementById('collect-modal'); return m ? m.classList.contains('show') : 'missing'; }"))
    page.evaluate("() => { const i = document.getElementById('collect-new-name'); if (i) { i.value = 'Phase2测试歌单'; } }")
    page.evaluate("() => { if (typeof createPlaylistFromCollect === 'function') createPlaylistFromCollect(); }")
    page.wait_for_timeout(1200)
    print('user playlists now:',
          page.evaluate("() => (window.userPlaylists || []).map(p => p.title || p.name)"))
    # open playlist panel and click the first playlist card
    page.evaluate("() => { if (typeof togglePlaylistPanel === 'function') togglePlaylistPanel(true); }")
    page.wait_for_timeout(1000)
    report['playlist_detail'] = page.evaluate(
        """() => {
          const panel = document.getElementById('playlist-panel');
          const cards = panel ? panel.querySelectorAll('[data-playlist-title], .playlist-card, .playlist-item, [data-pl-detail]') : [];
          const out = { cards: cards.length, panelTextBefore: panel ? panel.textContent.slice(0, 200) : '' };
          if (cards.length) { cards[0].click(); out.clicked = true; }
          return out; }""")
    page.wait_for_timeout(1500)
    report['playlist_detail']['panel_text_after'] = page.evaluate(
        "() => { const p = document.getElementById('playlist-panel');"
        " return p ? p.textContent.slice(0, 400) : 'missing'; }")
    report['playlist_detail']['detail_state'] = page.evaluate(
        "() => (typeof playlistPanelDetailState !== 'undefined') ? JSON.stringify(playlistPanelDetailState).slice(0, 300) : 'n/a'")
    print(json.dumps(report['playlist_detail'], ensure_ascii=False, indent=1))
    page.screenshot(path='/tmp/sw-v2-playlist-detail.png')

    print('== MusicKit load')
    report['apple_load'] = page.evaluate(
        "async () => { const ok = await window.starwaveAppleMusic.load();"
        " return { loaded: ok, musicKit: !!window.MusicKit,"
        " statusText: window.starwaveAppleMusic.statusText() }; }")
    print(json.dumps(report['apple_load'], ensure_ascii=False, indent=1))
    print('page errors:', report.get('page_errors', []))
    browser.close()
    if relay_proc:
        relay_proc.terminate()
    with open('/tmp/sw-phase2-followup2.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
