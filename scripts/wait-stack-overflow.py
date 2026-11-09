# -*- coding: utf-8 -*-
"""Is the stack overflow time-based? Load, play one demo track, wait 150s
doing nothing, count page errors every 15s."""
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
    page.evaluate("() => { const el = document.querySelector('#home-preview-list .home-preview-track'); if (el) el.click(); }")
    page.wait_for_timeout(3000)
    print('playing:', page.evaluate("() => { const a = window.audio; return a ? !a.paused : 'no-audio'; }"),
          'fps:', page.evaluate("() => (window.__starwavePerf || {}).fps"),
          'errors:', len(errors), flush=True)
    for i in range(10):
        page.wait_for_timeout(15000)
        print('t+%ds errors=%d fps=%s tier=%s' % (
            (i + 1) * 15, len(errors),
            page.evaluate("() => (window.__starwavePerf || {}).fps"),
            page.evaluate("() => window.starwavePerfGovernor.tier")), flush=True)
    print('distinct:', set(errors))
    browser.close()
    if relay_proc:
        relay_proc.terminate()
