# -*- coding: utf-8 -*-
"""StarWave Phase 1 verification round 2 (real browser, real network).
Goal: prove the two paths round 1 could not reach —
  (1) a FREE Netease track (fee 0) actually plays, with Netease lyrics;
  (2) a login-required track WITH an iTunes preview shows the manual
      30s-trial offer, and clicking it plays the trial (no auto-play).
Reuses the relay setup from verify-phase1.py (same VM egress MITM workaround).
Usage: python3 scripts/verify-phase1-round2.py
"""
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
    proc = subprocess.Popen(
        [sys.executable, RELAY_SCRIPT],
        stdout=open('/tmp/sw-relay.log', 'w'), stderr=subprocess.STDOUT,
    )
    for _ in range(30):
        try:
            s = socket.socket()
            s.connect(('127.0.0.1', RELAY_PORT))
            s.close()
            return proc
        except OSError:
            time.sleep(0.2)
    raise RuntimeError('verify relay proxy did not start')


def audio_state(page):
    return page.evaluate(
        """() => {
          const a = window.audio;
          if (!a) return { exists: false };
          return { exists: true, paused: a.paused, currentTime: a.currentTime,
                   duration: a.duration, src: (a.src || '').slice(0, 120),
                   volume: a.volume, muted: a.muted };
        }"""
    )


def lyric_state(page):
    return page.evaluate(
        """() => {
          const s = window.originalLyricsState || {};
          const lines = s.lines || [];
          return { count: lines.length, timingSource: s.timingSource || '',
                   first: lines.length ? lines[0].text : '',
                   hasFallback: lines.length ? !!lines[0].fallback : null };
        }"""
    )


def toast_text(page):
    return page.evaluate(
        "() => { const t = document.getElementById('toast'); return t ? (t.textContent || '').trim() : ''; }"
    )


def trial_banner(page):
    return page.evaluate(
        """() => {
          const b = document.getElementById('trial-banner');
          const txt = document.getElementById('trial-text');
          const btn = document.getElementById('trial-login-btn');
          return { shown: !!(b && b.classList.contains('show')),
                   text: txt ? txt.textContent.trim() : '',
                   btnText: btn ? btn.textContent.trim() : '',
                   btnVisible: !!(btn && btn.style.display !== 'none') };
        }"""
    )


def search(page, query):
    page.fill('#search-input', query)
    page.press('#search-input', 'Enter')
    try:
        page.wait_for_selector('#search-results .search-result', state='attached', timeout=30000)
    except Exception as e:
        print('WARN: no results for %r: %s' % (query, e))
        return []
    page.wait_for_timeout(1200)
    return page.evaluate(
        """() => Array.from(document.querySelectorAll('#search-results .search-result'))
               .map(el => ({
                 title: (el.querySelector('.search-result-title')||{}).textContent.trim(),
                 meta: (el.querySelector('.search-result-meta')||{}).textContent.trim(),
                 tag: (el.querySelector('.tag-source')||{}).textContent.trim()
               }))"""
    )


def dismiss_splash(page):
    try:
        page.wait_for_selector('#splash.ready', state='attached', timeout=30000)
        page.click('#splash', timeout=5000)
        print('splash dismissed via click')
    except Exception as e:
        print('splash click failed (%s); calling dismissSplash()' % e)
        page.evaluate("() => { if (typeof dismissSplash === 'function') dismissSplash(); }")
    page.wait_for_function(
        "() => { const s = document.getElementById('splash'); return !s || getComputedStyle(s).display === 'none' || getComputedStyle(s).pointerEvents === 'none'; }",
        timeout=15000,
    )
    page.wait_for_timeout(1200)


def main():
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

        print('== (1) free Netease track: search 晴天')
        results = search(page, '晴天')
        for r in results:
            print('  - [%s] %s | %s' % (r['tag'], r['title'], r['meta']))
        ne = [i for i, r in enumerate(results) if r['tag'] == '网易云']
        free_idx = [i for i in ne if 'VIP' not in results[i]['title']]
        print('netease indexes:', ne, '| non-VIP:', free_idx)
        if free_idx:
            i = free_idx[0]
            print('clicking non-VIP netease result:', results[i]['title'])
            page.locator('#search-results .search-result').nth(i).click()
            page.wait_for_timeout(5000)
            st1 = audio_state(page)
            page.wait_for_timeout(2000)
            st2 = audio_state(page)
            print(json.dumps({
                'title': results[i]['title'],
                'playing': bool(st2.get('exists') and not st2.get('paused')),
                'time_advanced': bool(st2.get('currentTime', 0) > st1.get('currentTime', 0)),
                'audio_src': (st2.get('src') or '')[:110],
                'toast': toast_text(page),
                'lyrics': lyric_state(page),
                'thumb_title': page.evaluate("() => (document.getElementById('thumb-title')||{}).textContent || ''"),
            }, ensure_ascii=False, indent=1))
        else:
            print('FAIL: no non-VIP netease result to test free playback')

        print('== (2) trial offer: search Yesterday')
        results = search(page, 'Yesterday')
        for r in results:
            print('  - [%s] %s | %s' % (r['tag'], r['title'], r['meta']))
        ne = [i for i, r in enumerate(results) if r['tag'] == '网易云']
        vip_idx = [i for i in ne if 'VIP' in results[i]['title']]
        target = vip_idx[0] if vip_idx else (ne[0] if ne else None)
        print('netease indexes:', ne, '| VIP:', vip_idx, '| target:', target)
        if target is not None:
            print('clicking netease result:', results[target]['title'])
            page.locator('#search-results .search-result').nth(target).click()
            page.wait_for_timeout(6000)
            st = audio_state(page)
            tb = trial_banner(page)
            print(json.dumps({
                'title': results[target]['title'],
                'playing': bool(st.get('exists') and not st.get('paused')),
                'toast': toast_text(page),
                'trial_banner': tb,
            }, ensure_ascii=False, indent=1))
            if tb.get('shown') and '试听' in tb.get('btnText', ''):
                print('  -> clicking manual trial button:', tb['btnText'])
                page.click('#trial-login-btn')
                page.wait_for_timeout(5000)
                st2 = audio_state(page)
                page.wait_for_timeout(2000)
                st3 = audio_state(page)
                print(json.dumps({
                    'manual_trial_playing': bool(st3.get('exists') and not st3.get('paused')),
                    'time_advanced': bool(st3.get('currentTime', 0) > st2.get('currentTime', 0)),
                    'src': (st3.get('src') or '')[:110],
                    'trial_banner_after': trial_banner(page),
                    'lyrics': lyric_state(page),
                }, ensure_ascii=False, indent=1))
            else:
                print('NOTE: no trial offer shown (iTunes preview lookup found nothing for this track)')
        else:
            print('FAIL: no netease result for Yesterday')

        print('page/console errors (%d):' % len(errs))
        for e in errs:
            print('  ERR:', e[:400])
        browser.close()
        if relay_proc:
            relay_proc.terminate()


if __name__ == '__main__':
    main()