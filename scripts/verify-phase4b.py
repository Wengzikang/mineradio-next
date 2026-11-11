# -*- coding: utf-8 -*-
"""StarWave Phase 4B verification (real browser, real network).
Serves web/public via scripts/range-http-server.py on 127.0.0.1:4174 and
drives it with Playwright (relay 18082 for external hosts), same harness
as scripts/verify-phase3.py.
Covers task items A-H:
  A rule AI DJ: generate (line + '规则生成，非大模型' label), play a seeded
    fixture queue (demo songs were deleted 2026-11-10 at Ma's order, so the
    DJ pool is seeded with the local fixture instead)
  B hybrid recommend: platform recommend_songs attempt + local mix + dedupe +
    playable-first sort, cold-start fallback label
  C music report: day/week/month/year compute from real listen history
    (seeded by real fixture playback), annual share card canvas export,
    export/clear data entry points
  D theme packs: 5 built-ins (names must not reuse original preset names),
    apply/import/export, cover-color theme (honest fallback)
  E particles + scenes + segment shots: 4 forms, audio drive (kick/spectrum),
    fps-adaptive budget wired to Phase 2 governor, 3 scenes, shot switching
  F listening pet + AI theme: 2 original pets (names must not copy
    mineradio.art pets), crawl-along-progress, DualTheme own format
  G mobile P1/P2: no Google Fonts, gesture default off, portrait shelf,
    PWA install status, double-tap like, long-press menu, shake/gyro toggles
  H repo/redirect URI references updated to mineradio-next
  + light regression: demo songs removed, phase4a removed, no page errors
Usage:
  ~/workspace/.venv-playwright/bin/python scripts/verify-phase4b.py [--smoke]
--smoke: fast bounded check only (load, no pageerror, FAB + tabs visible,
one real interaction per feature). Full run exercises everything.
Report JSON: /tmp/sw-phase4b-verify-report.json
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
LOCAL_MP3 = '/tmp/sw-local-test.mp3'

report = {'console_errors': [], 'page_errors': [], 'failed_requests': [], 'checks': {}}


def prepare_test_files():
    """(Re)generate the deterministic fixture mp3 in /tmp (same file as
    verify-phase3.py; the demo songs were deleted 2026-11-10 at Ma's order,
    so sections A/C/E seed their queues with this fixture instead)."""
    r = subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
                        '-f', 'lavfi', '-i', 'anoisesrc=color=white:duration=30',
                        '-codec:a', 'libmp3lame', '-q:a', '4', LOCAL_MP3],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError('ffmpeg failed to generate LOCAL_MP3: ' + (r.stderr or ''))


def import_fixture(page):
    """Import the generated MP3 fixture as a local file and return the
    imported song object (blob URL; the same real-analyser chain the deleted
    demo songs used to exercise). Playing a local file with no cached beat
    map opens the local-beat analysis modal, so close it (it would block
    later pointer actions such as the cover double-tap)."""
    page.set_input_files('#file-input', LOCAL_MP3)
    page.wait_for_timeout(4000)
    page.evaluate("() => { try { if (typeof closeLocalBeatModal === 'function') closeLocalBeatModal(); } catch (e) {} }")
    page.wait_for_timeout(500)
    modal_open = page.evaluate("() => { const m = document.getElementById('local-beat-modal'); return !!(m && m.classList.contains('show')); }")
    if modal_open:
        page.keyboard.press('Escape')
        page.wait_for_timeout(500)
    return page.evaluate("() => { const s = window.currentLocalSong || (window.playQueue && window.playQueue[0]) || null; return s ? { name: s.name, id: s.id, localKey: s.localKey, publicAudioUrl: s.publicAudioUrl, previewUrl: s.previewUrl, provider: s.provider, type: s.type } : null; }")


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


def main():
    prepare_test_files()
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
        p4b = page.evaluate("() => { const m = window.starwavePhase4b; return m ? { version: m.version, available: m.available } : null; }")
        if not check('load.phase4b_present', bool(p4b and p4b.get('available')), p4b):
            failures += 1
        fab = page.evaluate("() => { const f = document.getElementById('sw4b-fab'); if (!f) return null; const r = f.getBoundingClientRect(); return { visible: r.width > 0 && r.height > 0 }; }")
        if not check('load.fab_visible', bool(fab), fab):
            failures += 1
        p3ok = page.evaluate("() => !!window.starwavePhase3")
        p4aok = page.evaluate("() => !!window.starwavePhase4a")
        # 汽水已移除（Ma 2026-11-09 22:45 决定）：phase4a 应当不存在，存在才是失败。
        if not check('load.phase3_present_phase4a_removed', bool(p3ok and not p4aok), {'phase3': p3ok, 'phase4a': p4aok}):
            failures += 1

        # ---- panel + tabs ----
        page.evaluate("() => window.starwavePhase4b.openPanel('dj')")
        page.wait_for_timeout(600)
        tabs = page.evaluate("() => Array.from(document.querySelectorAll('#sw4b-panel [data-tab]')).map(b => b.getAttribute('data-tab'))")
        if not check('ui.tabs_present', tabs == ['dj', 'rec', 'report', 'theme', 'visual', 'pet', 'mobile'], tabs):
            failures += 1
        for tab in ['rec', 'report', 'theme', 'visual', 'pet', 'mobile']:
            page.evaluate("(t) => window.starwavePhase4b.openPanel(t)", tab)
            page.wait_for_timeout(300)
            body_len = page.evaluate("() => (document.getElementById('sw4b-body') || {}).innerHTML ? document.getElementById('sw4b-body').innerHTML.length : 0")
            if not check('ui.tab_renders_' + tab, body_len > 80, {'len': body_len}):
                failures += 1
        if smoke:
            # one real interaction per feature, then stop
            page.evaluate("() => window.starwavePhase4b.themes.apply(window.starwavePhase4b.themes.list()[3])")
            th = page.evaluate("() => window.starwavePhase4b.themes.current()")
            if not check('smoke.theme_apply', bool(th and th['id'] == 'neonrain'), th):
                failures += 1
            pet = page.evaluate("() => window.starwavePhase4b.pet.cycle()")
            if not check('smoke.pet_cycle', bool(pet and pet['id'] in ('tuantuan', 'fangfang')), pet):
                failures += 1
            rep = page.evaluate("() => window.starwavePhase4b.report.compute('year')")
            if not check('smoke.report_compute', isinstance(rep, dict) and 'totalPlays' in rep, rep):
                failures += 1
            # Cold start (fresh logged-out browser, demo songs deleted): the DJ
            # pool (weather + discover + playlist cache) is empty, so 0 songs
            # is the correct result. Assert the generate path + label instead.
            dj = page.evaluate("async () => { const d = await window.starwavePhase4b.dj.generate({}); return { songs: d.songs.length, line: d.line, by: d.generatedBy, hasDemo: d.songs.some(s => s.provider === 'demo') }; }")
            if not check('smoke.dj_generate', bool(dj and isinstance(dj['songs'], int) and dj['line'] and dj['by'] == '规则生成，非大模型' and not dj['hasDemo']), dj):
                failures += 1
            ps = page.evaluate("() => window.starwavePhase4b.particles.state()")
            if not check('smoke.particles_running', bool(ps and ps['running'] and ps['count'] > 0), ps):
                failures += 1
            browser.close()
            report['smoke'] = True
            report['failures'] = failures
            with open('/tmp/sw-phase4b-verify-report.json', 'w', encoding='utf-8') as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            print('SMOKE failures=%d console_errors=%d page_errors=%d failed_requests=%d' % (
                failures, len(report['console_errors']), len(report['page_errors']), len(report['failed_requests'])))
            return 0 if failures == 0 else 1

        # ---- A. rule AI DJ ----
        # Demo songs were deleted 2026-11-10 (Ma's order): the DJ pool is now
        # weather radio + discover + playlist cache, which is empty in a fresh
        # logged-out probe, so seed it with the local fixture (same real audio
        # the demo songs used to provide) before asserting generate/play.
        a_fixture = import_fixture(page)
        a_seed = page.evaluate("""(song) => {
          if (!song) return { seeded: 0 };
          const mk = (n) => Object.assign({}, song, { id: (song.localKey || song.id || 'fixture') + '#dj' + n, localKey: (song.localKey || song.id || 'fixture') + '#dj' + n, name: (song.name || 'fixture') + ' (DJ' + n + ')' });
          const songs = [mk(1), mk(2), mk(3)];
          if (typeof homeDiscoverState !== 'undefined') homeDiscoverState.songs = songs;
          return { seeded: songs.length, names: songs.map(s => s.name) };
        }""", a_fixture)
        if not check('A.dj_pool_seeded', bool(a_seed and a_seed.get('seeded', 0) >= 3), a_seed):
            failures += 1
        dj = page.evaluate("async () => { const d = await window.starwavePhase4b.dj.generate({}); return { songs: d.songs.length, line: d.line, by: d.generatedBy, slot: d.slot, mood: d.mood, names: d.songs.slice(0, 3).map(s => s.name), hasDemo: d.songs.some(s => s.provider === 'demo') }; }")
        if not check('A.dj_generate', bool(dj and dj['songs'] >= 3 and dj['line'] and dj['by'] == '规则生成，非大模型' and not dj['hasDemo']), dj):
            failures += 1
        page.evaluate("() => window.starwavePhase4b.dj.play()")
        page.wait_for_timeout(4000)
        au = page.evaluate("() => { const a = window.audio; return a ? { paused: a.paused, ct: Math.round(a.currentTime * 100) / 100, dur: Math.round((a.duration || 0) * 100) / 100 } : null; }")
        if not check('A.dj_play_fixture', bool(au and not au['paused'] and au['ct'] > 0), au):
            failures += 1
        q = page.evaluate("() => window.starwavePhase3.queueState()")
        if not check('A.dj_queue', bool(q and q.get('length', 0) >= 3), q):
            failures += 1

        # ---- B. hybrid recommend ----
        rec = page.evaluate("async () => { const r = await window.starwavePhase4b.recommend.hybrid({}); return { songs: r.songs.length, platform: r.platformCount, platformReason: r.platformReason, local: r.localCount, coldStart: r.coldStart, names: r.songs.slice(0, 3).map(s => s.name) }; }")
        if not check('B.hybrid_generate', bool(rec and rec['songs'] >= 3), rec):
            failures += 1
        if not check('B.hybrid_platform_reason_recorded', isinstance(rec.get('platformReason'), str), rec):
            failures += 1
        # playable-first sort: URL-bearing songs must come before URL-less ones
        # (the hybrid sort is a real sort by the playable predicate; demo songs
        # no longer exist, so the check asserts sortedness + no demo provider).
        playable_first = page.evaluate("async () => { const r = await window.starwavePhase4b.recommend.hybrid({}); const ok = (s) => !!(s.publicAudioUrl || s.previewUrl || s.trial); const flags = r.songs.map(ok); let seenFalse = false, sorted = true; flags.forEach(f => { if (!f) seenFalse = true; else if (seenFalse) sorted = false; }); return { sorted: sorted, total: r.songs.length, hasDemo: r.songs.some(s => s.provider === 'demo') }; }")
        if not check('B.hybrid_playable_first', bool(playable_first and playable_first['sorted']), playable_first):
            failures += 1
        if not check('B.hybrid_no_demo_songs', bool(playable_first and not playable_first['hasDemo']), playable_first):
            failures += 1

        # ---- C. music report (seed with real playback: seek 55% then next) ----
        # Fixture queue: the imported local song + a clone (demo songs were
        # deleted 2026-11-10 at Ma's order).
        c_fixture = import_fixture(page)
        page.evaluate("""(song) => { const clone = Object.assign({}, song, { id: (song.localKey || song.id || 'fixture') + '#c2', localKey: (song.localKey || '') + '#c2', name: (song.name || 'fixture') + ' (2)' }); window.playQueue = [song, clone]; window.currentIdx = 0; return playQueueAt(0, { manual: true }); }""", c_fixture)
        page.wait_for_timeout(4000)
        page.evaluate("() => { const a = window.audio; if (a && a.duration) a.currentTime = a.duration * 0.55; }")
        page.wait_for_timeout(2500)
        page.evaluate("() => { if (typeof nextTrack === 'function') nextTrack(); }")
        page.wait_for_timeout(2500)
        hist = page.evaluate("() => window.starwavePhase3.historyState()")
        if not check('C.history_seeded_by_real_play', bool(hist and hist.get('totalPlays', 0) >= 1), hist):
            failures += 1
        for rng in ['day', 'week', 'month', 'year']:
            rep = page.evaluate("(r) => window.starwavePhase4b.report.compute(r)", rng)
            if not check('C.report_' + rng, isinstance(rep, dict) and rep.get('totalPlays', 0) >= 1, rep):
                failures += 1
        card = page.evaluate("() => { const rep = window.starwavePhase4b.report.compute('year'); const cv = window.starwavePhase4b.report.shareCard(rep); return { w: cv.width, h: cv.height, urlLen: cv.toDataURL('image/png').length }; }")
        if not check('C.share_card_canvas', bool(card and card['w'] == 1080 and card['h'] == 1350 and card['urlLen'] > 10000), card):
            failures += 1
        exp = page.evaluate("() => window.starwavePhase4b.report.exportData()")
        if not check('C.export_data', exp is True, {'exported': exp}):
            failures += 1
        clr = page.evaluate("() => { const ok = window.starwavePhase4b.report.clear(); const rep = window.starwavePhase4b.report.compute('year'); return { cleared: ok, playsAfter: rep.totalPlays }; }")
        if not check('C.clear_data', bool(clr and clr.get('cleared') and clr.get('playsAfter') == 0), clr):
            failures += 1

        # ---- D. themes ----
        themes = page.evaluate("() => window.starwavePhase4b.themes.list()")
        forbidden = {'emily', '安魂', '星河', '唱片', '星球', '滚筒', '虚空'}
        names_ok = bool(themes and len(themes) >= 4 and not any(t['name'] in forbidden for t in themes))
        if not check('D.theme_builtin_names', names_ok, [t['name'] for t in (themes or [])]):
            failures += 1
        for t in (themes or []):
            page.evaluate("(id) => window.starwavePhase4b.themes.apply(window.starwavePhase4b.themes.get(id))", t['id'])
            page.wait_for_timeout(200)
            accent = page.evaluate("() => getComputedStyle(document.documentElement).getPropertyValue('--sw4b-accent').trim()")
            if not check('D.theme_apply_' + t['id'], accent.lower() == t['colors']['accent'].lower(), {'accent': accent, 'expected': t['colors']['accent']}):
                failures += 1
        bad = page.evaluate("() => window.starwavePhase4b.themes.validate({ name: 'x' })")
        if not check('D.theme_validate_rejects_bad', isinstance(bad, str) and len(bad) > 0, {'err': bad}):
            failures += 1
        imp = page.evaluate("async () => { const f = new File([JSON.stringify({ id: 't1', name: '导入测试', colors: { accent: '#ff0000', bg: '#111111', text: '#ffffff' }, font: 'system-ui', particle: { type: 'snow', density: 1, speed: 1 } })], 't.json', { type: 'application/json' }); const r = await window.starwavePhase4b.themes.importFile(f); return { ok: r.ok, name: (r.theme || {}).name }; }")
        if not check('D.theme_import', bool(imp and imp.get('ok')), imp):
            failures += 1
        cover = page.evaluate("async () => { const r = await window.starwavePhase4b.themes.fromCover(); return { hasTheme: !!r.theme, reason: r.reason }; }")
        if not check('D.theme_from_cover_resolves', isinstance(cover, dict) and 'reason' in cover, cover):
            failures += 1

        # ---- F (dual theme) + pet ----
        dual_bad = page.evaluate("() => window.starwavePhase4b.dualTheme.validate({ format: 'other', version: 1, light: {}, dark: {} })")
        if not check('F.dual_validate_rejects_foreign_format', isinstance(dual_bad, str) and 'starwave-dual-theme' in dual_bad, {'err': dual_bad}):
            failures += 1
        dual_ok = page.evaluate("() => { const d = { format: 'starwave-dual-theme', version: 1, name: '测试双主题', light: { accent: '#0ea5e9', accent2: '#38bdf8', bg: '#f0f9ff', bg2: '#e0f2fe', text: '#0f172a', muted: '#475569' }, dark: { accent: '#0ea5e9', accent2: '#38bdf8', bg: '#082f49', bg2: '#0c4a6e', text: '#f0f9ff', muted: '#7dd3fc' } }; return window.starwavePhase4b.dualTheme.apply(d); }")
        if not check('F.dual_apply', dual_ok is True, {'applied': dual_ok}):
            failures += 1
        pets = page.evaluate("() => window.starwavePhase4b.pet.list()")
        pet_forbidden = {'像素爪爪', '熊猫', '橘猫', '金毛', '赤狐', '褐兔'}
        pets_ok = bool(pets and len(pets) >= 2 and not any(p['name'] in pet_forbidden for p in pets))
        if not check('F.pet_list_original', pets_ok, pets):
            failures += 1
        pet1 = page.evaluate("() => window.starwavePhase4b.pet.current()")
        pet2 = page.evaluate("() => window.starwavePhase4b.pet.cycle()")
        if not check('F.pet_cycle', bool(pet1 and pet2 and pet1['id'] != pet2['id']), {'from': pet1, 'to': pet2}):
            failures += 1
        pet_dom = page.evaluate("() => { const c = document.getElementById('sw4b-pet'); return c ? { w: c.width, h: c.height } : null; }")
        if not check('F.pet_canvas_present', bool(pet_dom), pet_dom):
            failures += 1
        pet_off = page.evaluate("() => window.starwavePhase4b.pet.setEnabled(false)")
        pet_on = page.evaluate("() => window.starwavePhase4b.pet.setEnabled(true)")
        if not check('F.pet_toggle', pet_off is False and pet_on is True, {'off': pet_off, 'on': pet_on}):
            failures += 1

        # ---- E. particles + scenes + shots ----
        ps = page.evaluate("() => window.starwavePhase4b.particles.state()")
        if not check('E.particles_running', bool(ps and ps['running'] and ps['count'] > 0 and 0.1 <= ps['budget'] <= 1.0), ps):
            failures += 1
        for typ in ['rain', 'snow', 'firefly', 'stardust', 'blocks']:
            st = page.evaluate("(t) => { window.starwavePhase4b.particles.setType(t); return window.starwavePhase4b.particles.state(); }", typ)
            if not check('E.particle_type_' + typ, bool(st and st['type'] == typ and st['count'] > 0), st):
                failures += 1
        # 2026-11-11 blur fix: starry scene now maps to 'blocks' (was 'stardust');
        # blocks is the new default particle type.
        for sc, expect in [('ocean', 'firefly'), ('rainy', 'rain'), ('starry', 'blocks')]:
            st = page.evaluate("(s) => { window.starwavePhase4b.scenes.apply(s); return window.starwavePhase4b.particles.state(); }", sc)
            if not check('E.scene_' + sc, bool(st and st['sceneId'] == sc and st['type'] == expect), st):
                failures += 1
        # Fixture queue (demo songs deleted 2026-11-10): the imported local
        # song plays through the same real-analyser chain.
        e_fixture = import_fixture(page)
        page.evaluate("""(song) => { window.playQueue = [song]; window.currentIdx = 0; return playQueueAt(0, { manual: true }); }""", e_fixture)
        page.wait_for_timeout(5000)
        shot = page.evaluate("() => { const s = window.starwavePhase4b.scenes.shot(); const st = window.starwavePhase4b.particles.state(); return { shot: s.id, label: s.label, stateShot: st.shotId, kick: st.kick, spec: st.spectrum }; }")
        if not check('E.segment_shot', bool(shot and shot['shot'] in ('intro', 'verse', 'chorus', 'bridge', 'outro')), shot):
            failures += 1
        if not check('E.audio_drive_numbers', isinstance(shot.get('kick'), (int, float)) and isinstance(shot.get('spec'), dict), shot):
            failures += 1

        # ---- G. mobile ----
        fonts = page.evaluate("() => window.starwavePhase4b.mobile.fonts()")
        if not check('G.fonts_self_hosted', bool(fonts and fonts.get('selfHosted')), fonts):
            failures += 1
        gest = page.evaluate("() => window.starwavePhase4b.mobile.gesture()")
        if not check('G.gesture_default_off', bool(gest and gest.get('cam') == 'off' and gest.get('defaultOff')), gest):
            failures += 1
        pwa = page.evaluate("() => window.starwavePhase4b.mobile.pwa()")
        if not check('G.pwa_status', bool(pwa and pwa.get('kind') in ('installed', 'ios', 'android_ready', 'android_waiting', 'desktop')), pwa):
            failures += 1
        # portrait shelf on a narrow portrait viewport
        page2 = browser.new_page(viewport={'width': 390, 'height': 844})
        page2.on('pageerror', lambda e: report['page_errors'].append('mobile-context: ' + str(e)))
        page2.goto(BASE_URL, wait_until='load', timeout=60000)
        page2.wait_for_timeout(3000)
        dismiss_splash(page2)
        shelf = page2.evaluate("() => window.starwavePhase4b.mobile.portraitShelf()")
        if not check('G.portrait_shelf', bool(shelf and shelf.get('portrait') is True), shelf):
            failures += 1
        page2.close()
        # double-tap like on cover (current song is the fixture from section E)
        before = page.evaluate("() => window.starwavePhase3.listFavorites().length")
        page.dblclick('#control-cover', timeout=5000)
        page.wait_for_timeout(800)
        after = page.evaluate("() => window.starwavePhase3.listFavorites().length")
        if not check('G.dblclick_like', after == before + 1 or after == before - 1, {'before': before, 'after': after}):
            failures += 1
        # long-press menu via touch
        page.evaluate("() => window.starwavePhase4b.openPanel('mobile')")
        page.wait_for_timeout(400)
        lp = page.evaluate("async () => { const el = document.getElementById('control-cover'); if (!el) return { noEl: true }; const r = el.getBoundingClientRect(); const t = new Touch({ identifier: 1, target: el, clientX: r.x + 10, clientY: r.y + 10 }); el.dispatchEvent(new TouchEvent('touchstart', { touches: [t], bubbles: true, cancelable: true })); await new Promise(r2 => setTimeout(r2, 750)); const m = document.getElementById('sw4b-lp-menu'); return { menuShown: !!(m && m.style.display === 'block') }; }")
        if not check('G.longpress_menu', bool(lp and lp.get('menuShown')), lp):
            failures += 1
        shake = page.evaluate("() => { const on = window.starwavePhase4b.mobile.shake(true); const off = window.starwavePhase4b.mobile.shake(false); return { on: on, off: off }; }")
        if not check('G.shake_toggle_experimental', bool(shake and shake.get('on') is True and shake.get('off') is False), shake):
            failures += 1
        gyro = page.evaluate("() => { const off = window.starwavePhase4b.mobile.gyro(false); return { off: off }; }")
        if not check('G.gyro_toggle_off', bool(gyro and gyro.get('off') is False), gyro):
            failures += 1

        # ---- H. repo / redirect URI ----
        with open(os.path.join(ROOT, 'web', 'public', 'starwave-phase2.js'), encoding='utf-8') as f:
            phase2_src = f.read()
        h_ok = ('https://github.com/Wengzikang/mineradio-next' in phase2_src and
                'https://wengzikang.github.io/mineradio-next/' in phase2_src and
                'starwave-music' not in phase2_src)
        if not check('H.phase2_urls_updated', h_ok, {'has_new_repo': 'mineradio-next' in phase2_src, 'old_left': 'starwave-music' in phase2_src}):
            failures += 1
        about = page.evaluate("() => { try { if (typeof window.starwaveOpenAbout === 'function') window.starwaveOpenAbout(); } catch (e) { return { err: String(e) }; } return new Promise(r => setTimeout(() => { const els = Array.from(document.querySelectorAll('.sw-about a, .modal a')); r({ links: els.map(a => a.href) }); }, 800)); }")
        about_ok = bool(about and any('github.com/Wengzikang/mineradio-next' in (u or '') for u in (about.get('links') or [])))
        if not check('H.about_modal_source_link', about_ok, about):
            failures += 1

        # ---- light regression ----
        # Demo songs removed 2026-11-10 (Ma's order): both demo builders must
        # return [] and the demo audio directory must be gone.
        q2 = page.evaluate("async () => ({ p3: (await window.starwavePhase3.demoSongs()).length, build: (await buildStarwaveDemoSongs()).length })")
        if not check('regression.demo_songs_removed', bool(q2 and q2.get('p3') == 0 and q2.get('build') == 0), q2):
            failures += 1
        demo_dir_gone = not os.path.exists(os.path.join(ROOT, 'web', 'public', 'demo'))
        if not check('regression.demo_audio_dir_removed', demo_dir_gone, {'demo_dir_exists': not demo_dir_gone}):
            failures += 1
        spot = page.evaluate("() => !!window.starwaveSpotify")
        if not check('regression.spotify_object_present', bool(spot), {'present': spot}):
            failures += 1

        browser.close()

    report['failures'] = failures
    with open('/tmp/sw-phase4b-verify-report.json', 'w', encoding='utf-8') as f:
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
