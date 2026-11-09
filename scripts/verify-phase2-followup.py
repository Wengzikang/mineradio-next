# -*- coding: utf-8 -*-
"""Focused follow-ups after verify-phase2:
(a) Spotify auth URL params via buildAuthUrl() directly (popup navigation
    to accounts.spotify.com fails in this VM, so inspect the URL string)
(b) radio queue composition after iTunes English-query fix + chip visible
(c) playlist detail view with a real created playlist
(d) MusicKit JS load outcome
"""
import json
import os
import socket
import subprocess
import sys
import time
import urllib.parse

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

    print('== (a) Spotify auth URL (direct buildAuthUrl)')
    url = page.evaluate("async () => await window.starwaveSpotify.buildAuthUrl()")
    parsed = urllib.parse.urlparse(url)
    qs = urllib.parse.parse_qs(parsed.query)
    report['spotify_auth_url'] = {
        'url': url,
        'scheme_host': parsed.scheme + '://' + parsed.netloc,
        'path': parsed.path,
        'client_id': qs.get('client_id', [''])[0],
        'redirect_uri': qs.get('redirect_uri', [''])[0],
        'scope': qs.get('scope', [''])[0],
        'response_type': qs.get('response_type', [''])[0],
        'code_challenge_method': qs.get('code_challenge_method', [''])[0],
        'code_challenge_len': len(qs.get('code_challenge', [''])[0]),
        'state_len': len(qs.get('state', [''])[0]),
    }
    print(json.dumps(report['spotify_auth_url'], ensure_ascii=False, indent=1))
    print('verifier in localStorage:',
          page.evaluate("() => !!localStorage.getItem('starwave.spotify.pkce_verifier')"))
    print('pendingLogin:',
          page.evaluate("() => window.starwaveSpotify.pendingLogin()"))
    print('sessionStorage has verifier (must be false):',
          page.evaluate("() => !!sessionStorage.getItem('starwave.spotify.pkce_verifier')"))

    print('== (b) radio composition + chip')
    page.evaluate("() => window.starwaveRadio.start('relax')")
    page.wait_for_timeout(12000)
    report['radio'] = page.evaluate(
        """() => ({ status: window.starwaveRadio.status(),
                   queueLen: (window.playQueue || []).length,
                   sources: (window.playQueue || []).map(s => (s.provider || s.source) + ':' + s.name),
                   chip: (() => { const c = document.getElementById('starwave-radio-chip');
                     return c ? { display: getComputedStyle(c).display, text: c.textContent } : 'missing'; })(),
                   playing: (() => { const a = window.audio; return a ? !a.paused : false; })() })""")
    print(json.dumps(report['radio'], ensure_ascii=False, indent=1))
    page.evaluate("() => window.starwaveRadio.stop()")

    print('== (c) playlist detail with a real playlist')
    # create a playlist via the collect flow: play a demo track, collect it
    page.evaluate("() => { if (typeof loadHomeDiscover === 'function') loadHomeDiscover(true); }")
    page.wait_for_timeout(1500)
    try:
        page.locator('#home-preview-list .home-preview-track').first.click()
        page.wait_for_timeout(3500)
    except Exception as e:
        print('demo click fail:', e)
    page.evaluate("() => { if (typeof openCollectModalForCurrent === 'function') openCollectModalForCurrent(); }")
    page.wait_for_timeout(800)
    page.fill('#collect-new-name', 'Phase2测试歌单')
    page.evaluate("() => { if (typeof createPlaylistFromCollect === 'function') createPlaylistFromCollect(); }")
    page.wait_for_timeout(1000)
    print('collect modal closed:',
          page.evaluate("() => { const m = document.getElementById('collect-modal'); return m ? !m.classList.contains('show') : 'missing'; }"))
    page.evaluate("() => { if (typeof togglePlaylistPanel === 'function') togglePlaylistPanel(true); }")
    page.wait_for_timeout(1000)
    report['playlist_detail'] = page.evaluate(
        """() => {
          const cards = document.querySelectorAll('#playlist-panel [data-playlist-title], #playlist-panel .playlist-card, #playlist-panel .playlist-item');
          const info = { cards: cards.length };
          if (cards.length) { cards[0].click(); info.clicked = true; }
          return info; }""")
    page.wait_for_timeout(1200)
    report['playlist_detail']['panel_text'] = page.evaluate(
        "() => { const p = document.getElementById('playlist-panel');"
        " return p ? p.textContent.slice(0, 300) : 'missing'; }")
    print(json.dumps(report['playlist_detail'], ensure_ascii=False, indent=1))
    page.screenshot(path='/tmp/sw-v2-playlist-detail.png')

    print('== (d) MusicKit load')
    report['apple_load'] = page.evaluate(
        "async () => { const ok = await window.starwaveAppleMusic.load();"
        " return { loaded: ok, musicKit: !!window.MusicKit,"
        " statusText: window.starwaveAppleMusic.statusText() }; }")
    print(json.dumps(report['apple_load'], ensure_ascii=False, indent=1))

    print('page errors:', report.get('page_errors', []))
    browser.close()
    if relay_proc:
        relay_proc.terminate()
    with open('/tmp/sw-phase2-followup.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print('written to /tmp/sw-phase2-followup.json')
