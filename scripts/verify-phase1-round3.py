# -*- coding: utf-8 -*-
"""StarWave Phase 1 verification round 3: the FREE-play path.
Searches 晴天, clicks the known-free track 晴天 (弦乐版) / 球球忘不掉
(id 3455095614, fee 0 — curl-verified to return a real url without login)
and checks it really plays with Netease lyrics.
Usage: python3 scripts/verify-phase1-round3.py
"""
import json
import os
import sys

import importlib.util

_spec = importlib.util.spec_from_file_location(
    'verify_phase1_round2',
    os.path.join(os.path.dirname(os.path.abspath(__file__)), 'verify-phase1-round2.py'))
_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mod)
RELAY_PORT = _mod.RELAY_PORT
ensure_relay = _mod.ensure_relay
audio_state = _mod.audio_state
lyric_state = _mod.lyric_state
toast_text = _mod.toast_text
trial_banner = _mod.trial_banner
dismiss_splash = _mod.dismiss_splash
search = _mod.search

from playwright.sync_api import sync_playwright

with sync_playwright() as pw:
    relay_proc = ensure_relay()
    browser = pw.chromium.launch(
        args=['--autoplay-policy=no-user-gesture-required', '--ignore-certificate-errors'],
        proxy={'server': 'http://127.0.0.1:%d' % RELAY_PORT, 'bypass': 'localhost,127.0.0.1,::1'},
    )
    page = browser.new_page(viewport={'width': 1280, 'height': 900})
    errs = []
    page.on('pageerror', lambda e: errs.append(str(e)))
    page.on('console', lambda m: errs.append(m.text) if m.type == 'error' else None)

    page.goto('http://127.0.0.1:4173/', wait_until='load', timeout=60000)
    dismiss_splash(page)
    results = search(page, '晴天')
    for i, r in enumerate(results):
        print('%2d - [%s] %s | %s' % (i, r['tag'], r['title'], r['meta']))
    target = None
    for i, r in enumerate(results):
        if r['tag'] == '网易云' and '弦乐版' in r['title']:
            target = i
            break
    print('target (弦乐版):', target)
    if target is None:
        print('FAIL: 弦乐版 not in results; cannot prove free-play path')
    else:
        print('clicking:', results[target]['title'])
        page.locator('#search-results .search-result').nth(target).click()
        page.wait_for_timeout(5000)
        st1 = audio_state(page)
        page.wait_for_timeout(2000)
        st2 = audio_state(page)
        print(json.dumps({
            'title': results[target]['title'],
            'playing': bool(st2.get('exists') and not st2.get('paused')),
            'time_advanced': bool(st2.get('currentTime', 0) > st1.get('currentTime', 0)),
            'audio_src': (st2.get('src') or '')[:130],
            'duration': st2.get('duration'),
            'toast': toast_text(page),
            'trial_banner': trial_banner(page),
            'lyrics': lyric_state(page),
            'thumb_title': page.evaluate("() => (document.getElementById('thumb-title')||{}).textContent || ''"),
        }, ensure_ascii=False, indent=1))
    print('page/console errors (%d):' % len(errs))
    for e in errs:
        print('  ERR:', e[:400])
    browser.close()
    if relay_proc:
        relay_proc.terminate()
