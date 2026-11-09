# -*- coding: utf-8 -*-
"""StarWave Phase 1 verification (real browser, real network).
Serves web/public via python http.server on 127.0.0.1:4173 and drives it with Playwright.
Checks:
  (a) page load, uncaught JS errors / console errors
  (b) demo track plays (audio.paused == False, currentTime advances) + lyrics loaded
  (c) search '周杰伦' returns real Netease results
  (d) clicking Netease results: plays OR shows '需登录' toast (tries up to 3 tracks)
Usage: python3 scripts/verify-phase1.py [--url http://127.0.0.1:4173/]
The http server must already be running (or start one: python3 -m http.server 4173 -d web/public).
"""
import argparse
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
    """Start the test-only local relay (see scripts/verify-relay-proxy.py)."""
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
    raise RuntimeError('verify relay proxy did not start on 127.0.0.1:%d' % RELAY_PORT)

parser = argparse.ArgumentParser()
parser.add_argument('--url', default='http://127.0.0.1:4173/')
args = parser.parse_args()

report = {'console_errors': [], 'page_errors': [], 'failed_requests': []}


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
        """() => {
          const t = document.getElementById('toast');
          return t ? (t.textContent || '').trim() : '';
        }"""
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


with sync_playwright() as pw:
    # VM egress proxy MITMs TLS with a private CA and Chromium's CONNECT to it
    # fails when credentials are attached. Route the browser through the
    # test-only local relay (no credentials; it forwards CONNECT verbatim)
    # and ignore cert errors (VM MITM only; real users' browsers are unaffected).
    relay_proc = ensure_relay()
    proxy_cfg = {'server': 'http://127.0.0.1:%d' % RELAY_PORT,
                 'bypass': 'localhost,127.0.0.1,::1'}
    browser = pw.chromium.launch(
        args=['--autoplay-policy=no-user-gesture-required',
              '--ignore-certificate-errors'],
        proxy=proxy_cfg,
    )
    page = browser.new_page(viewport={'width': 1280, 'height': 900})
    page.on('console', lambda m: report['console_errors'].append(m.text) if m.type == 'error' else None)
    page.on('pageerror', lambda e: report['page_errors'].append(str(e)))
    page.on('requestfailed', lambda r: report['failed_requests'].append(r.url + ' :: ' + (r.failure or '')))

    print('== (a) load', args.url)
    page.goto(args.url, wait_until='load', timeout=60000)
    page.wait_for_timeout(2000)
    # Dismiss the click-to-enter splash overlay (it intercepts pointer events).
    # It only accepts the click once 'ready'; fall back to its own dismiss fn.
    try:
        page.wait_for_selector('#splash.ready', state='attached', timeout=30000)
        page.click('#splash', timeout=5000)
        print('splash dismissed via click')
    except Exception as e:
        print('splash not ready for click (%s); calling dismissSplash() directly' % e)
        page.evaluate("() => { if (typeof dismissSplash === 'function') dismissSplash(); }")
    page.wait_for_function(
        "() => { const s = document.getElementById('splash'); return !s || getComputedStyle(s).display === 'none' || getComputedStyle(s).pointerEvents === 'none'; }",
        timeout=15000,
    )
    page.wait_for_timeout(1500)
    # Home discover is lazy: trigger the normal path, fall back to a direct call
    # and record which one produced the list.
    page.evaluate("() => { if (typeof loadHomeDiscover === 'function') loadHomeDiscover(true); }")
    try:
        page.wait_for_selector('#home-preview-list .home-preview-track', state='attached', timeout=20000)
        print('home preview rendered via loadHomeDiscover')
    except Exception:
        print('loadHomeDiscover did not render preview; calling loadHomePreviewSongs() directly')
        page.evaluate("() => { if (typeof loadHomePreviewSongs === 'function') loadHomePreviewSongs(); }")
        try:
            page.wait_for_selector('#home-preview-list .home-preview-track', state='attached', timeout=20000)
            print('home preview rendered via direct loadHomePreviewSongs()')
        except Exception as e:
            print('WARN: home preview tracks did not appear:', e)
    print('window.homePreviewSongs:', json.dumps(page.evaluate(
        "() => (window.homePreviewSongs || []).map(s => s.name + '|' + (s.provider || ''))"), ensure_ascii=False))
    try:
        page.wait_for_function("() => window.homePreviewLoaded === true", timeout=30000)
    except Exception:
        print('WARN: homePreviewLoaded never became true')
    preview = page.evaluate(
        """() => Array.from(document.querySelectorAll('#home-preview-list .home-preview-track-title'))
               .map(el => el.textContent.trim())"""
    )
    print('home preview tracks (%d): %s' % (len(preview), json.dumps(preview, ensure_ascii=False)))
    report['preview_titles'] = preview

    print('== (b) demo track play')
    demo_count = page.locator('#home-preview-list .home-preview-track').count()
    demo_result = {}
    if demo_count:
        page.locator('#home-preview-list .home-preview-track').first.click()
        page.wait_for_timeout(4000)
        st1 = audio_state(page)
        page.wait_for_timeout(2000)
        st2 = audio_state(page)
        demo_result = {
            'title_clicked': preview[0] if preview else '',
            'audio_t0': st1, 'audio_t1': st2,
            'playing': bool(st2.get('exists') and not st2.get('paused')),
            'time_advanced': bool(st2.get('currentTime', 0) > st1.get('currentTime', 0)),
            'lyrics': lyric_state(page),
            'thumb_title': page.evaluate("() => (document.getElementById('thumb-title')||{}).textContent || ''"),
        }
        print(json.dumps(demo_result, ensure_ascii=False, indent=1))
    else:
        print('FAIL: no demo track button found')
    report['demo'] = demo_result

    print("== (c) search '周杰伦'")
    page.fill('#search-input', '周杰伦')
    page.press('#search-input', 'Enter')
    try:
        page.wait_for_selector('#search-results .search-result', state='attached', timeout=30000)
    except Exception as e:
        print('WARN: no search results appeared:', e)
    print('neteaseWebSearchError:', repr(page.evaluate("() => window.neteaseWebSearchError || ''")))
    page.wait_for_timeout(1000)
    results = page.evaluate(
        """() => Array.from(document.querySelectorAll('#search-results .search-result'))
               .map(el => ({
                 title: (el.querySelector('.search-result-title')||{}).textContent.trim(),
                 meta: (el.querySelector('.search-result-meta')||{}).textContent.trim(),
                 tag: (el.querySelector('.tag-source')||{}).textContent.trim()
               }))"""
    )
    print('search results (%d):' % len(results))
    for r in results:
        print('  - [%s] %s | %s' % (r['tag'], r['title'], r['meta']))
    report['search_results'] = results
    netease_idx = [i for i, r in enumerate(results) if r['tag'] == '网易云']
    print('netease-web results at indexes:', netease_idx)

    print('== (d) play netease results (up to 3)')
    trials = []
    for n, i in enumerate(netease_idx[:3]):
        # re-resolve the row each time via locator (list re-renders between clicks)
        row_count = page.locator('#search-results .search-result').count()
        if i >= row_count:
            trials.append({'index': i, 'note': 'row gone after previous click'})
            break
        title = results[i]['title']
        page.locator('#search-results .search-result').nth(i).click()
        page.wait_for_timeout(5000)
        st1 = audio_state(page)
        page.wait_for_timeout(2000)
        st2 = audio_state(page)
        trials.append({
            'index': i, 'title': title,
            'playing': bool(st2.get('exists') and not st2.get('paused')),
            'time_advanced': bool(st2.get('currentTime', 0) > st1.get('currentTime', 0)),
            'audio_src': (st2.get('src') or '')[:110],
            'toast': toast_text(page),
            'trial_banner': trial_banner(page),
            'lyrics': lyric_state(page),
            'thumb_title': page.evaluate("() => (document.getElementById('thumb-title')||{}).textContent || ''"),
        })
        print(json.dumps(trials[-1], ensure_ascii=False, indent=1))
        # if a trial offer appeared, try the manual 30s trial button once
        tb = trials[-1]['trial_banner']
        if tb.get('shown') and '试听' in tb.get('btnText', ''):
            print('  -> clicking manual trial button:', tb['btnText'])
            page.click('#trial-login-btn')
            page.wait_for_timeout(5000)
            st = audio_state(page)
            trials[-1]['manual_trial'] = {
                'playing': bool(st.get('exists') and not st.get('paused')),
                'src': (st.get('src') or '')[:110],
                'trial_banner_after': trial_banner(page),
            }
            print(json.dumps(trials[-1]['manual_trial'], ensure_ascii=False, indent=1))
        # re-run the search for the next trial (input was cleared by playSearchResult)
        if n < len(netease_idx[:3]) - 1:
            page.fill('#search-input', '周杰伦')
            page.press('#search-input', 'Enter')
            try:
                page.wait_for_selector('#search-results .search-result', state='attached', timeout=30000)
            except Exception:
                pass
            page.wait_for_timeout(800)
            results = page.evaluate(
                """() => Array.from(document.querySelectorAll('#search-results .search-result'))
                       .map(el => ({
                         title: (el.querySelector('.search-result-title')||{}).textContent.trim(),
                         meta: (el.querySelector('.search-result-meta')||{}).textContent.trim(),
                         tag: (el.querySelector('.tag-source')||{}).textContent.trim()
                       }))"""
            )
            netease_idx = [j for j, r in enumerate(results) if r['tag'] == '网易云']
    report['netease_trials'] = trials

    print('== (a) console / page errors')
    print('console errors (%d):' % len(report['console_errors']))
    for e in report['console_errors']:
        print('  CONSOLE-ERROR:', e[:500])
    print('page errors (%d):' % len(report['page_errors']))
    for e in report['page_errors']:
        print('  PAGE-ERROR:', e[:500])
    print('failed requests (%d):' % len(report['failed_requests']))
    for e in report['failed_requests']:
        print('  REQ-FAIL:', e[:300])
    browser.close()
    if relay_proc:
        relay_proc.terminate()

with open('/tmp/sw-phase1-verify-report.json', 'w', encoding='utf-8') as f:
    json.dump(report, f, ensure_ascii=False, indent=2)
print('report written to /tmp/sw-phase1-verify-report.json')
