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
  Phase 5A review-fix coverage (checks p6r/p9r/p1r):
    (a) failed load-more keeps the button + retry then succeeds;
    (b) mode switch / new search resets stale pagination (no phantom button);
    (c) clearCaches preserves the PWA shell cache starwave-pwa-v1;
    (d) presets 9-12 selectable with no new console/page (incl. WebGL) errors.
    Round-2 (M1): stale empty load-more must not tighten the new search's total.
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
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(30):
        if _port_open(RANGE_PORT):
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
    aborted_for_test = 0  # requests deliberately aborted by check (a); see error budget

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
        # review fix (d): presets 9-12 selectable with no new console/page errors
        # (WebGL failures surface as console errors from the renderer).
        err_before = (len(report['console_errors']), len(report['page_errors']))
        sel912 = page.evaluate(
            "async () => { const out = [];"
            " for (let i = 9; i <= 12; i++) {"
            " try { setPreset(i, { silent: true, noSave: true, skipTransition: true });"
            " await new Promise(r => setTimeout(r, 500));"
            " out.push({ i: i, fx: (typeof fx !== 'undefined' ? fx.preset : -1),"
            " u: (typeof uniforms !== 'undefined' && uniforms.uPreset ? uniforms.uPreset.value : -1) }); }"
            " catch (e) { out.push({ i: i, err: String(e) }); } }"
            " setPreset(0, { silent: true, noSave: true, skipTransition: true }); return out; }")
        err_after = (len(report['console_errors']), len(report['page_errors']))
        sel912_ok = all(s.get('fx') == s.get('i') and s.get('u') == s.get('i') for s in sel912)
        if not check('p1r.presets_9_12_no_errors', sel912_ok and err_after == err_before,
                     {'sel': sel912, 'consoleDelta': err_after[0] - err_before[0],
                      'pageDelta': err_after[1] - err_before[1]}):
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
        # review fix (c): clearCaches preserves the PWA shell cache starwave-pwa-v1
        cache_check = page.evaluate(
            "async () => {"
            " const pwa = await caches.open('starwave-pwa-v1');"
            " await pwa.put('/__sw5a_probe', new Response('probe'));"
            " const junk = await caches.open('sw5a-junk-cache');"
            " await junk.put('/__sw5a_junk', new Response('junk'));"
            " const before = await caches.keys();"
            " const deleted = await window.starwavePhase5.storage.clearCaches();"
            " const after = await caches.keys();"
            " const probe = await (await caches.open('starwave-pwa-v1')).match('/__sw5a_probe');"
            " return { before: before, after: after, deleted: deleted,"
            " pwaKept: after.includes('starwave-pwa-v1') && !!probe,"
            " junkGone: !after.includes('sw5a-junk-cache') }; }")
        if not check('p9r.clear_caches_preserves_pwa',
                     bool(cache_check['pwaKept'] and cache_check['junkGone']), cache_check):
            failures += 1
        # Round-2 fix (L1): remove the probe entry left in the PWA shell cache.
        try:
            page.evaluate("async () => { const c = await caches.open('starwave-pwa-v1'); await c.delete('/__sw5a_probe'); }")
        except Exception:
            pass

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

        # ---- P6 review fix (a): failed load-more keeps the button, retry succeeds ----
        if not smoke and btn1:
            fail_state = {'armed': False, 'failed': 0}
            search_url_pred = lambda u: 'api-enhanced-pied-rho.vercel.app/search' in str(u)

            def _fail_once(route):
                if fail_state['armed'] and fail_state['failed'] == 0:
                    fail_state['failed'] += 1
                    route.abort()
                else:
                    route.continue_()

            page.route(search_url_pred, _fail_once)
            fail_state['armed'] = True
            page_state = lambda: page.evaluate(
                "() => ({ len: (window.playlist ? window.playlist.length : -1),"
                " query: (typeof neteaseWebSearchPage !== 'undefined' ? neteaseWebSearchPage.query : null),"
                " offset: (typeof neteaseWebSearchPage !== 'undefined' ? neteaseWebSearchPage.offset : -1),"
                " total: (typeof neteaseWebSearchPage !== 'undefined' ? neteaseWebSearchPage.total : -1),"
                " lastFetchOk: (typeof neteaseWebSearchPage !== 'undefined' ? neteaseWebSearchPage.lastFetchOk : null),"
                " btn: (() => { const b = document.querySelector('[data-search-load-more]');"
                " return b ? { visible: b.offsetParent !== null, disabled: b.disabled, text: b.textContent } : null; })() })")
            before_fail = page_state()
            page.click('[data-search-load-more]')
            page.wait_for_timeout(1500)
            after_fail = page_state()
            toast_fail = page.evaluate("() => (document.getElementById('toast') || {}).textContent || ''")
            fail_ok = (fail_state['failed'] == 1 and after_fail['len'] == before_fail['len']
                       and after_fail['offset'] == before_fail['offset']
                       and after_fail['total'] == before_fail['total']
                       and after_fail['lastFetchOk'] is False
                       and after_fail['btn'] and after_fail['btn']['visible']
                       and not after_fail['btn']['disabled']
                       and '加载更多失败' in toast_fail)
            if not check('p6r.load_more_failure_keeps_button', fail_ok,
                         {'before': before_fail, 'after': after_fail, 'toast': toast_fail,
                          'aborted': fail_state['failed']}):
                failures += 1
            aborted_for_test = fail_state['failed']
            # retry with the failure disarmed: same button must now append page 3
            fail_state['armed'] = False
            page.click('[data-search-load-more]')
            try:
                page.wait_for_function(
                    "(n) => (window.playlist ? window.playlist.length : 0) > n",
                    arg=after_fail['len'], timeout=30000)
            except Exception:
                pass
            page.wait_for_timeout(1500)
            after_retry = page_state()
            retry_ok = (after_retry['len'] > after_fail['len']
                        and after_retry['offset'] > after_fail['offset']
                        and after_retry['lastFetchOk'] is True)
            if not check('p6r.load_more_retry_succeeds', retry_ok,
                         {'afterFail': after_fail, 'afterRetry': after_retry}):
                failures += 1

            # Round-2 fix (M1) regression: a stale empty load-more must not
            # tighten the NEW search's total. Deterministic: the stale fetch
            # is fulfilled empty by route interception, while the reset + new
            # state write happen synchronously in the same JS task, so the
            # response can only land after the new search's state is written.
            # Without the fix, total would be tightened to 0 and the button lost.
            page.unroute(search_url_pred, _fail_once)
            race_state = {'n': 0}

            def _empty_first_stale(route):
                try:
                    from urllib.parse import urlparse, parse_qs
                    off = int(parse_qs(urlparse(str(route.request.url)).query).get('offset', ['0'])[0])
                except Exception:
                    off = 0
                if off > 0 and race_state['n'] == 0:
                    race_state['n'] += 1
                    route.fulfill(status=200, content_type='application/json',
                                  body='{"code":200,"result":{"songs":[],"songCount":0}}')
                else:
                    route.continue_()

            page.route(search_url_pred, _empty_first_stale)
            race = page.evaluate(
                "async () => {"
                " const p = neteaseWebSearchLoadMore();"
                " resetNeteaseWebSearchPage();"
                " neteaseWebSearchPage.query = '五月天';"
                " neteaseWebSearchPage.offset = 0;"
                " neteaseWebSearchPage.total = 500;"
                " neteaseWebSearchPage.lastCount = 10;"
                " const songs = await p;"
                " updateSearchLoadMoreButton();"
                " return { songs: songs.length, total: neteaseWebSearchPage.total,"
                " query: neteaseWebSearchPage.query,"
                " btn: !!document.querySelector('[data-search-load-more]') }; }")
            page.unroute(search_url_pred, _empty_first_stale)
            if not check('p6r.stale_empty_load_more_no_tighten',
                         race['total'] == 500 and race['query'] == '五月天' and race['btn'], race):
                failures += 1

        # ---- P6 review fix (b): mode switch / new search resets stale pagination ----
        if not smoke:
            # LOCAL_FIRST_MODE=true locks setSearchMode() to 'song' (index.html:
            # `if (LOCAL_FIRST_MODE) mode = 'song'`), so the UI mode switch
            # cannot be exercised in this build. Test the same reset path the
            # switch uses instead: clearSearchResults() (called by setSearchMode)
            # must drop the pagination state and hide the button.
            local_first = page.evaluate("() => (typeof LOCAL_FIRST_MODE !== 'undefined' ? !!LOCAL_FIRST_MODE : false)")
            if local_first:
                page.evaluate("() => { clearSearchResults(); updateSearchLoadMoreButton(); }")
                page.wait_for_timeout(500)
                mode_state = page.evaluate(
                    "() => ({ mode: (typeof searchMode !== 'undefined' ? searchMode : '?'),"
                    " query: (typeof neteaseWebSearchPage !== 'undefined' ? neteaseWebSearchPage.query : null),"
                    " btn: !!document.querySelector('[data-search-load-more]'),"
                    " rows: document.querySelectorAll('#search-results .search-result').length })")
                if not check('p6r.mode_switch_reset_path',
                             mode_state['query'] == '' and not mode_state['btn'] and mode_state['rows'] == 0, mode_state):
                    failures += 1
            else:
                page.evaluate("() => setSearchMode('netease')")
                try:
                    page.wait_for_selector('#search-results .search-result', timeout=45000)
                except Exception:
                    pass
                page.wait_for_timeout(2000)
                mode_state = page.evaluate(
                    "() => ({ mode: (typeof searchMode !== 'undefined' ? searchMode : '?'),"
                    " query: (typeof neteaseWebSearchPage !== 'undefined' ? neteaseWebSearchPage.query : null),"
                    " btn: !!document.querySelector('[data-search-load-more]'),"
                    " rows: document.querySelectorAll('#search-results .search-result').length })")
                if not check('p6r.mode_switch_resets_pagination',
                             mode_state['mode'] == 'netease' and mode_state['query'] == ''
                             and not mode_state['btn'] and mode_state['rows'] >= 1, mode_state):
                    failures += 1
            page.evaluate("() => setSearchMode('song')")
            page.wait_for_timeout(500)
            page.fill('#search-input', '五月天')
            try:
                page.wait_for_function(
                    "() => (typeof neteaseWebSearchPage !== 'undefined' && neteaseWebSearchPage.query === '五月天')",
                    timeout=30000)
            except Exception:
                pass
            page.wait_for_timeout(1500)
            newq = page.evaluate(
                "() => ({ mode: (typeof searchMode !== 'undefined' ? searchMode : '?'),"
                " query: (typeof neteaseWebSearchPage !== 'undefined' ? neteaseWebSearchPage.query : null),"
                " btn: !!document.querySelector('[data-search-load-more]'),"
                " rows: document.querySelectorAll('#search-results .search-result').length })")
            if not check('p6r.new_search_resets_pagination',
                         newq['mode'] == 'song' and newq['query'] == '五月天' and newq['rows'] >= 1 and newq['btn'], newq):
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
    #  (c) review-fix check (a) deliberately aborts one api-enhanced search
    #      request; Chromium logs one "Failed to load resource" console error
    #      for it. That error is the test's own doing — excluded below, capped
    #      at the aborted count, so a real second failure still fails.
    # First-party failures (missing 5A files, JS exceptions) still fail.
    console_real = [e for e in report['console_errors'] if '/api/update/latest' not in e]
    _abort_left = aborted_for_test
    _kept = []
    for e in console_real:
        if _abort_left > 0 and e.strip() == 'Failed to load resource: net::ERR_FAILED':
            _abort_left -= 1
            continue
        _kept.append(e)
    console_real = _kept
    first_party_failed = [u for u in report['failed_requests'] if u.startswith(BASE_URL)]
    report['third_party_failed_requests'] = [u for u in report['failed_requests'] if not u.startswith(BASE_URL)]
    # Carve-out (b) also applies to the console side: a failed third-party
    # resource (e.g. Audius cover image) logs one "Failed to load resource"
    # console error, and console errors carry no URL. Attribute by count:
    # drop up to (third-party failed requests minus the deliberate abort,
    # already excluded above) such errors. This cannot mask a first-party
    # failure: first-party failures still fail errors.failed_requests_zero
    # independently of the console budget.
    _tp_left = len(report['third_party_failed_requests']) - aborted_for_test
    _kept2 = []
    for e in console_real:
        if _tp_left > 0 and e.strip().startswith('Failed to load resource: net::'):
            _tp_left -= 1
            continue
        _kept2.append(e)
    console_real = _kept2
    if not check('errors.console_zero', len(console_real) == 0, console_real[:5]):
        failures += 1
    if not check('errors.page_zero', len(report['page_errors']) == 0, report['page_errors'][:5]):
        failures += 1
    if not check('errors.failed_requests_zero', len(first_party_failed) == 0, first_party_failed[:5]):
        failures += 1

    report['failures'] = failures
    try:
        with open(REPORT_PATH, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    except OSError as e:
        # Report is a convenience artifact; the verdict is the stdout checks
        # + exit code, so a transient write failure must not mask the result.
        print('WARN report write failed (%s); verdict stands on stdout checks' % e)
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
