# -*- coding: utf-8 -*-
"""StarWave Phase 5A verification (real browser, real network).
Serves web/public via scripts/range-http-server.py on 127.0.0.1:4174 and
drives it with Playwright (relay 18082 for external hosts), same harness
as scripts/verify-phase4b.py.
Covers Phase 5A items:
  P6 search pagination: type a query, page 1 renders, [data-search-load-more]
     appends the next NetEase page with no duplicate rows, offset advances
  P1 six new visual presets (renamed): presetMeta 7 -> 13, 13 cards in the
     grid, all free (no premiumVisual), no upstream names/authors in preset
     data or card text, each new preset selectable (fx.preset + uPreset)
  P9 toolkit (only confirmed gaps): storage section + probe present and
     working; lyric-color controls + ColorLab present already (skip evidence)
  + light regression: demo songs removed, phase4a absent, login module
    untouched, playlist load-more controls untouched, 0 console/page/first-
    party failed requests (two documented pre-existing carve-outs: the
    /api/update/latest 404 from the update poller with no static backend,
    and third-party cover-image failures — see error-budget section below).
Usage:
  ~/workspace/.venv-playwright/bin/python scripts/verify-phase5a.py [--smoke]
--smoke: load + preset count + one search page only (no load-more click).
Report JSON: /tmp/sw-phase5a-verify-report.json
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
RANGE_PORT = 4174
RANGE_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'range-http-server.py')
BASE_URL = 'http://127.0.0.1:4174/'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPORT_PATH = '/tmp/sw-phase5a-verify-report.json'

report = {'console_errors': [], 'page_errors': [], 'failed_requests': [], 'checks': {}}

NEW_PRESET_NAMES = ['声波丘陵', '霓光涟漪', '曜环', '霓雨', '光蝶', '潮汐荧光']
BANNED_LITERALS = ['音域回响', '月蚀圣环', '雨幕霓虹', '折光蝶群', '深海绽放',
                   'Sonic-Topography', 'Wallpaper Engine', 'ECLIPSE HALO',
                   'NEON DRIZZLE', 'PRISM FLOCK', 'ABYSSAL BLOOM',
                   'Ajin', 'CmzYa', 'premiumVisual']


def _port_open(port):
    s = socket.socket()
    try:
        s.connect(('127.0.0.1', port))
        s.close()
        return True
    except OSError:
        return False


def _kill_relays():
    pat = 'verify' + '-relay-proxy.py'
    subprocess.run(['pkill', '-f', pat], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(20):
        if not _port_open(RELAY_PORT):
            return
        time.sleep(0.2)


def _relay_probe_ok():
    try:
        import urllib.request
        proxy = urllib.request.ProxyHandler({'https': 'http://127.0.0.1:%d' % RELAY_PORT})
        opener = urllib.request.build_opener(proxy)
        with opener.open('https://itunes.apple.com/search?term=ping&limit=1', timeout=10) as r:
            return r.status == 200 and len(r.read()) > 10
    except Exception:
        return False


def ensure_relay():
    if _port_open(RELAY_PORT) and _relay_probe_ok():
        return None
    if _port_open(RELAY_PORT):
        print('relay port open but probe failed -> restarting relay')
        _kill_relays()
    proc = subprocess.Popen([sys.executable, RELAY_SCRIPT],
                            stdout=open('/tmp/sw-relay.log', 'w'), stderr=subprocess.STDOUT)
    for _ in range(30):
        if _port_open(RELAY_PORT) and _relay_probe_ok():
            return proc
        time.sleep(0.5)
    raise RuntimeError('relay did not start / probe failed')


def ensure_range_server():
    if _port_open(RANGE_PORT):
        return None
    proc = subprocess.Popen(
        [sys.executable, RANGE_SCRIPT, str(RANGE_PORT)],
        stdout=open('/tmp/sw-range.log', 'w'), stderr=subprocess.STDOUT)
    for _ in range(30):
        if _port_open(RELAY_PORT):
            return proc
        time.sleep(0.2)
    raise RuntimeError('range server did not start')


def check(name, ok, detail=None):
    report['checks'][name] = {'ok': bool(ok), 'detail': detail}
    print(('PASS ' if ok else 'FAIL ') + name + ((' :: ' + json.dumps(detail, ensure_ascii=False)[:600]) if detail is not None else ''))
    return bool(ok)


def dismiss_splash(page):
    page.wait_for_timeout(1200)
    try:
        page.wait_for_selector('#splash.ready', state='attached', timeout=30000)
        page.click('#splash', timeout=5000)
    except Exception:
        page.evaluate("() => { if (typeof dismissSplash === 'function') dismissSplash(); }")
    page.wait_for_timeout(1200)


def search_row_keys(page):
    return page.evaluate(
        "() => Array.from(document.querySelectorAll('#search-results .search-result'))"
        ".map(el => (el.querySelector('.search-result-title') || {}).textContent + '|' +"
        " ((el.querySelector('.search-result-meta') || {}).textContent || ''))")


def main():
    smoke = '--smoke' in sys.argv
    relay_proc = ensure_relay()
    range_proc = ensure_range_server()
    failures = 0

    with sync_playwright() as pw:
        proxy_cfg = {'server': 'http://127.0.0.1:%d' % RELAY_PORT,
                     'bypass': 'localhost,127.0.0.1,::1'}
        browser = pw.chromium.launch(
            args=['--autoplay-policy=no-user-gesture-required', '--ignore-certificate-errors'],
            proxy=proxy_cfg)
        page = browser.new_page(viewport={'width': 1280, 'height': 800})
        page.on('console', lambda m: report['console_errors'].append(m.text) if m.type == 'error' else None)
        page.on('pageerror', lambda e: report['page_errors'].append(str(e)))
        page.on('requestfailed', lambda r: report['failed_requests'].append(r.url[:160] + ' :: ' + str(r.failure)[:120]))
        page.goto(BASE_URL, wait_until='load', timeout=60000)
        page.wait_for_timeout(3000)
        dismiss_splash(page)

        # ---- load ----
        p5 = page.evaluate("() => { const m = window.starwavePhase5; return m ? { version: m.version, available: m.available, presetsRegistered: m.presetsRegistered } : null; }")
        if not check('load.phase5_present', bool(p5 and p5.get('available') and p5.get('presetsRegistered')), p5):
            failures += 1

        # ---- P1: presets ----
        presets = page.evaluate(
            "() => ({ metaCount: (typeof presetMeta !== 'undefined' ? presetMeta.length : -1),"
            " names: (typeof presetMeta !== 'undefined' ? presetMeta.map(p => p.name) : []),"
            " cards: document.querySelectorAll('#preset-grid .preset-card').length,"
            " premiumCards: document.querySelectorAll('.preset-card-premium').length,"
            " premiumFlags: (typeof presetMeta !== 'undefined' ? presetMeta.filter(p => ('premiumVisual' in p)).length : -1),"
            " cardText: (document.getElementById('preset-grid') || {}).innerText || '' })")
        p1_count_ok = presets['metaCount'] == 13 and presets['cards'] == 13
        if not check('p1.preset_count_13', p1_count_ok, {'meta': presets['metaCount'], 'cards': presets['cards']}):
            failures += 1
        p1_names_ok = all(n in (presets['names'] or []) for n in NEW_PRESET_NAMES)
        if not check('p1.new_names_present', p1_names_ok, {'names': presets['names']}):
            failures += 1
        banned_hits = [b for b in BANNED_LITERALS
                       if b in json.dumps(presets['names'], ensure_ascii=False)
                       or b in (presets['cardText'] or '')]
        if not check('p1.no_upstream_names', not banned_hits, {'hits': banned_hits}):
            failures += 1
        if not check('p1.all_free_no_premium', presets['premiumCards'] == 0 and presets['premiumFlags'] == 0,
                     {'premiumCards': presets['premiumCards'], 'premiumFlags': presets['premiumFlags']}):
            failures += 1
        # each new preset selectable: fx.preset + uniforms.uPreset follow
        sel = page.evaluate(
            "() => { const out = []; for (let i = 7; i <= 12; i++) {"
            " try { setPreset(i, { silent: true, noSave: true, skipTransition: true });"
            " out.push({ i: i, fx: (typeof fx !== 'undefined' ? fx.preset : -1),"
            " u: (typeof uniforms !== 'undefined' && uniforms.uPreset ? uniforms.uPreset.value : -1) }); }"
            " catch (e) { out.push({ i: i, err: String(e) }); } }"
            " setPreset(0, { silent: true, noSave: true, skipTransition: true }); return out; }")
        sel_ok = all(s.get('fx') == s.get('i') and s.get('u') == s.get('i') for s in sel)
        if not check('p1.new_presets_selectable', sel_ok, sel):
            failures += 1

        # ---- P9: only confirmed gaps present ----
        storage = page.evaluate(
            "async () => { const el = document.getElementById('sw5-storage');"
            " const val = (document.getElementById('sw5-storage-value') || {}).textContent || '';"
            " let est = null; try { est = await window.starwavePhase5.storage.refresh(); } catch (e) { est = { err: String(e) }; }"
            " return { section: !!el, valueText: val, est: est }; }")
        if not check('p9.storage_section_working', bool(storage['section'] and isinstance(storage.get('est'), dict)
                                                       and storage['est'].get('usage', -1) >= 0), storage):
            failures += 1
        probe = page.evaluate(
            "() => { const p = window.starwavePerfProbe; if (!p) return null;"
            " p.mark('verify5a-probe', 1.5); const s = p.summary();"
            " return { version: p.version, hasMark: typeof p.mark === 'function',"
            " hasMeasure: typeof p.measure === 'function', hasCount: typeof p.count === 'function',"
            " recorded: !!(s.metrics && s.metrics['verify5a-probe'] && s.metrics['verify5a-probe'].count === 1) }; }")
        if not check('p9.perf_probe_working', bool(probe and probe.get('recorded')), probe):
            failures += 1
        # skip evidence: lyric-color controls + ColorLab already existed
        skip_ev = page.evaluate(
            "() => ({ lyricSwatches: document.querySelectorAll('#lyric-color-grid .lyric-swatch').length,"
            " colorLabPop: !!document.getElementById('color-lab-pop'),"
            " lyricColorPresets: (typeof lyricColorPresets !== 'undefined' ? lyricColorPresets.length : -1) })")
        if not check('p9.skip_evidence_lyric_color_colorlab', bool(skip_ev['lyricSwatches'] > 0 and skip_ev['colorLabPop']
                                                                    and skip_ev['lyricColorPresets'] == 18), skip_ev):
            failures += 1

        # ---- P6: search pagination (real network via relay) ----
        page.fill('#search-input', '周杰伦')
        try:
            page.wait_for_selector('#search-results .search-result', timeout=45000)
        except Exception:
            pass
        page.wait_for_timeout(2500)
        keys1 = search_row_keys(page)
        btn1 = page.evaluate("() => { const b = document.querySelector('[data-search-load-more]');"
                             " return b ? { visible: b.offsetParent !== null, disabled: b.disabled, text: b.textContent } : null; }")
        if not check('p6.page1_results', len(keys1) >= 5, {'rows': len(keys1), 'sample': keys1[:3]}):
            failures += 1
        if not check('p6.load_more_button_present', bool(btn1 and btn1.get('visible')), btn1):
            failures += 1
        if not smoke and btn1:
            ids1 = page.evaluate("() => (window.playlist || []).map(s => (s.provider || s.source || '') + ':' + (s.mid || s.id || ''))")
            page.click('[data-search-load-more]')
            try:
                page.wait_for_function(
                    "(n) => (window.playlist ? window.playlist.length : 0) > n",
                    arg=len(keys1), timeout=30000)
            except Exception:
                pass
            page.wait_for_timeout(1500)
            keys2 = search_row_keys(page)
            ids2 = page.evaluate("() => (window.playlist || []).map(s => (s.provider || s.source || '') + ':' + (s.mid || s.id || ''))")
            state = page.evaluate("() => ({ offset: (typeof neteaseWebSearchPage !== 'undefined' ? neteaseWebSearchPage.offset : -1),"
                                  " playlistLen: (window.playlist ? window.playlist.length : -1) })")
            # 去重以 provider:id 为准：同名不同版本（如不同专辑的《布拉格广场》）标题/元数据
            # 文本相同但 id 不同，不算重复；真正重复是同一 provider:id 出现两次。
            id_dupes = len(ids2) - len(set(ids2))
            new_ids = [x for x in ids2 if x not in set(ids1)]
            if not check('p6.load_more_appends_no_dupes', len(keys2) > len(keys1) and id_dupes == 0 and len(new_ids) == len(keys2) - len(keys1),
                         {'before': len(keys1), 'after': len(keys2), 'idDupes': id_dupes, 'newIds': len(new_ids), 'state': state}):
                failures += 1
            if not check('p6.offset_advanced', state['offset'] > 0, state):
                failures += 1

        # ---- light regression ----
        q2 = page.evaluate("async () => ({ build: (await buildStarwaveDemoSongs()).length })")
        if not check('regression.demo_songs_removed', bool(q2 and q2.get('build') == 0), q2):
            failures += 1
        p4a = page.evaluate("() => !!window.starwavePhase4a")
        if not check('regression.phase4a_absent', not p4a, {'phase4a': p4a}):
            failures += 1
        login_ok = page.evaluate("() => ({ hasSessionFn: typeof neteaseWebHasSession === 'function',"
                                 " scriptTag: !!document.querySelector('script[src=\"starwave-netease-login.js\"]') })")
        if not check('regression.login_untouched', bool(login_ok['hasSessionFn'] and login_ok['scriptTag']), login_ok):
            failures += 1
        with open(os.path.join(ROOT, 'web', 'public', 'index.html'), encoding='utf-8') as f:
            idx_src = f.read()
        pl_ok = ('data-pl-load-more' in idx_src and 'data-pl-detail-load-more' in idx_src
                 and 'pl-detail-load-more' in idx_src and 'pl-load-more' in idx_src)
        if not check('regression.playlist_load_more_untouched', pl_ok, {}):
            failures += 1

        browser.close()

    # ---- error budget ----
    # Strict, with two documented pre-existing carve-outs (both predate 5A):
    #  (a) /api/update/latest 404: the app's self-update poller has no backend
    #      on the static host (range server / GitHub Pages); present in HEAD.
    #  (b) failed requests to third-party origins (e.g. Audius/IPFS cover
    #      images blocked by ORB): live search-result media, content-dependent
    #      and flaky; the rows already degrade via onerror opacity fallback.
    # First-party failures (missing 5A files, JS exceptions) still fail.
    console_real = [e for e in report['console_errors'] if '/api/update/latest' not in e]
    first_party_failed = [u for u in report['failed_requests'] if u.startswith(BASE_URL)]
    report['third_party_failed_requests'] = [u for u in report['failed_requests'] if not u.startswith(BASE_URL)]
    if not check('errors.console_zero', len(console_real) == 0, console_real[:5]):
        failures += 1
    if not check('errors.page_zero', len(report['page_errors']) == 0, report['page_errors'][:5]):
        failures += 1
    if not check('errors.failed_requests_zero', len(first_party_failed) == 0, first_party_failed[:5]):
        failures += 1

    report['failures'] = failures
    with open(REPORT_PATH, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print('FULL failures=%d console_errors=%d page_errors=%d failed_requests=%d' % (
        failures, len(report['console_errors']), len(report['page_errors']), len(report['failed_requests'])))
    if report['console_errors']:
        print('console_errors sample:', json.dumps(report['console_errors'][:5], ensure_ascii=False))
    if report['page_errors']:
        print('page_errors sample:', json.dumps(report['page_errors'][:5], ensure_ascii=False))
    if report['failed_requests']:
        print('failed_requests sample:', json.dumps(report['failed_requests'][:5], ensure_ascii=False))
    return 0 if failures == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
