# -*- coding: utf-8 -*-
"""Capture the stack of the first 'Maximum call stack size exceeded' error."""
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


with sync_playwright() as pw:
    relay_proc = ensure_relay()
    proxy_cfg = {'server': 'http://127.0.0.1:%d' % RELAY_PORT,
                 'bypass': 'localhost,127.0.0.1,::1'}
    browser = pw.chromium.launch(
        args=['--autoplay-policy=no-user-gesture-required', '--ignore-certificate-errors'],
        proxy=proxy_cfg)
    page = browser.new_page(viewport={'width': 1280, 'height': 900})
    page.goto('http://127.0.0.1:4173/', wait_until='load', timeout=60000)
    page.evaluate(
        """() => {
          window.__swStacks = [];
          window.addEventListener('error', (e) => {
            const err = e.error;
            window.__swStacks.push({
              message: e.message,
              stack: err && err.stack ? String(err.stack).slice(0, 3000) : '(no stack)',
              time: Date.now()
            });
          });
        }""")
    page.wait_for_timeout(2000)
    try:
        page.wait_for_selector('#splash.ready', state='attached', timeout=30000)
        page.click('#splash', timeout=5000)
    except Exception:
        page.evaluate("() => { if (typeof dismissSplash === 'function') dismissSplash(); }")
    page.wait_for_timeout(1200)
    page.evaluate("() => { if (typeof loadHomeDiscover === 'function') loadHomeDiscover(true); }")
    page.wait_for_timeout(1500)
    # replicate audit home probe: force-click every visible button in #empty-home
    page.evaluate(
        """() => {
          const btns = Array.from(document.querySelectorAll('#empty-home button, #empty-home [onclick]'))
            .filter(el => { const r = el.getBoundingClientRect();
              return r.width > 0 && r.height > 0 && getComputedStyle(el).display !== 'none'; });
          window.__swHomeBtns = btns.map(el => el.id || (el.textContent||'').trim().slice(0,30));
          btns.forEach(el => { try { el.click(); } catch (e) {} });
        }""")
    page.wait_for_timeout(5000)
    print('after home burst, stacks:', page.evaluate("() => window.__swStacks.length"))
    # search + click results like the audit
    page.fill('#search-input', '周杰伦')
    page.press('#search-input', 'Enter')
    try:
        page.wait_for_selector('#search-results .search-result', state='attached', timeout=30000)
    except Exception as e:
        print('search fail:', e)
    page.wait_for_timeout(1000)
    page.evaluate(
        """() => {
          document.querySelectorAll('#search-area button').forEach(el => {
            const r = el.getBoundingClientRect();
            if (r.width > 0 && getComputedStyle(el).display !== 'none') { try { el.click(); } catch (e) {} }
          });
          document.querySelectorAll('#search-results .search-result').forEach(el => { try { el.click(); } catch (e) {} });
        }""")
    page.wait_for_timeout(8000)
    stacks = page.evaluate("() => window.__swStacks")
    print('total stacks captured:', len(stacks))
    for s in stacks[:3]:
        print('=== message:', s['message'])
        print(s['stack'])
    with open('/tmp/sw-stacks.json', 'w', encoding='utf-8') as f:
        json.dump(stacks, f, ensure_ascii=False, indent=2)
    browser.close()
    if relay_proc:
        relay_proc.terminate()
