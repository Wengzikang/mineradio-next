# -*- coding: utf-8 -*-
"""StarWave Phase 6 LIVE verification (real browser, real network, live site only).
Drives the deployed GitHub Pages site https://wengzikang.github.io/mineradio-next/
with Playwright Chromium through the test relay 127.0.0.1:18082.
READ-ONLY: verifies only, never edits project code, never logs in, never calls
decrypt/download endpoints, never fabricates mock data.
Does NOT restart the relay and does NOT start any local static server: if the
relay port is closed the run aborts immediately and reports the failure.
Two runs: desktop 1280x800, mobile 390x844 (is_mobile + touch).
JSON logs: /tmp/sw-live-desktop.json, /tmp/sw-live-mobile.json
Usage:
  ~/workspace/.venv-playwright/bin/python scripts/verify-live.py
"""
import asyncio
import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.parse

from playwright.sync_api import sync_playwright

RELAY_PORT = 18082
CDP_PORT = 9222
RELAY_LOG = '/tmp/sw-relay.log'
BASE_URL = 'https://wengzikang.github.io/mineradio-next/'
DESKTOP_JSON = '/tmp/sw-live-desktop.json'
MOBILE_JSON = '/tmp/sw-live-mobile.json'
LOCAL_MP3 = '/tmp/sw-local-test.mp3'

BAD_HOSTS = ('qishui', 'douyin', 'douyinvod')


def _port_open(port):
    s = socket.socket()
    try:
        s.connect(('127.0.0.1', port))
        s.close()
        return True
    except OSError:
        return False


def _relay_log_lines():
    try:
        with open(RELAY_LOG, 'rb') as f:
            return sum(1 for _ in f)
    except OSError:
        return None


def _relay_delta_bad(start_line, end_line):
    """Count delta lines in relay log mentioning forbidden hosts."""
    bad = []
    total = 0
    try:
        with open(RELAY_LOG, 'rb') as f:
            for i, raw in enumerate(f):
                if start_line is not None and i < start_line:
                    continue
                if end_line is not None and i >= end_line:
                    break
                total += 1
                try:
                    line = raw.decode('utf-8', 'replace')
                except Exception:
                    continue
                low = line.lower()
                if any(h in low for h in BAD_HOSTS):
                    bad.append(line.strip()[:200])
    except OSError as e:
        return {'error': str(e), 'bad_count': None, 'delta_lines': None, 'bad_lines': []}
    return {'bad_count': len(bad), 'delta_lines': total, 'bad_lines': bad}


def check(report, name, ok, detail=None):
    report['checks'][name] = {'ok': bool(ok), 'detail': detail}
    print(('PASS ' if ok else 'FAIL ') + name + ((' :: ' + json.dumps(detail, ensure_ascii=False)[:700]) if detail is not None else ''))
    return bool(ok)


async def _cdp_double_tap_async(x, y, url_sub, gap=0.15):
    """Two real touch taps via CDP Input.dispatchTouchEvent, fire-and-forget.

    The sync API's CDP send waits ~300-600ms per ack on this heavy page, which
    stretches two taps to ~700ms apart in event time, past Chromium's
    ~300-400ms double-click window, so dblclick never fires (measured on the
    local build). Fire-and-forget keeps the real event gap at the intended
    ~150ms, matching a human double-tap. No event timestamp is forged: the
    browser stamps the events itself.
    """
    from playwright.async_api import async_playwright
    async with async_playwright() as apw:
        browser = await apw.chromium.connect_over_cdp('http://127.0.0.1:%d' % CDP_PORT)
        page = None
        for ctx in browser.contexts:
            for pg in ctx.pages:
                if url_sub in pg.url:
                    page = pg
        if page is None:
            raise RuntimeError('CDP attach: page not found for %s' % url_sub)
        cdp = await page.context.new_cdp_session(page)

        async def tap():
            asyncio.create_task(cdp.send('Input.dispatchTouchEvent',
                                         {'type': 'touchStart', 'touchPoints': [{'x': x, 'y': y, 'id': 1}]}))
            await asyncio.sleep(0.03)
            asyncio.create_task(cdp.send('Input.dispatchTouchEvent',
                                         {'type': 'touchEnd', 'touchPoints': []}))
        await tap()
        await asyncio.sleep(gap)
        await tap()
        await asyncio.sleep(0.8)


def _cdp_real_double_tap(x, y, url_sub):
    """Run _cdp_double_tap_async in a worker thread.

    asyncio.run() cannot run inside the sync Playwright event loop, so the
    async CDP attach runs on its own thread and the caller blocks on join.
    Raises on failure; the caller records the method honestly.
    """
    errs = []

    def _run():
        try:
            asyncio.run(_cdp_double_tap_async(x, y, url_sub))
        except Exception as e:  # noqa: BLE001 - surfaced to caller via errs
            errs.append(str(e))

    th = threading.Thread(target=_run, daemon=True)
    th.start()
    th.join(timeout=30)
    if errs:
        raise RuntimeError(errs[0])
    if th.is_alive():
        raise RuntimeError('CDP double-tap thread timed out')


def dismiss_splash(page):
    page.wait_for_timeout(1200)
    try:
        page.wait_for_selector('#splash.ready', state='attached', timeout=30000)
        page.click('#splash', timeout=5000)
    except Exception:
        page.evaluate("() => { if (typeof dismissSplash === 'function') dismissSplash(); }")
    page.wait_for_timeout(1200)


def audio_state(page):
    return page.evaluate(
        "() => { const a = window.audio; if (!a) return { exists: false };"
        " return { exists: true, paused: a.paused, ct: Math.round(a.currentTime * 100) / 100,"
        " dur: Math.round((a.duration || 0) * 100) / 100, src: (a.src || '').slice(0, 120) }; }")


def prepare_test_files():
    """(Re)generate the deterministic fixture mp3 in /tmp (same file as
    verify-phase3.py; the demo songs were deleted 2026-11-10 at Ma's order,
    so live playback checks use this fixture instead)."""
    r = subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
                        '-f', 'lavfi', '-i', 'anoisesrc=color=white:duration=30',
                        '-codec:a', 'libmp3lame', '-q:a', '4', LOCAL_MP3],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError('ffmpeg failed to generate LOCAL_MP3: ' + (r.stderr or ''))


def play_fixture(page):
    """Play the generated MP3 fixture via the real Phase 3 queue (demo songs
    were deleted 2026-11-10 at Ma's order). Playing a local file with no
    cached beat map opens the local-beat analysis modal, so close it (it
    would block later pointer actions). Returns audio samples."""
    page.set_input_files('#file-input', LOCAL_MP3)
    page.wait_for_timeout(4000)
    page.evaluate("() => { try { if (typeof closeLocalBeatModal === 'function') closeLocalBeatModal(); } catch (e) {} }")
    page.wait_for_timeout(500)
    modal_open = page.evaluate("() => { const m = document.getElementById('local-beat-modal'); return !!(m && m.classList.contains('show')); }")
    if modal_open:
        page.keyboard.press('Escape')
        page.wait_for_timeout(500)
    song = page.evaluate("() => { const s = window.currentLocalSong || (window.playQueue && window.playQueue[0]) || null; return s ? { name: s.name, id: s.id, localKey: s.localKey, publicAudioUrl: s.publicAudioUrl, previewUrl: s.previewUrl, provider: s.provider, type: s.type } : null; }")
    page.evaluate("(song) => { if (!song) return; window.playQueue = [song]; window.currentIdx = 0; return playQueueAt(0, { manual: true }); }", song)
    page.wait_for_timeout(3000)
    t0 = audio_state(page)
    page.wait_for_timeout(3000)
    t1 = audio_state(page)
    advance = None
    if t0.get('ct') is not None and t1.get('ct') is not None:
        advance = round(t1['ct'] - t0['ct'], 2)
    return {'played_index': 0, 'played_name': song['name'] if song else None,
            'song': song, 't0': t0, 't1': t1, 'advance_sec': advance}


def search_jay(page):
    page.fill('#search-input', '周杰伦')
    page.press('#search-input', 'Enter')
    try:
        page.wait_for_selector('#search-results .search-result', state='attached', timeout=45000)
    except Exception:
        pass
    page.wait_for_timeout(2500)
    rows = page.evaluate(
        "() => Array.from(document.querySelectorAll('#search-results .search-result')).map(el => ({"
        " title: (el.querySelector('.search-result-title')||{}).textContent.trim().slice(0, 40),"
        " tag: (el.querySelector('.tag-source')||{}).textContent.trim(),"
        " tagClass: (el.querySelector('.tag-source')||{}).className || '',"
        " meta: (el.querySelector('.search-result-meta')||{}).textContent.trim().slice(0, 60) }))")
    by_tag = {}
    for r in rows:
        key = (r.get('tag') or '?').upper()
        by_tag[key] = by_tag.get(key, 0) + 1
    return {'total': len(rows), 'by_tag': by_tag, 'rows_sample': rows[:8]}


def spotify_auth_format(page):
    """Format-only check: buildAuthUrl() returns the authorize URL string.
    No popup opened, no navigation, no credentials, no code exchange."""
    url = page.evaluate("async () => window.starwaveSpotify.buildAuthUrl()")
    parsed = urllib.parse.urlparse(url or '')
    qs = urllib.parse.parse_qs(parsed.query)
    got = {'host': parsed.netloc, 'path': parsed.path,
           'client_id': qs.get('client_id', [''])[0],
           'redirect_uri': qs.get('redirect_uri', [''])[0],
           'response_type': qs.get('response_type', [''])[0],
           'code_challenge_method': qs.get('code_challenge_method', [''])[0],
           'has_code_challenge': bool(qs.get('code_challenge', [''])[0]),
           'has_state': bool(qs.get('state', [''])[0])}
    ok = (got['host'] == 'accounts.spotify.com' and got['path'] == '/authorize'
          and got['client_id'] == '35e5a591884f42d398ab298ab79f16cb'
          and got['redirect_uri'] == 'https://wengzikang.github.io/mineradio-next/'
          and got['response_type'] == 'code' and got['code_challenge_method'] == 'S256'
          and got['has_code_challenge'] and got['has_state'])
    return ok, got


def run_desktop(browser):
    report = {'run': 'desktop', 'base_url': BASE_URL, 'viewport': {'width': 1280, 'height': 800},
              'console_errors': [], 'page_errors': [], 'failed_requests': [],
              'request_urls': [], 'checks': {}}
    failures = 0
    relay_start = _relay_log_lines()
    page = browser.new_page(viewport={'width': 1280, 'height': 800})
    page.on('console', lambda m: report['console_errors'].append(m.text) if m.type == 'error' else None)
    page.on('pageerror', lambda e: report['page_errors'].append(str(e)))
    page.on('requestfailed', lambda r: report['failed_requests'].append(r.url[:160] + ' :: ' + str(r.failure)[:120]))
    page.on('request', lambda r: report['request_urls'].append(r.url))
    page.goto(BASE_URL, wait_until='load', timeout=60000)
    page.wait_for_timeout(3000)
    dismiss_splash(page)
    load = {'title': page.title(), 'url': page.url,
            'console_errors': len(report['console_errors']), 'page_errors': len(report['page_errors']),
            'failed_requests': len(report['failed_requests'])}
    if not check(report, 'load.page_ok', load['title'] == 'StarWave' and load['page_errors'] == 0, load):
        failures += 1

    p4b = page.evaluate("() => { const m = window.starwavePhase4b; return m ? { version: m.version, available: m.available } : null; }")
    if not check(report, 'load.phase4b_available', bool(p4b and p4b.get('available')), p4b):
        failures += 1
    p3 = page.evaluate("() => !!window.starwavePhase3")
    p4a = page.evaluate("() => !!window.starwavePhase4a")
    if not check(report, 'load.phase3_present_phase4a_absent', bool(p3 and not p4a), {'phase3': p3, 'phase4a': p4a}):
        failures += 1

    demo = play_fixture(page)
    ok_demo = bool(demo['t1'].get('exists') and not demo['t1'].get('paused')
                  and demo['advance_sec'] is not None and demo['advance_sec'] > 0)
    if not check(report, 'play.fixture_advances', ok_demo, demo):
        failures += 1

    srch = search_jay(page)
    ne = sum(v for k, v in srch['by_tag'].items() if '网易' in k or 'NETEASE' in k)
    au = sum(v for k, v in srch['by_tag'].items() if 'AUDIUS' in k)
    if not check(report, 'search.jay_chou', bool(srch['total'] >= 1 and (ne + au) >= 1),
                 {'total': srch['total'], 'by_tag': srch['by_tag'], 'netease': ne, 'audius': au,
                  'sample': srch['rows_sample']}):
        failures += 1

    page.evaluate("() => window.starwavePhase4b.openPanel('dj')")
    page.wait_for_timeout(800)
    # Seed the DJ pool with the fixture (demo songs deleted 2026-11-10: the
    # cold-start pool is empty on the live site, so generate() returns 0).
    page.evaluate("""(song) => {
      if (!song) return { seeded: 0 };
      const mk = (n) => Object.assign({}, song, { id: (song.localKey || song.id || 'fixture') + '#dj' + n, localKey: (song.localKey || song.id || 'fixture') + '#dj' + n, name: (song.name || 'fixture') + ' (DJ' + n + ')' });
      const songs = [mk(1), mk(2), mk(3)];
      if (typeof homeDiscoverState !== 'undefined') homeDiscoverState.songs = songs;
      return { seeded: songs.length };
    }""", demo.get('song'))
    dj = page.evaluate("async () => { const d = await window.starwavePhase4b.dj.generate({}); return { songs: d.songs.length, line: d.line, by: d.generatedBy, names: d.songs.slice(0, 6).map(s => s.name), hasDemo: d.songs.some(s => s.provider === 'demo') }; }")
    if not check(report, 'dj.generate_seeded', bool(dj and dj['songs'] >= 3 and dj['by'] == '规则生成，非大模型' and not dj['hasDemo']), dj):
        failures += 1
    page.evaluate("() => window.starwavePhase4b.dj.play()")
    page.wait_for_timeout(3000)
    d0 = audio_state(page)
    page.wait_for_timeout(3000)
    d1 = audio_state(page)
    dj_adv = round(d1['ct'] - d0['ct'], 2) if d0.get('ct') is not None and d1.get('ct') is not None else None
    ok_dj_play = bool(d1.get('exists') and not d1.get('paused') and dj_adv is not None and dj_adv > 0)
    if not check(report, 'dj.play_advances', ok_dj_play, {'t0': d0, 't1': d1, 'advance_sec': dj_adv}):
        failures += 1

    rec = page.evaluate("async () => { const r = await window.starwavePhase4b.recommend.hybrid({}); return { songs: r.songs.length, platform: r.platformCount, platformReason: r.platformReason, local: r.localCount, coldStart: r.coldStart, names: r.songs.slice(0, 3).map(s => s.name) }; }")
    if not check(report, 'recommend.hybrid_has_results', bool(rec and rec['songs'] >= 1), rec):
        failures += 1

    ok_sp, sp = spotify_auth_format(page)
    if not check(report, 'spotify.auth_url_format_only', ok_sp, sp):
        failures += 1

    relay_end = _relay_log_lines()
    relay = _relay_delta_bad(relay_start, relay_end)
    page_reqs_bad = [u for u in report['request_urls'] if any(h in u.lower() for h in BAD_HOSTS)]
    relay['page_request_urls_total'] = len(report['request_urls'])
    relay['page_request_bad_count'] = len(page_reqs_bad)
    relay['page_request_bad_urls'] = page_reqs_bad[:10]
    relay['relay_log_start_line'] = relay_start
    relay['relay_log_end_line'] = relay_end
    if not check(report, 'zero_qishui_douyin_requests', relay['bad_count'] == 0 and relay['page_request_bad_count'] == 0, relay):
        failures += 1

    report['failures'] = failures
    report['relay'] = relay
    with open(DESKTOP_JSON, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print('DESKTOP failures=%d console_errors=%d page_errors=%d failed_requests=%d requests=%d' % (
        failures, len(report['console_errors']), len(report['page_errors']),
        len(report['failed_requests']), len(report['request_urls'])))
    page.close()
    return failures, report


def run_mobile(browser):
    report = {'run': 'mobile', 'base_url': BASE_URL, 'viewport': {'width': 390, 'height': 844},
              'console_errors': [], 'page_errors': [], 'failed_requests': [],
              'request_urls': [], 'checks': {}}
    failures = 0
    relay_start = _relay_log_lines()
    ctx = browser.new_context(viewport={'width': 390, 'height': 844}, is_mobile=True, has_touch=True,
                              user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1')
    page = ctx.new_page()
    page.on('console', lambda m: report['console_errors'].append(m.text) if m.type == 'error' else None)
    page.on('pageerror', lambda e: report['page_errors'].append(str(e)))
    page.on('requestfailed', lambda r: report['failed_requests'].append(r.url[:160] + ' :: ' + str(r.failure)[:120]))
    page.on('request', lambda r: report['request_urls'].append(r.url))
    page.goto(BASE_URL, wait_until='load', timeout=60000)
    page.wait_for_timeout(3000)
    dismiss_splash(page)
    load = {'title': page.title(), 'url': page.url,
            'console_errors': len(report['console_errors']), 'page_errors': len(report['page_errors']),
            'failed_requests': len(report['failed_requests'])}
    if not check(report, 'load.page_ok_no_pageerror', load['title'] == 'StarWave' and load['page_errors'] == 0, load):
        failures += 1

    shelf = page.evaluate("() => window.starwavePhase4b.mobile.portraitShelf()")
    if not check(report, 'mobile.portrait_shelf', bool(shelf and shelf.get('portrait') is True), shelf):
        failures += 1

    demo = play_fixture(page)
    ok_demo = bool(demo['t1'].get('exists') and not demo['t1'].get('paused')
                  and demo['advance_sec'] is not None and demo['advance_sec'] > 0)
    if not check(report, 'play.fixture_advances', ok_demo, demo):
        failures += 1

    # double-tap like 0 -> 1 on the cover (fresh profile, favorites start empty).
    # Target is #thumb-cover: #control-cover stays display:none at <=720px by
    # design, so it can never be the real-touch target on mobile; #thumb-cover
    # (inside #thumb-wrap.visible) is the reachable one after the CSS fix.
    before = page.evaluate("() => window.starwavePhase3.listFavorites().length")
    method = None
    box = page.evaluate("() => { const el = document.getElementById('thumb-cover'); if (!el) return null; const r = el.getBoundingClientRect(); return { x: r.x + r.width / 2, y: r.y + r.height / 2 }; }")
    after = before
    if box:
        try:
            # Real double-tap via CDP (see _cdp_real_double_tap): sync
            # touchscreen.tap waits ~300-600ms per tap ack on this page, which
            # pushes the two taps past the double-click window and can never
            # fire dblclick here, even when the feature works.
            _cdp_real_double_tap(box['x'], box['y'], BASE_URL)
            method = 'cdp_real_double_tap'
        except Exception as e:
            method = 'cdp_double_tap_failed: %s' % e
        page.wait_for_timeout(800)
        after = page.evaluate("() => window.starwavePhase3.listFavorites().length")
    if after == before:
        # fallback: Playwright dblclick, record the method honestly
        try:
            page.dblclick('#thumb-cover', timeout=5000)
            method = (method or '') + ' + dblclick_fallback'
            page.wait_for_timeout(800)
            after = page.evaluate("() => window.starwavePhase3.listFavorites().length")
        except Exception as e:
            method = (method or '') + ' + dblclick_failed: %s' % e
    if not check(report, 'mobile.dblclick_like_0_to_1', before == 0 and after == 1,
                 {'before': before, 'after': after, 'method': method}):
        failures += 1

    # long-press menu via REAL touch (CDP Input.dispatchTouchEvent, touchStart
    # -> hold 750ms -> touchEnd). The old check dispatched a synthetic
    # TouchEvent straight to the element, which fires handlers even on a
    # display:none target and false-passed; a real touch only reaches a
    # visible, hittable target, so this cannot pass on a hidden element.
    lp_box = page.evaluate("() => { const el = document.getElementById('thumb-cover'); if (!el) return null; const r = el.getBoundingClientRect(); return { x: r.x + r.width / 2, y: r.y + r.height / 2, w: r.width, h: r.height }; }")
    lp = None
    if lp_box and lp_box.get('w', 0) > 0:
        try:
            cdp = ctx.new_cdp_session(page)
            cdp.send('Input.dispatchTouchEvent', {'type': 'touchStart', 'touchPoints': [{'x': lp_box['x'], 'y': lp_box['y'], 'id': 1}]})
            page.wait_for_timeout(750)
            cdp.send('Input.dispatchTouchEvent', {'type': 'touchEnd', 'touchPoints': []})
            page.wait_for_timeout(500)
            lp = {'menuShown': bool(page.evaluate("() => { const m = document.getElementById('sw4b-lp-menu'); return !!(m && m.style.display === 'block'); }"))}
        except Exception as e:
            lp = {'error': str(e)[:300]}
    else:
        lp = {'noVisibleTarget': True, 'box': lp_box}
    if not check(report, 'mobile.longpress_menu', bool(lp and lp.get('menuShown')), lp):
        failures += 1

    relay_end = _relay_log_lines()
    relay = _relay_delta_bad(relay_start, relay_end)
    page_reqs_bad = [u for u in report['request_urls'] if any(h in u.lower() for h in BAD_HOSTS)]
    relay['page_request_urls_total'] = len(report['request_urls'])
    relay['page_request_bad_count'] = len(page_reqs_bad)
    relay['page_request_bad_urls'] = page_reqs_bad[:10]
    relay['relay_log_start_line'] = relay_start
    relay['relay_log_end_line'] = relay_end
    if not check(report, 'zero_qishui_douyin_requests', relay['bad_count'] == 0 and relay['page_request_bad_count'] == 0, relay):
        failures += 1

    report['failures'] = failures
    report['relay'] = relay
    with open(MOBILE_JSON, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print('MOBILE failures=%d console_errors=%d page_errors=%d failed_requests=%d requests=%d' % (
        failures, len(report['console_errors']), len(report['page_errors']),
        len(report['failed_requests']), len(report['request_urls'])))
    ctx.close()
    return failures, report


def main():
    prepare_test_files()
    if not _port_open(RELAY_PORT):
        print('ABORT: relay 127.0.0.1:%d not listening; per task rules, do not restart it.' % RELAY_PORT)
        return 2
    total_failures = 0
    with sync_playwright() as pw:
        proxy_cfg = {'server': 'http://127.0.0.1:%d' % RELAY_PORT,
                     'bypass': 'localhost,127.0.0.1,::1'}
        browser = pw.chromium.launch(
            args=['--autoplay-policy=no-user-gesture-required', '--ignore-certificate-errors',
                  '--remote-debugging-port=%d' % CDP_PORT],
            proxy=proxy_cfg)
        try:
            f1, _ = run_desktop(browser)
            total_failures += f1
            f2, _ = run_mobile(browser)
            total_failures += f2
        finally:
            browser.close()
    print('TOTAL failures=%d' % total_failures)
    return 0 if total_failures == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
