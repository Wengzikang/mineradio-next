# -*- coding: utf-8 -*-
"""Capture overflow stack using the audit's exact interaction style:
Playwright page.click(force=True), Escape, modal-close evaluate."""
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


STACK_JS = """() => {
  window.__swStacks = [];
  window.addEventListener('error', (e) => {
    const err = e.error;
    window.__swStacks.push({
      message: e.message,
      stack: err && err.stack ? String(err.stack).slice(0, 4000) : '(no stack)',
      time: Date.now()
    });
  });
}"""


def audit_clicks(page, root_selector):
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
            print('  click-error %s %s: %s' % (b['id'], b['text'], str(e)[:100]), flush=True)


with sync_playwright() as pw:
    relay_proc = ensure_relay()
    proxy_cfg = {'server': 'http://127.0.0.1:%d' % RELAY_PORT,
                 'bypass': 'localhost,127.0.0.1,::1'}
    browser = pw.chromium.launch(
        args=['--autoplay-policy=no-user-gesture-required', '--ignore-certificate-errors'],
        proxy=proxy_cfg)
    page = browser.new_page(viewport={'width': 1280, 'height': 900})
    page.goto('http://127.0.0.1:4173/', wait_until='load', timeout=60000)
    page.evaluate(STACK_JS)
    page.wait_for_timeout(2000)
    try:
        page.wait_for_selector('#splash.ready', state='attached', timeout=30000)
        page.click('#splash', timeout=5000)
    except Exception:
        page.evaluate("() => { if (typeof dismissSplash === 'function') dismissSplash(); }")
    page.wait_for_timeout(1200)
    page.evaluate("() => { if (typeof loadHomeDiscover === 'function') loadHomeDiscover(true); }")
    page.wait_for_timeout(1500)
    print('stacks before home:', page.evaluate("() => window.__swStacks.length"), flush=True)
    audit_clicks(page, '#empty-home')
    print('stacks after home:', page.evaluate("() => window.__swStacks.length"), flush=True)
    page.fill('#search-input', '周杰伦')
    page.press('#search-input', 'Enter')
    try:
        page.wait_for_selector('#search-results .search-result', state='attached', timeout=30000)
    except Exception as e:
        print('search fail:', e)
    page.wait_for_timeout(800)
    audit_clicks(page, '#search-area')
    print('stacks after search:', page.evaluate("() => window.__swStacks.length"), flush=True)
    # lyrics phase like the audit
    try:
        page.locator('#home-preview-list .home-preview-track').first.click()
        page.wait_for_timeout(3500)
    except Exception as e:
        print('demo click fail:', e)
    page.evaluate("() => { if (typeof toggleLyricsPanel === 'function') toggleLyricsPanel(true); }")
    page.wait_for_timeout(800)
    print('stacks after lyrics open:', page.evaluate("() => window.__swStacks.length"), flush=True)
    audit_clicks(page, '#lyrics-panel')
    print('stacks after lyrics clicks:', page.evaluate("() => window.__swStacks.length"), flush=True)
    stacks = page.evaluate("() => window.__swStacks")
    print('total stacks:', len(stacks))
    for s in stacks[:2]:
        print('=== message:', s['message'])
        print(s['stack'])
    with open('/tmp/sw-stacks2.json', 'w', encoding='utf-8') as f:
        json.dump(stacks, f, ensure_ascii=False, indent=2)
    browser.close()
    if relay_proc:
        relay_proc.terminate()
