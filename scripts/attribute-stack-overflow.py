# -*- coding: utf-8 -*-
"""Attribute 'Maximum call stack size exceeded' page errors to UI actions.
Fresh page, one action group at a time, print error count after each group.
"""
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


def step(page, name):
    n0 = len(errors)
    page.wait_for_timeout(600)
    n1 = len(errors)
    print('%-28s errors +%d (total %d)' % (name, n1 - n0, n1), flush=True)


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
    step(page, 'load+splash')
    page.evaluate("() => { if (typeof loadHomeDiscover === 'function') loadHomeDiscover(true); }")
    page.wait_for_timeout(2000)
    step(page, 'home discover')
    # click demo tracks one by one with gaps
    try:
        n = page.locator('#home-preview-list .home-preview-track').count()
        print('preview tracks:', n)
        for i in range(min(n, 3)):
            page.locator('#home-preview-list .home-preview-track').nth(i).click()
            page.wait_for_timeout(4000)
            step(page, 'click preview track %d' % i)
    except Exception as e:
        print('preview click error:', e)
    # search + click results
    page.fill('#search-input', '周杰伦')
    page.press('#search-input', 'Enter')
    try:
        page.wait_for_selector('#search-results .search-result', state='attached', timeout=30000)
    except Exception as e:
        print('search fail:', e)
    page.wait_for_timeout(800)
    step(page, 'search 周杰伦')
    for i in range(2):
        try:
            page.locator('#search-results .search-result').nth(i).click()
            page.wait_for_timeout(4000)
            step(page, 'click search result %d' % i)
        except Exception as e:
            print('result click error:', e)
    # lyrics panel
    page.evaluate("() => { if (typeof toggleLyricsPanel === 'function') toggleLyricsPanel(true); }")
    step(page, 'lyrics panel open')
    page.evaluate("() => { if (typeof toggleLyricsPanel === 'function') toggleLyricsPanel(false); }")
    step(page, 'lyrics panel close')
    # playlist panel + tabs
    page.evaluate("() => { if (typeof togglePlaylistPanel === 'function') togglePlaylistPanel(true); }")
    step(page, 'playlist panel open')
    for tab in ('queue', 'playlists', 'podcasts'):
        page.evaluate("() => switchPlaylistTab(%s)" % repr(tab))
        step(page, 'playlist tab ' + tab)
    page.evaluate("() => { if (typeof togglePlaylistPanel === 'function') togglePlaylistPanel(false); }")
    step(page, 'playlist panel close')
    # DIY console: open, click each fx-toggle once
    page.evaluate("() => { if (typeof openDiyRhythmConsole === 'function') openDiyRhythmConsole(); }")
    page.wait_for_timeout(800)
    step(page, 'diy open')
    toggles = page.evaluate(
        "() => Array.from(document.querySelectorAll('#fx-panel .fx-toggle')).map(e => e.id)")
    print('fx toggles:', toggles)
    for tid in toggles:
        page.evaluate("() => { var el = document.getElementById(%s); if (el) el.click(); }" % repr(tid))
        step(page, 'fx toggle ' + tid)
    # DIY seg buttons
    segs = page.evaluate(
        "() => Array.from(document.querySelectorAll('#fx-panel .fx-seg button')).map(e => (e.parentElement.id || '') + ':' + (e.textContent || '').trim())")
    print('fx seg buttons:', len(segs))
    for label in segs:
        seg_id, txt = label.split(':', 1)
        page.evaluate(
            """([sid, t]) => {
              const seg = document.getElementById(sid);
              if (!seg) return;
              const b = Array.from(seg.querySelectorAll('button')).find(x => (x.textContent||'').trim() === t);
              if (b) b.click();
            }""", [seg_id, txt])
        step(page, 'fx seg ' + label)
    page.evaluate("() => { if (typeof toggleFxPanel === 'function') toggleFxPanel(false); }")
    step(page, 'diy close')
    # login modal
    page.evaluate("() => { if (typeof showLoginModal === 'function') showLoginModal(); }")
    page.wait_for_timeout(1000)
    step(page, 'login modal open')
    for bid in ('refresh-qr-btn', 'qq-cookie-toggle-btn', 'login-both-btn'):
        page.evaluate("() => { var el = document.getElementById(%s); if (el) el.click(); }" % repr(bid))
        step(page, 'login btn ' + bid)
    page.evaluate("() => { if (typeof closeLoginModal === 'function') closeLoginModal(); }")
    step(page, 'login modal close')
    # user modal
    page.evaluate("() => { if (typeof onUserBtnClick === 'function') onUserBtnClick(); }")
    page.wait_for_timeout(800)
    step(page, 'user modal open')
    page.evaluate("() => { if (typeof closeUserModal === 'function') closeUserModal(); }")
    step(page, 'user modal close')
    # about modal (Phase 2)
    page.evaluate("() => { if (typeof window.starwaveOpenAbout === 'function') window.starwaveOpenAbout(); }")
    page.wait_for_timeout(800)
    step(page, 'about modal open')
    page.evaluate("() => { if (typeof window.starwaveCloseAbout === 'function') window.starwaveCloseAbout(); }")
    step(page, 'about modal close')
    print('TOTAL page errors:', len(errors))
    browser.close()
    if relay_proc:
        relay_proc.terminate()
