# -*- coding: utf-8 -*-
"""Bisect 'Maximum call stack size exceeded': replicate the audit's rapid
force-clicking per view, logging error count after EACH click."""
import json
import os
import re
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


def click_probe(page, root_selector, view):
    btns = page.evaluate(
        """(rootSel) => {
          const root = rootSel ? document.querySelector(rootSel) : document;
          if (!root) return [];
          const out = [];
          root.querySelectorAll('button, [onclick], input[type=button]').forEach((el) => {
            const r = el.getBoundingClientRect();
            const cs = getComputedStyle(el);
            const visible = r.width > 0 && r.height > 0 && cs.display !== 'none'
              && cs.visibility !== 'hidden' && cs.pointerEvents !== 'none';
            out.push({ id: el.id || '', text: (el.textContent || '').trim().slice(0, 40),
                       onclick: el.getAttribute('onclick') || '', visible: visible,
                       disabled: !!el.disabled });
          });
          return out;
        }""", root_selector)
    for b in btns:
        if not b['visible'] or b['disabled']:
            continue
        if 'file-input' in b['onclick'] or 'installStarWavePwa' in b['onclick']:
            continue
        n0 = len(errors)
        try:
            if b['id']:
                page.click('#' + b['id'], timeout=3000, force=True)
            else:
                page.evaluate(
                    """(txt) => {
                      const el = Array.from(document.querySelectorAll('button'))
                        .find(e => (e.textContent||'').trim().slice(0,40) === txt
                          && e.getBoundingClientRect().width > 0);
                      if (el) el.click();
                    }""", b['text'])
            page.wait_for_timeout(450)
            page.keyboard.press('Escape')
            page.wait_for_timeout(200)
            page.evaluate(
                """() => {
                  document.querySelectorAll('.modal-mask.show').forEach(m => {
                    const c = m.querySelector('.btn-row .modal-btn');
                    if (c) c.click();
                  });
                }""")
            page.wait_for_timeout(200)
        except Exception as e:
            print('  [%s] click-error %s %s: %s' % (view, b['id'], b['text'], str(e)[:100]), flush=True)
        n1 = len(errors)
        if n1 > n0:
            print('  [%s] +%d errors after click id=%s text=%s onclick=%s' % (
                view, n1 - n0, b['id'], b['text'], b['onclick'][:120]), flush=True)


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
    print('== home probe (total errors before: %d)' % len(errors), flush=True)
    click_probe(page, '#empty-home', 'home')
    print('home done, total errors: %d' % len(errors), flush=True)
    page.fill('#search-input', '周杰伦')
    page.press('#search-input', 'Enter')
    try:
        page.wait_for_selector('#search-results .search-result', state='attached', timeout=30000)
    except Exception as e:
        print('search fail:', e)
    page.wait_for_timeout(800)
    print('== search probe (total errors before: %d)' % len(errors), flush=True)
    click_probe(page, '#search-area', 'search')
    print('search done, total errors: %d' % len(errors), flush=True)
    print('distinct errors:', json.dumps(list(set(errors))[:5], ensure_ascii=False))
    browser.close()
    if relay_proc:
        relay_proc.terminate()
