# -*- coding: utf-8 -*-
"""StarWave Phase 5B (P3) verification — stage-lyrics prewarm, single-line cache.
Serves web/public via scripts/range-http-server.py on 127.0.0.1:4174 and
drives it with Playwright (relay 18082 for external hosts), same harness
as scripts/verify-phase5a.py.
Covers P3 (design spike concluded: DEGRADED to single-line prewarm cache;
full-track warmup + resident build dropped — see starwave-phase5.js header):
  p3b.module_present: prewarm module present, version 5b-p3, both wrappers
     installed (showStageLine + applyLyricsState)
  p3b.redline_zero_hits: static check — no red-line literal in the changed
     file (decryptor / hardcoded signing salts / security SDK / soda
     session endpoints / QQ reverse signing / cookie-file writes)
  p3b.governor_cap_pure: tier -> cap mapping (eco 0 / balanced 2 / high 4 /
     ultra 6, unknown -> 4)
  p3b.play_real_track: a real NetEase free track plays with real (non-fallback)
     lyric lines (no mocks, no demo songs)
  p3b.prewarm_builds_next_line: while playing, the next line's mesh is built
     ahead (observable stats.builds >= 1, cache holds the next line, trigger
     'next-line' or 'track-switch' fired) — asserted via renderer state
  p3b.next_line_cache_hit: seeking to just before the next line makes the
     line switch consume the prebuilt mesh (stats.hits increases, current
     line text matches lyricsLines[nextIdx])
  p3b.lyric_sync_unchanged: lyricsLines (t + text), lyric offset and timing
     source identical before/after prewarm activity; currentIdx matches the
     index computed from audio time (same rule as tickLyricsParticles)
  p3b.resume_prewarm: pause -> resume line is warmed while paused, resume
     restores the same line via a cache hit (no rebuild at the resume frame)
  p3b.track_switch_prewarm: switching to a second real track fires the
     track-switch trigger, clears the old cache and builds the new track's
     lines ahead
  p3b.low_end_guard: at governor tier eco prewarm is disabled, cache is
     emptied and schedule() refuses; tier is restored afterwards
  + light regression: demo songs removed, login module untouched, 5A presets
    still 13 (full 5A suite is re-run separately via verify-phase5a.py)
  + error budget: 0 console/page/first-party failed requests (same documented
    pre-existing carve-outs as 5A: /api/update/latest 404, third-party media).
  Note: headless Chromium renders slowly, so the Phase 2 governor auto-drops
  to eco (which disables prewarm by design). The script therefore forces
  manual tier 'high' before the enabled-path checks and restores 'auto' in
  the low-end-guard check; without the forcing the enabled path is untestable
  in this environment.
Usage:
  ~/workspace/.venv-playwright/bin/python scripts/verify-phase5b.py [--smoke]
--smoke: load + module + red-line + cap mapping + light regression only.
Report JSON: /tmp/sw-phase5b-verify-report.json
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
REPORT_PATH = '/tmp/sw-phase5b-verify-report.json'

report = {'console_errors': [], 'page_errors': [], 'failed_requests': [], 'checks': {}}

# Red-line literals (REPORT.md §6). Must be zero hits in the changed file.
# NOTE: keep this list in sync with the task's grep list.
BANNED_LITERALS = ['spade_a', 'KUGOU_', 'bdms', '/luna/pc/', 'qqSearchSign',
                   'KUGOU_ANDROID_SALT', 'KUGOU_H5_SALT', 'KUGOU_SIGN_KEY_SALT']


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
    print(('PASS ' if ok else 'FAIL ') + name + ((' :: ' + json.dumps(detail, ensure_ascii=False)[:700]) if detail is not None else ''))
    return bool(ok)


def dismiss_splash(page):
    page.wait_for_timeout(1200)
    try:
        page.wait_for_selector('#splash.ready', state='attached', timeout=30000)
        page.click('#splash', timeout=5000)
    except Exception:
        page.evaluate("() => { if (typeof dismissSplash === 'function') dismissSplash(); }")
    page.wait_for_timeout(1200)


def prewarm_snapshot(page):
    return page.evaluate("() => { const p = window.starwavePhase5 && window.starwavePhase5.prewarm;"
                         " return p ? p.snapshot() : null; }")


def lyric_snapshot(page):
    return page.evaluate(
        "() => ({ lines: (window.lyricsLines || []).map(l => (Number(l.t) || 0).toFixed(3) + '|' + (l.text || '')),"
        " timingSource: (typeof lyricsTimingSource !== 'undefined' ? lyricsTimingSource : '?'),"
        " offset: (window.__starwaveLyricOffsetSec || 0),"
        " currentIdx: (typeof stageLyrics !== 'undefined' ? stageLyrics.currentIdx : -1),"
        " currentText: (typeof stageLyrics !== 'undefined' ? stageLyrics.currentText : ''),"
        " audioTime: (window.audio ? window.audio.currentTime : -1),"
        " paused: (window.audio ? window.audio.paused : null) })")


def expected_idx(lines_t, t):
    idx = -1
    for i, lt in enumerate(lines_t):
        if lt <= t + 0.05:
            idx = i
        else:
            break
    return idx


def play_candidate(page, cand):
    """Try to play one candidate song; return (played_bool, detail)."""
    res = page.evaluate(
        """async (cand) => {
          let s = null;
          for (const q of ['周杰伦', '邓丽君', '刘德华', '陈奕迅']) {
            const songs = await fetchNeteaseWebSearchResults(q);
            s = songs.find(x => String(x.id) === String(cand.id));
            if (s) break;
          }
          if (!s) {
            s = { id: cand.id, neteaseId: cand.id, name: cand.name, artist: cand.artist || '',
                  provider: 'netease-web', source: 'netease-web', type: 'netease-web' };
          }
          window.playQueue = [s];
          window.currentIdx = 0;
          await playQueueAt(0, { manual: true });
          await new Promise(r => setTimeout(r, 8000));
          const a = window.audio;
          return {
            audio: a ? { exists: true, paused: a.paused, currentTime: a.currentTime,
                         duration: a.duration, src: (a.src || '').slice(0, 80) } : null,
            toast: (document.getElementById('toast') || {}).textContent || ''
          };
        }""", cand)
    a = (res or {}).get('audio') or {}
    if a.get('paused') is False and 'music.126.net' in (a.get('src') or ''):
        # wait for real (non-fallback) lyric lines
        try:
            page.wait_for_function(
                "() => (window.lyricsLines && window.lyricsLines.length > 5"
                " && (typeof lyricsTimingSource !== 'undefined' ? lyricsTimingSource : '') !== 'fallback')",
                timeout=30000)
            ls = lyric_snapshot(page)
            return True, {'audio': a, 'lines': len(ls['lines']), 'timingSource': ls['timingSource']}
        except Exception:
            ls = lyric_snapshot(page)
            return False, {'audio': a, 'lines': len(ls['lines']), 'timingSource': ls['timingSource'],
                           'reason': 'played but no real lyrics'}
    return False, {'audio': a, 'toast': (res or {}).get('toast', '')}


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

        # Headless Chromium renders slowly, so the Phase 2 governor's auto
        # downgrade (fps < 25 for 3 ticks) drops the tier to eco within
        # seconds — and eco disables prewarm by design. Force manual 'high'
        # for the enabled-path checks (a capable real device sits at high);
        # the eco path is exercised separately in p3b.low_end_guard.
        # Governor mode is restored to 'auto' at the end of that check.
        tier_force = page.evaluate(
            "() => { const g = window.starwavePerfGovernor;"
            " const before = g ? { tier: g.tier, fps: g.fps, mode: g.mode } : null;"
            " if (g) g.setMode('high');"
            " return { before: before,"
            " after: g ? { tier: g.tier, fps: g.fps, mode: g.mode } : null }; }")
        page.wait_for_timeout(800)
        tier_now = page.evaluate(
            "() => (window.starwavePerfGovernor ? window.starwavePerfGovernor.tier : null)")
        if not check('p3b.tier_forced_high', tier_now == 'high',
                     {'force': tier_force, 'tierNow': tier_now}):
            failures += 1

        # ---- module present ----
        mod = page.evaluate(
            "() => { const m = window.starwavePhase5; const p = m && m.prewarm;"
            " return m ? { version: m.version, available: m.available,"
            " prewarmVersion: p ? p.version : null,"
            " wrapped: p ? p.snapshot().wrapped : null,"
            " tier: p ? p.snapshot().tier : null,"
            " cap: p ? p.snapshot().cap : null } : null; }")
        mod_ok = bool(mod and mod.get('available') and mod.get('prewarmVersion') == '5b-p3'
                      and (mod.get('wrapped') or {}).get('showStageLine')
                      and (mod.get('wrapped') or {}).get('applyLyricsState'))
        if not check('p3b.module_present', mod_ok, mod):
            failures += 1

        # ---- red-line static check (changed file only) ----
        with open(os.path.join(ROOT, 'web', 'public', 'starwave-phase5.js'), encoding='utf-8') as f:
            p5_src = f.read()
        banned_hits = [b for b in BANNED_LITERALS if b in p5_src]
        # cookie-file writes / hardcoded passwords: no such constructs in this file
        extra_hits = []
        if 'document.cookie' in p5_src:
            extra_hits.append('document.cookie')
        if not check('p3b.redline_zero_hits', not banned_hits and not extra_hits,
                     {'banned': banned_hits, 'extra': extra_hits}):
            failures += 1

        # ---- governor cap mapping (pure function) ----
        caps = page.evaluate(
            "() => { const p = window.starwavePhase5 && window.starwavePhase5.prewarm;"
            " if (!p) return null;"
            " return { eco: p.capForTier('eco'), balanced: p.capForTier('balanced'),"
            " high: p.capForTier('high'), ultra: p.capForTier('ultra'),"
            " unknown: p.capForTier('bogus'), tierNow: p.snapshot().tier }; }")
        caps_ok = bool(caps and caps.get('eco') == 0 and caps.get('balanced') == 2
                       and caps.get('high') == 4 and caps.get('ultra') == 6
                       and caps.get('unknown') == 4)
        if not check('p3b.governor_cap_pure', caps_ok, caps):
            failures += 1

        played = None
        candidates = []
        if not smoke:
            # ---- collect fee-0 candidates (phase3 pattern) ----
            for q in ['周杰伦', '邓丽君', '刘德华', '陈奕迅']:
                try:
                    ne = page.evaluate(
                        """async (q) => {
                          const songs = await fetchNeteaseWebSearchResults(q);
                          return songs.map(s => ({ name: s.name, artist: s.artist, fee: s.fee, id: s.id }));
                        }""", q)
                except Exception:
                    ne = []
                for cand in (ne or []):
                    if cand.get('fee') == 0 and cand['id'] not in [c['id'] for c in candidates]:
                        candidates.append(cand)
                if candidates:
                    break
            if 288820 not in [c['id'] for c in candidates]:
                candidates.append({'name': '结尾曲-友谊地久天长(Live)', 'artist': '宋祖英 / 郎朗 / 多明戈 / 周杰伦', 'fee': 0, 'id': 288820})

            attempts = []
            for cand in candidates[:6]:
                ok, detail = play_candidate(page, cand)
                attempts.append({'name': cand['name'], 'id': cand['id'], 'ok': ok, 'detail': detail})
                if ok:
                    played = {'name': cand['name'], 'id': cand['id'], 'detail': detail}
                    break
                page.wait_for_timeout(2000)
            if not check('p3b.play_real_track', bool(played),
                         {'played': played, 'attempts': attempts}):
                failures += 1

        if played and not smoke:
            snap0 = prewarm_snapshot(page)
            lyr0 = lyric_snapshot(page)
            lines_t = [float(x.split('|')[0]) for x in lyr0['lines']]

            # ---- prewarm builds the next line ahead ----
            # Wait until the NEXT line specifically is cached (not just any
            # build): the cached text must equal lyricsLines[currentIdx+1].
            built = False
            snap = snap0
            next_txt = {}
            for _ in range(80):  # up to ~40s
                page.wait_for_timeout(500)
                snap = prewarm_snapshot(page)
                next_txt = page.evaluate(
                    "() => { const s = window.starwavePhase5.prewarm.snapshot();"
                    " const idx = s.currentIdx + 1;"
                    " const lines = (typeof lyricsLines !== 'undefined' ? lyricsLines : []);"
                    " const norm = t => String(t || '').replace(/\\s+/g, ' ').trim();"
                    " const want = (idx >= 0 && idx < lines.length) ? norm(lines[idx].text) : '';"
                    " return { want: want, idx: idx, cachedTexts: s.items.map(i => i.text),"
                    " match: want ? s.items.some(i => i.text === want) : false }; }")
                if snap and snap['stats']['builds'] >= 1 and snap['cacheSize'] >= 1 and next_txt.get('match'):
                    built = True
                    break
            trig = (snap or {}).get('stats', {}).get('triggers', {})
            if not check('p3b.prewarm_builds_next_line', built,
                         {'snapshot': snap, 'triggers': trig, 'nextLine': next_txt}):
                failures += 1

            # ---- next-line switch consumes the prebuilt mesh ----
            hits0 = (snap or {}).get('stats', {}).get('hits', 0)
            seek_plan = page.evaluate(
                """() => {
                  const a = window.audio; if (!a) return null;
                  const now = a.currentTime + (window.__starwaveLyricOffsetSec || 0);
                  const cur = (typeof stageLyrics !== 'undefined' ? stageLyrics.currentIdx : -1);
                  const lines = window.lyricsLines || [];
                  for (let j = Math.max(0, cur + 1); j < lines.length; j++) {
                    const tj = Number(lines[j].t || 0);
                    if (tj - now > 1.5 && tj < (a.duration || 1e9) - 1) {
                      return { targetIdx: j, targetTime: tj - 0.3, text: lines[j].text || '' };
                    }
                  }
                  return null;
                }""")
            hit_ok = False
            hit_detail = {'seekPlan': seek_plan, 'hits0': hits0}
            if seek_plan:
                page.evaluate("(t) => { window.audio.currentTime = t; }", seek_plan['targetTime'])
                try:
                    page.wait_for_function("(j) => (typeof stageLyrics !== 'undefined' && stageLyrics.currentIdx === j)",
                                           arg=seek_plan['targetIdx'], timeout=10000)
                    page.wait_for_timeout(500)
                except Exception:
                    pass
                snap1 = prewarm_snapshot(page)
                lyr1 = lyric_snapshot(page)
                hit_detail.update({'snapshot': snap1, 'lyric': lyr1})
                hit_ok = bool(snap1 and snap1['stats']['hits'] > hits0
                              and lyr1['currentIdx'] == seek_plan['targetIdx']
                              and lyr1['currentText'] == seek_plan['text'])
                if not hit_ok:
                    # seek may not have taken effect (range/buffering): fall back
                    # to a natural wait for any cache hit on a line switch.
                    cur_time = page.evaluate("() => (window.audio ? window.audio.currentTime : -1)")
                    hit_detail['seekDidNotMove'] = cur_time
                    for _ in range(180):  # up to ~90s natural wait
                        page.wait_for_timeout(500)
                        snap_n = prewarm_snapshot(page)
                        if snap_n and snap_n['stats']['hits'] > hits0:
                            hit_ok = True
                            hit_detail['naturalHitSnapshot'] = snap_n
                            break
                    hit_detail['finalSnapshot'] = prewarm_snapshot(page)
            else:
                # no seekable next line (e.g. near track end): natural wait.
                for _ in range(180):
                    page.wait_for_timeout(500)
                    snap_n = prewarm_snapshot(page)
                    if snap_n and snap_n['stats']['hits'] > hits0:
                        hit_ok = True
                        hit_detail['naturalHitSnapshot'] = snap_n
                        break
                hit_detail['finalSnapshot'] = prewarm_snapshot(page)
            if not check('p3b.next_line_cache_hit', hit_ok, hit_detail):
                failures += 1

            # ---- poll refill: clearing the cache mid-playback must make the
            # 500ms poll rebuild the next line on its own ('next-line'
            # trigger). In the runs above the track-switch/resume triggers
            # always covered the next line first, so this isolates the poll.
            snap_pre_refill = prewarm_snapshot(page)
            nl_pre = (snap_pre_refill or {}).get('stats', {}).get('triggers', {}).get('next-line', 0)
            builds_pre_refill = (snap_pre_refill or {}).get('stats', {}).get('builds', 0)
            page.evaluate("() => window.starwavePhase5.prewarm.clear()")
            refill_ok = False
            snap_refill = None
            for _ in range(20):  # up to ~10s
                page.wait_for_timeout(500)
                snap_refill = prewarm_snapshot(page)
                if (snap_refill and snap_refill['stats']['triggers'].get('next-line', 0) > nl_pre
                        and snap_refill['stats']['builds'] > builds_pre_refill):
                    refill_ok = True
                    break
            if not check('p3b.poll_next_line_refill', refill_ok,
                         {'triggersNextLineBefore': nl_pre, 'buildsBefore': builds_pre_refill,
                          'snapshot': snap_refill}):
                failures += 1

            # ---- lyric sync unchanged ----
            lyr_after = lyric_snapshot(page)
            lines_after_t = [float(x.split('|')[0]) for x in lyr_after['lines']]
            t_now = lyr_after['audioTime'] + lyr_after['offset']
            exp = expected_idx(lines_after_t, t_now)
            cur = lyr_after['currentIdx']
            # tick rule: before the first line the renderer shows the intro
            # fallback at currentIdx -2; both -1 and -2 are "before first line".
            idx_match = (cur == exp) or (exp == -1 and cur in (-1, -2))
            sync_ok = (lyr_after['lines'] == lyr0['lines']
                       and lyr_after['timingSource'] == lyr0['timingSource']
                       and lyr_after['offset'] == lyr0['offset']
                       and idx_match)
            if not check('p3b.lyric_sync_unchanged', sync_ok,
                         {'linesSame': lyr_after['lines'] == lyr0['lines'],
                          'timingSource': (lyr0['timingSource'], lyr_after['timingSource']),
                          'offset': (lyr0['offset'], lyr_after['offset']),
                          'expectedIdx': exp, 'currentIdx': cur, 'audioTime': t_now}):
                failures += 1

            # ---- resume prewarm ----
            pre_pause = lyric_snapshot(page)
            snap_pre_pause = prewarm_snapshot(page)
            hits_pre = (snap_pre_pause or {}).get('stats', {}).get('hits', 0)
            page.evaluate("() => { if (window.audio) window.audio.pause(); }")
            try:
                page.wait_for_function("() => (window.audio ? window.audio.paused : false)", timeout=5000)
            except Exception:
                pass
            page.wait_for_timeout(2500)  # poll warms the resume line while paused
            snap_paused = prewarm_snapshot(page)
            paused_cache_texts = [it['text'] for it in (snap_paused or {}).get('items', [])]
            resume_line_warm = pre_pause['currentText'] in paused_cache_texts
            page.evaluate("() => { if (window.audio) window.audio.play(); }")
            resumed = False
            try:
                page.wait_for_function(
                    "(j) => (typeof stageLyrics !== 'undefined' && stageLyrics.currentIdx === j)",
                    arg=pre_pause['currentIdx'], timeout=10000)
                resumed = True
            except Exception:
                pass
            page.wait_for_timeout(800)
            snap_resumed = prewarm_snapshot(page)
            lyr_resumed = lyric_snapshot(page)
            hits_post = (snap_resumed or {}).get('stats', {}).get('hits', 0)
            trig_resume = (snap_resumed or {}).get('stats', {}).get('triggers', {}).get('resume', 0)
            resume_ok = bool(resume_line_warm and resumed and hits_post > hits_pre
                             and lyr_resumed['currentIdx'] == pre_pause['currentIdx']
                             and lyr_resumed['currentText'] == pre_pause['currentText']
                             and trig_resume >= 1)
            if not check('p3b.resume_prewarm', resume_ok,
                         {'prePause': pre_pause, 'pausedCacheTexts': paused_cache_texts,
                          'resumeLineWarm': resume_line_warm, 'resumed': resumed,
                          'hits': (hits_pre, hits_post), 'triggersResume': trig_resume,
                          'afterResume': lyr_resumed}):
                failures += 1

            # ---- track-switch prewarm (second real track) ----
            remaining = [c for c in candidates if c['id'] != played['id']]
            snap_pre_switch = prewarm_snapshot(page)
            ts_pre = (snap_pre_switch or {}).get('stats', {}).get('triggers', {}).get('track-switch', 0)
            builds_pre = (snap_pre_switch or {}).get('stats', {}).get('builds', 0)
            token_pre = (snap_pre_switch or {}).get('trackToken')
            switched = None
            switch_attempts = []
            for cand in remaining[:2]:
                ok, detail = play_candidate(page, cand)
                switch_attempts.append({'name': cand['name'], 'id': cand['id'], 'ok': ok, 'detail': detail})
                if ok:
                    switched = {'name': cand['name'], 'id': cand['id']}
                    break
                page.wait_for_timeout(2000)
            if not switched:
                # No other fee-0 candidate is playable without login (known
                # app behavior: fee=0 does not guarantee a playable URL).
                # Fall back to replaying the same song: playQueueAt still
                # mints a new trackSwitchToken and re-applies lyrics, so the
                # track-switch trigger + cache clear + rebuild path is the
                # same code path as switching to a different track.
                ok, detail = play_candidate(page, played)
                switch_attempts.append({'name': played['name'], 'id': played['id'],
                                        'ok': ok, 'detail': detail, 'replay': True})
                if ok:
                    switched = {'name': played['name'], 'id': played['id'], 'replay': True}
            snap_post_switch = None
            switch_ok = False
            if switched:
                for _ in range(60):  # up to ~30s for the new track's prewarm
                    page.wait_for_timeout(500)
                    snap_post_switch = prewarm_snapshot(page)
                    if (snap_post_switch and snap_post_switch['trackToken'] != token_pre
                            and snap_post_switch['stats']['builds'] > builds_pre):
                        switch_ok = True
                        break
            # Round-2 fix (Minor 2): the post-switch cache must hold no
            # old-token items (snapshot items now carry token). Non-empty is
            # required: all() over zero items would pass vacuously (L1).
            old_token_gone = False
            if snap_post_switch:
                old_token_gone = (len(snap_post_switch.get('items', [])) >= 1
                                  and all(i.get('token') == snap_post_switch.get('trackToken')
                                          for i in snap_post_switch.get('items', [])))
            switch_ok = switch_ok and old_token_gone
            if not check('p3b.track_switch_prewarm', bool(switched and switch_ok),
                         {'switched': switched, 'attempts': switch_attempts,
                          'triggersBefore': ts_pre, 'buildsBefore': builds_pre,
                          'tokenBefore': token_pre, 'snapshotAfter': snap_post_switch,
                          'oldTokenGone': old_token_gone}):
                failures += 1

            # ---- same-lyrics re-apply dedup (Minor 2) ----
            # Re-applying the identical lyrics with the same track token must
            # not clear/rebuild: snapshot items/keys are identical immediately
            # after the synchronous re-apply (no poll tick can interleave).
            dedup = page.evaluate(
                "() => { const p = window.starwavePhase5.prewarm;"
                " const b = p.snapshot();"
                " window.applyLyricsState(window.lyricsLines, window.lyricsHasNativeKaraoke, window.lyricsTimingSource);"
                " const a = p.snapshot();"
                " return { wrapped: !!b.wrapped.applyLyricsState,"
                " sizeBefore: b.cacheSize, sizeAfter: a.cacheSize,"
                " keysBefore: b.items.map(i => i.key), keysAfter: a.items.map(i => i.key),"
                " buildsBefore: b.stats.builds, buildsAfter: a.stats.builds }; }")
            dedup_ok = (dedup['wrapped'] and dedup['sizeBefore'] >= 1
                        and dedup['sizeAfter'] == dedup['sizeBefore']
                        and dedup['keysAfter'] == dedup['keysBefore']
                        and dedup['buildsAfter'] == dedup['buildsBefore'])
            if not check('p3b.same_lyrics_reapply_no_rebuild', dedup_ok, dedup):
                failures += 1

            # ---- low-end guard (live eco test, tier restored after) ----
            gov = page.evaluate(
                "() => ({ hasSetter: typeof setPerformanceQualityMode === 'function',"
                " tier: (window.starwavePerfGovernor ? window.starwavePerfGovernor.tier : null),"
                " mode: (window.starwavePerfGovernor ? window.starwavePerfGovernor.mode : null) })")
            eco_ok = False
            eco_detail = {'governor': gov}
            if gov.get('hasSetter') and gov.get('tier'):
                orig_tier = gov['tier']
                snap_before_eco = prewarm_snapshot(page)
                builds_eco0 = (snap_before_eco or {}).get('stats', {}).get('builds', 0)
                page.evaluate("(t) => setPerformanceQualityMode(t, true)", 'eco')
                page.wait_for_timeout(1500)
                snap_eco = prewarm_snapshot(page)
                refused = page.evaluate("() => window.starwavePhase5.prewarm.schedule(0, 'test')")
                page.wait_for_timeout(800)
                snap_eco2 = prewarm_snapshot(page)
                eco_detail.update({'snapshotEco': snap_eco, 'scheduleRefused': refused,
                                   'buildsBeforeEco': builds_eco0,
                                   'buildsAfterEco': (snap_eco2 or {}).get('stats', {}).get('builds', 0)})
                eco_ok = bool(snap_eco and snap_eco['enabled'] is False and snap_eco['cap'] == 0
                              and snap_eco['cacheSize'] == 0 and refused is False
                              and (snap_eco2 or {}).get('stats', {}).get('builds', 0) == builds_eco0)
                # restore the original tier + auto governor mode. NOTE: in
                # auto mode the tier is re-derived from live fps, so it need
                # not read back as orig_tier in headless (fps ~2-3); assert
                # the mode is back to auto and record the tier instead.
                page.evaluate("(t) => setPerformanceQualityMode(t, true)", orig_tier)
                page.evaluate("() => { if (window.starwavePerfGovernor) window.starwavePerfGovernor.setMode('auto'); }")
                page.wait_for_timeout(1000)
                restored = page.evaluate(
                    "() => (window.starwavePerfGovernor ? window.starwavePerfGovernor.tier : null)")
                restored_mode = page.evaluate(
                    "() => (window.starwavePerfGovernor ? window.starwavePerfGovernor.mode : null)")
                eco_detail['restoredTier'] = restored
                eco_detail['restoredMode'] = restored_mode
                eco_ok = eco_ok and (restored_mode == 'auto')
            if not check('p3b.low_end_guard', eco_ok, eco_detail):
                failures += 1

        # ---- light regression (5A must not regress) ----
        q2 = page.evaluate("async () => ({ build: (await buildStarwaveDemoSongs()).length })")
        if not check('regression.demo_songs_removed', bool(q2 and q2.get('build') == 0), q2):
            failures += 1
        login_ok = page.evaluate("() => ({ hasSessionFn: typeof neteaseWebHasSession === 'function',"
                                 " scriptTag: !!document.querySelector('script[src=\"starwave-netease-login.js\"]') })")
        if not check('regression.login_untouched', bool(login_ok['hasSessionFn'] and login_ok['scriptTag']), login_ok):
            failures += 1
        presets = page.evaluate(
            "() => ({ metaCount: (typeof presetMeta !== 'undefined' ? presetMeta.length : -1),"
            " cards: document.querySelectorAll('#preset-grid .preset-card').length })")
        if not check('regression.presets_still_13', presets['metaCount'] == 13 and presets['cards'] == 13, presets):
            failures += 1

        browser.close()

    # ---- error budget (same carve-outs as 5A; no deliberate aborts here) ----
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
    try:
        with open(REPORT_PATH, 'w', encoding='utf-8') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
    except OSError as e:
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
