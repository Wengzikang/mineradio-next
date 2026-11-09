# -*- coding: utf-8 -*-
"""Playlist detail via real import: paste a public Netease playlist link into
search and import it, then open its detail view."""
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
    page.fill('#search-input', 'https://music.163.com/#/playlist?id=3778678')
    page.evaluate("() => { if (typeof runPlaylistImportFromSearch === 'function') runPlaylistImportFromSearch(); }")
    page.wait_for_timeout(12000)
    print('toast:', page.evaluate("() => { const t = document.getElementById('toast'); return t ? t.textContent.trim() : ''; }"))
    print('user playlists:',
          page.evaluate("() => (window.userPlaylists || []).map(p => (p.title || p.name) + '|' + (p.provider || ''))"))
    page.evaluate("() => { if (typeof togglePlaylistPanel === 'function') togglePlaylistPanel(true); }")
    page.wait_for_timeout(1200)
    report['detail'] = page.evaluate(
        """() => {
          const panel = document.getElementById('playlist-panel');
          const cards = panel ? panel.querySelectorAll('[data-playlist-title], .playlist-card, .playlist-item') : [];
          const out = { cards: cards.length };
          if (cards.length) { cards[0].click(); out.clicked = true; }
          return out; }""")
    page.wait_for_timeout(2000)
    report['detail']['panel_text'] = page.evaluate(
        "() => { const p = document.getElementById('playlist-panel');"
        " return p ? p.textContent.slice(0, 500) : 'missing'; }")
    report['detail']['state'] = page.evaluate(
        "() => (typeof playlistPanelDetailState !== 'undefined') ? JSON.stringify(playlistPanelDetailState).slice(0, 400) : 'n/a'")
    print(json.dumps(report['detail'], ensure_ascii=False, indent=1))
    page.screenshot(path='/tmp/sw-v2-playlist-detail.png')
    print('page errors:', report.get('page_errors', []))
    browser.close()
    if relay_proc:
        relay_proc.terminate()
    with open('/tmp/sw-phase2-followup3.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
