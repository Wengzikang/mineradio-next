# -*- coding: utf-8 -*-
"""Targeted regression for the listen-stats recursion fix:
rapid track switching (the exact trigger) must produce 0 page errors."""
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


errors = []
with sync_playwright() as pw:
    relay_proc = ensure_relay()
    proxy_cfg = {'server': 'http://127.0.0.1:%d' % RELAY_PORT,
                 'bypass': 'localhost,127.0.0.1,::1'}
    browser = pw.chromium.launch(
        args=['--autoplay-policy=no-user-gesture-required', '--ignore-certificate-errors'],
        proxy=proxy_cfg)
    page = browser.new_page(viewport={'width': 1280, 'height': 900})
    page.on('pageerror', lambda e: errors.append(str(e)))
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
    # rapid switching: click all 6 preview tracks with only 700ms gaps
    for i in range(6):
        page.evaluate("() => { const els = document.querySelectorAll('#home-preview-list .home-preview-track');"
                      " if (els[%d]) els[%d].click(); }" % (i, i))
        page.wait_for_timeout(700)
    print('after 6 rapid track clicks, errors:', len(errors), flush=True)
    # rapid next/prev via keyboard-free JS calls
    for _ in range(8):
        page.evaluate("() => { if (typeof nextTrack === 'function') nextTrack(); }")
        page.wait_for_timeout(400)
    for _ in range(4):
        page.evaluate("() => { if (typeof prevTrack === 'function') prevTrack(); }")
        page.wait_for_timeout(400)
    page.wait_for_timeout(3000)
    print('after 12 rapid next/prev, errors:', len(errors), flush=True)
    print('playing:', page.evaluate("() => { const a = window.audio; return a ? !a.paused : 'no-audio'; }"))
    print('current track:', page.evaluate("() => (window.playQueue[window.currentIdx]||{}).name || ''"))
    print('distinct errors:', set(errors))
    browser.close()
    if relay_proc:
        relay_proc.terminate()
