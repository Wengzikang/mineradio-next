# -*- coding: utf-8 -*-
"""StarWave Phase 2 verification (real browser, real network).
Serves web/public via python http.server on 127.0.0.1:4173 and drives it with Playwright.
Checks:
  (a) page load: 0 uncaught errors / console errors (Phase 2 files loaded)
  (b) 8 views open: home, search, lyrics stage, shelf/playlist panel,
      playlist detail, DIY console, listening profile, settings/about
  (c) fixture track plays (demo songs were deleted 2026-11-10 at Ma's order;
      the generated local mp3 fixture is imported and played instead)
  (d) netease search + free track play / login prompt
  (e) Spotify login button opens auth URL with client_id, redirect_uri,
      scope, code_challenge, code_challenge_method=S256, state; verifier in localStorage
  (f) Spotify redirect drain with a fake code fails cleanly (no crash)
  (g) private radio builds a real queue, plays, next changes track
  (h) mobile viewport 390x844: no horizontal overflow, swipe changes track,
      Media Session metadata set
  (i) perf governor manual mode works; auto mode present
  (j) Apple Music framework returns pending_auth; no token anywhere
  (k) secret scan over web/public
Usage: ~/workspace/.venv-playwright/bin/python scripts/verify-phase2.py
The http server must already be running (python3 -m http.server 4173 -d web/public).
"""
import json
import os
import re
import socket
import subprocess
import sys
import time
import urllib.parse

from playwright.sync_api import sync_playwright

RELAY_PORT = 18082
RELAY_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'verify-relay-proxy.py')
BASE_URL = 'http://127.0.0.1:4173/'
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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


report = {'console_errors': [], 'page_errors': [], 'failed_requests': []}


def audio_state(page):
    return page.evaluate(
        """() => {
          const a = window.audio;
          if (!a) return { exists: false };
          return { exists: true, paused: a.paused, currentTime: a.currentTime,
                   duration: a.duration, src: (a.src || '').slice(0, 120) };
        }""")


LOCAL_MP3 = '/tmp/sw-local-test.mp3'


def prepare_test_files():
    """(Re)generate the deterministic fixture mp3 in /tmp (same file as
    verify-phase3.py; the demo songs were deleted 2026-11-10 at Ma's order,
    so playback steps use this fixture instead)."""
    r = subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
                        '-f', 'lavfi', '-i', 'anoisesrc=color=white:duration=30',
                        '-codec:a', 'libmp3lame', '-q:a', '4', LOCAL_MP3],
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError('ffmpeg failed to generate LOCAL_MP3: ' + (r.stderr or ''))


def import_fixture(page):
    """Import the generated MP3 fixture as a local file and return the
    imported song object (blob URL). Playing a local file with no cached
    beat map opens the local-beat analysis modal, so close it (it would
    block later pointer actions)."""
    page.set_input_files('#file-input', LOCAL_MP3)
    page.wait_for_timeout(4000)
    page.evaluate("() => { try { if (typeof closeLocalBeatModal === 'function') closeLocalBeatModal(); } catch (e) {} }")
    page.wait_for_timeout(500)
    modal_open = page.evaluate("() => { const m = document.getElementById('local-beat-modal'); return !!(m && m.classList.contains('show')); }")
    if modal_open:
        page.keyboard.press('Escape')
        page.wait_for_timeout(500)
    return page.evaluate("() => { const s = window.currentLocalSong || (window.playQueue && window.playQueue[0]) || null; return s ? { name: s.name, id: s.id, localKey: s.localKey, publicAudioUrl: s.publicAudioUrl, previewUrl: s.previewUrl, provider: s.provider, type: s.type } : null; }")


def toast_text(page):
    return page.evaluate(
        "() => { const t = document.getElementById('toast');"
        " return t ? (t.textContent || '').trim() : ''; }")


def secret_scan():
    bad = []
    pats = [
        (r'client_secret', 'client_secret literal'),
        (r'github_pat_', 'github PAT'),
        (r'spade_a', 'qishui spade_a'),
        (r'KUGOU_(ANDROID|H5)_SALT|KUGOU_SIGN_KEY_SALT', 'kugou signing salt'),
        (r'KUWO_SECRET', 'kuwo secret'),
        (r'decryptSpadeA|TrackDecryptor', 'qishui decryptor'),
        (r'api\.music\.apple\.com.*developer.?token|developerToken\s*[:=]\s*[\'"][A-Za-z0-9]',
         'apple developer token'),
    ]
    for dirpath, _dirs, files in os.walk(os.path.join(ROOT, 'web', 'public')):
        for fn in files:
            if fn.endswith(('.js', '.html', '.json')) and 'vendor' not in dirpath:
                path = os.path.join(dirpath, fn)
                text = open(path, encoding='utf-8', errors='ignore').read()
                for pat, label in pats:
                    if re.search(pat, text):
                        bad.append('%s: %s' % (os.path.relpath(path, ROOT), label))
    return bad


def main():
    prepare_test_files()
    report['secret_scan'] = secret_scan()
    with sync_playwright() as pw:
        relay_proc = ensure_relay()
        proxy_cfg = {'server': 'http://127.0.0.1:%d' % RELAY_PORT,
                     'bypass': 'localhost,127.0.0.1,::1'}
        browser = pw.chromium.launch(
            args=['--autoplay-policy=no-user-gesture-required', '--ignore-certificate-errors'],
            proxy=proxy_cfg)
        page = browser.new_page(viewport={'width': 1280, 'height': 900})
        page.on('console', lambda m: report['console_errors'].append(m.text)
                if m.type == 'error' else None)
        page.on('pageerror', lambda e: report['page_errors'].append(str(e)))
        page.on('requestfailed', lambda r: report['failed_requests'].append(
            r.url + ' :: ' + (r.failure or '')))

        print('== (a) load')
        page.goto(BASE_URL, wait_until='load', timeout=60000)
        page.wait_for_timeout(2000)
        try:
            page.wait_for_selector('#splash.ready', state='attached', timeout=30000)
            page.click('#splash', timeout=5000)
        except Exception:
            page.evaluate("() => { if (typeof dismissSplash === 'function') dismissSplash(); }")
        page.wait_for_timeout(1200)
        print('phase2 globals:',
              page.evaluate("() => ({ spotify: typeof window.starwaveSpotify,"
                            " apple: typeof window.starwaveAppleMusic,"
                            " radio: typeof window.starwaveRadio,"
                            " governor: typeof window.starwavePerfGovernor,"
                            " about: typeof window.starwaveOpenAbout })"))
        report['phase2_globals'] = page.evaluate(
            "() => ({ spotify: typeof window.starwaveSpotify, apple: typeof window.starwaveAppleMusic,"
            " radio: typeof window.starwaveRadio, governor: typeof window.starwavePerfGovernor,"
            " about: typeof window.starwaveOpenAbout })")
        print('about button present:',
              page.evaluate("() => !!document.getElementById('starwave-about-btn')"))
        print('radio home card present:',
              page.evaluate("() => !!document.getElementById('starwave-radio-card')"))
        print('spotify login btn in login modal:',
              page.evaluate("() => !!document.getElementById('starwave-spotify-login-btn')"))
        report['phase2_dom'] = page.evaluate(
            "() => ({ aboutBtn: !!document.getElementById('starwave-about-btn'),"
            " radioCard: !!document.getElementById('starwave-radio-card'),"
            " spotifyLoginBtn: !!document.getElementById('starwave-spotify-login-btn'),"
            " cookiePanelHidden: (() => { const el = document.getElementById('qq-cookie-panel');"
            "   return el ? getComputedStyle(el).display : 'missing'; })() })")

        print('== (b) 8 views')
        views = {}
        # 1 home
        page.evaluate("() => { if (typeof loadHomeDiscover === 'function') loadHomeDiscover(true); }")
        try:
            page.wait_for_selector('#home-preview-list .home-preview-track', state='attached', timeout=20000)
            views['home'] = True
        except Exception:
            views['home'] = False
        # 2 search
        page.fill('#search-input', '周杰伦')
        page.press('#search-input', 'Enter')
        try:
            page.wait_for_selector('#search-results .search-result', state='attached', timeout=30000)
            views['search'] = page.locator('#search-results .search-result').count()
        except Exception as e:
            views['search'] = 'FAIL: %s' % e
        page.screenshot(path='/tmp/sw-v2-search.png')
        # 3 lyrics stage: play the fixture (demo songs deleted 2026-11-10),
        # open lyrics panel (the fixture has no lyrics, so lyricLines is 0)
        try:
            fixture = import_fixture(page)
            page.evaluate("(song) => { if (!song) return; window.playQueue = [song]; window.currentIdx = 0; return playQueueAt(0, { manual: true }); }", fixture)
            page.wait_for_timeout(4000)
            st = audio_state(page)
            views['fixture_playing'] = bool(st.get('exists') and not st.get('paused'))
            views['fixture_src'] = st.get('src', '')
        except Exception as e:
            views['fixture_playing'] = 'FAIL: %s' % e
        page.evaluate("() => { if (typeof toggleLyricsPanel === 'function') toggleLyricsPanel(true); }")
        page.wait_for_timeout(800)
        views['lyrics_stage'] = page.evaluate(
            """() => { const s = document.getElementById('stage-lyrics');
              const p = document.getElementById('lyrics-panel');
              return { stageExists: !!s, stageChildren: s ? s.children.length : 0,
                       panelVisible: p ? getComputedStyle(p).display !== 'none' : 'no-panel',
                       lyricLines: (window.originalLyricsState || {}).lines
                         ? window.originalLyricsState.lines.length : 0 }; }""")
        page.screenshot(path='/tmp/sw-v2-lyrics.png')
        page.evaluate("() => { if (typeof toggleLyricsPanel === 'function') toggleLyricsPanel(false); }")
        # 4 shelf / playlist panel
        page.evaluate("() => { if (typeof togglePlaylistPanel === 'function') togglePlaylistPanel(true); }")
        page.wait_for_timeout(900)
        views['shelf_panel'] = page.evaluate(
            "() => { const p = document.getElementById('playlist-panel');"
            " return p ? getComputedStyle(p).opacity : 'missing'; }")
        page.screenshot(path='/tmp/sw-v2-panel.png')
        # 5 playlist detail
        views['playlist_detail'] = page.evaluate(
            """() => {
              const cards = document.querySelectorAll('#playlist-panel [data-playlist-title], #playlist-panel .playlist-card');
              if (cards.length) { cards[0].click(); return 'cards:' + cards.length; }
              return 'no-cards'; }""")
        page.wait_for_timeout(900)
        page.evaluate("() => { if (typeof togglePlaylistPanel === 'function') togglePlaylistPanel(false); }")
        # 6 DIY console
        page.evaluate("() => { if (typeof openDiyRhythmConsole === 'function') openDiyRhythmConsole(); }")
        page.wait_for_timeout(1000)
        views['diy'] = page.evaluate(
            "() => { const p = document.getElementById('fx-panel');"
            " return { visible: p ? getComputedStyle(p).opacity : 'missing',"
            " toggles: document.querySelectorAll('#fx-panel .fx-toggle').length }; }")
        page.screenshot(path='/tmp/sw-v2-diy.png')
        page.evaluate("() => { if (typeof toggleFxPanel === 'function') toggleFxPanel(false); }")
        # 7 profile
        page.evaluate("() => { if (typeof openHomeInsight === 'function') openHomeInsight(); }")
        page.wait_for_timeout(800)
        views['profile'] = {'toast': toast_text(page),
                            'summary': page.evaluate("() => { try { return homeListenSummary(); } catch (e) { return String(e); } }")}
        # 8 settings/about
        page.evaluate("() => window.starwaveOpenAbout()")
        page.wait_for_timeout(800)
        views['settings'] = page.evaluate(
            """() => { const m = document.getElementById('starwave-about-modal');
              return { shown: m ? m.classList.contains('show') : false,
                       sourceLink: !!document.querySelector('#starwave-about-modal a[href*="Wengzikang/starwave-music"]'),
                       text: m ? m.textContent.slice(0, 400) : '' }; }""")
        page.screenshot(path='/tmp/sw-v2-about.png')
        page.evaluate("() => window.starwaveCloseAbout()")
        print(json.dumps(views, ensure_ascii=False, indent=1))
        report['views'] = views

        print('== (d) netease search meta + play')
        page.fill('#search-input', '周杰伦')
        page.press('#search-input', 'Enter')
        try:
            page.wait_for_selector('#search-results .search-result', state='attached', timeout=30000)
        except Exception:
            pass
        page.wait_for_timeout(1000)
        metas = page.evaluate(
            """() => Array.from(document.querySelectorAll('#search-results .search-result'))
               .slice(0, 8).map(el => ({
                 title: (el.querySelector('.search-result-title')||{}).textContent.trim().slice(0, 40),
                 meta: (el.querySelector('.search-result-meta')||{}).textContent.trim(),
                 tag: (el.querySelector('.tag-source')||{}).textContent.trim(),
                 vip: !!el.querySelector('.tag-vip') }))""")
        print(json.dumps(metas, ensure_ascii=False, indent=1))
        report['netease_metas'] = metas
        report['netease_label_ok'] = any('非官方社区服务' in (m['meta'] or '') for m in metas)

        print('== (e) Spotify auth URL')
        with page.expect_popup() as pop_info:
            page.evaluate("() => window.starwaveSpotify.login()")
        popup = pop_info.value
        popup.wait_for_load_state('domcontentloaded', timeout=30000)
        auth_url = popup.url
        print('auth url:', auth_url[:400])
        parsed = urllib.parse.urlparse(auth_url)
        qs = urllib.parse.parse_qs(parsed.query)
        report['spotify_auth'] = {
            'host': parsed.netloc, 'path': parsed.path,
            'client_id': qs.get('client_id', [''])[0],
            'redirect_uri': qs.get('redirect_uri', [''])[0],
            'scope': qs.get('scope', [''])[0],
            'code_challenge_method': qs.get('code_challenge_method', [''])[0],
            'has_code_challenge': bool(qs.get('code_challenge', [''])[0]),
            'has_state': bool(qs.get('state', [''])[0]),
            'response_type': qs.get('response_type', [''])[0],
        }
        report['spotify_verifier_in_localstorage'] = page.evaluate(
            "() => !!localStorage.getItem('starwave.spotify.pkce_verifier')")
        print(json.dumps(report['spotify_auth'], ensure_ascii=False, indent=1))
        print('verifier in localStorage:', report['spotify_verifier_in_localstorage'])
        popup.close()

        print('== (f) Spotify drain with fake code')
        page.evaluate(
            """() => {
              const st = localStorage.getItem('starwave.spotify.auth_state') || 'x';
              history.replaceState(null, '', '/?code=FAKECODE123&state=' + encodeURIComponent(st));
            }""")
        page.reload(wait_until='load', timeout=60000)
        page.wait_for_timeout(4000)
        try:
            page.wait_for_selector('#splash.ready', state='attached', timeout=30000)
            page.click('#splash', timeout=5000)
        except Exception:
            page.evaluate("() => { if (typeof dismissSplash === 'function') dismissSplash(); }")
        page.wait_for_timeout(3000)
        report['spotify_drain_fake_code'] = {
            'toast': toast_text(page),
            'logged_in': page.evaluate("() => window.starwaveSpotify.isLoggedIn()"),
            'url_cleaned': page.evaluate("() => !window.location.search.includes('FAKECODE123')"),
        }
        print(json.dumps(report['spotify_drain_fake_code'], ensure_ascii=False, indent=1))

        print('== (f2) Spotify drain with expired login (>10 min TTL)')
        # re-seed a login, then age its startedAt past the 10-min TTL
        with page.expect_popup() as pop2:
            page.evaluate("() => window.starwaveSpotify.login()")
        popup2 = pop2.value
        popup2.wait_for_load_state('domcontentloaded', timeout=30000)
        popup2.close()
        page.evaluate(
            "() => { localStorage.setItem('starwave.spotify.auth_started_at',"
            " String(Date.now() - 11 * 60 * 1000));"
            " const st = localStorage.getItem('starwave.spotify.auth_state') || 'x';"
            " history.replaceState(null, '', '/?code=FAKECODE456&state=' + encodeURIComponent(st)); }")
        page.reload(wait_until='load', timeout=60000)
        page.wait_for_timeout(3000)
        try:
            page.wait_for_selector('#splash.ready', state='attached', timeout=30000)
            page.click('#splash', timeout=5000)
        except Exception:
            page.evaluate("() => { if (typeof dismissSplash === 'function') dismissSplash(); }")
        page.wait_for_timeout(2000)
        report['spotify_drain_expired_ttl'] = {
            'toast': toast_text(page),
            'logged_in': page.evaluate("() => window.starwaveSpotify.isLoggedIn()"),
            'verifier_cleared': page.evaluate(
                "() => !localStorage.getItem('starwave.spotify.pkce_verifier')"),
            'ttl_ms': page.evaluate("() => window.starwaveSpotify.loginTtlMs"),
            'pending': page.evaluate("() => window.starwaveSpotify.pendingLogin()"),
        }
        print(json.dumps(report['spotify_drain_expired_ttl'], ensure_ascii=False, indent=1))

        print('== (g) private radio')
        page.evaluate("() => window.starwaveRadio.start('relax')")
        page.wait_for_timeout(12000)
        radio1 = page.evaluate(
            """() => ({ status: window.starwaveRadio.status(),
                       queueLen: (window.playQueue || []).length,
                       queueSources: (window.playQueue || []).slice(0, 20).map(s => s.provider || s.source),
                       current: (window.playQueue || [])[window.currentIdx]
                         ? { name: window.playQueue[window.currentIdx].name,
                             provider: window.playQueue[window.currentIdx].provider } : null,
                       chipVisible: (() => { const c = document.getElementById('starwave-radio-chip');
                         return c ? getComputedStyle(c).display : 'missing'; })() })""")
        print(json.dumps(radio1, ensure_ascii=False, indent=1))
        page.wait_for_timeout(3000)
        radio1_audio = audio_state(page)
        print('radio audio:', json.dumps(radio1_audio, ensure_ascii=False))
        first_track = radio1.get('current', {}).get('name') if radio1.get('current') else None
        page.evaluate("() => { if (typeof nextTrack === 'function') nextTrack(); }")
        page.wait_for_timeout(5000)
        radio2 = page.evaluate(
            "() => ({ current: (window.playQueue || [])[window.currentIdx]"
            " ? window.playQueue[window.currentIdx].name : null })")
        print('radio after next:', json.dumps(radio2, ensure_ascii=False))
        report['radio'] = {'start': radio1, 'audio': radio1_audio,
                           'first_track': first_track,
                           'after_next_track': radio2.get('current'),
                           'next_changed': bool(first_track and radio2.get('current')
                                               and radio2.get('current') != first_track)}
        page.evaluate("() => window.starwaveRadio.stop()")

        print('== (i) perf governor')
        report['governor'] = page.evaluate(
            """() => {
              const before = window.starwavePerfGovernor.tier;
              window.starwavePerfGovernor.setMode('eco');
              const eco = window.starwavePerfGovernor.tier;
              window.starwavePerfGovernor.setMode('auto');
              return { before: before, afterEco: eco, modeAfter: window.starwavePerfGovernor.mode,
                       fps: window.starwavePerfGovernor.fps }; }""")
        print(json.dumps(report['governor'], ensure_ascii=False, indent=1))

        print('== (j) Apple Music framework')
        report['apple'] = page.evaluate(
            """async () => {
              const r = await window.starwaveAppleMusic.searchCatalog('周杰伦');
              return { search: r, statusText: window.starwaveAppleMusic.statusText(),
                       musicKitLoaded: !!window.MusicKit }; }""")
        print(json.dumps(report['apple'], ensure_ascii=False, indent=1))

        print('== (h) mobile 390x844')
        mob = browser.new_page(viewport={'width': 390, 'height': 844})
        mob.on('pageerror', lambda e: report['page_errors'].append('mobile: ' + str(e)))
        mob.goto(BASE_URL, wait_until='load', timeout=60000)
        mob.wait_for_timeout(2000)
        try:
            mob.wait_for_selector('#splash.ready', state='attached', timeout=30000)
            mob.click('#splash', timeout=5000)
        except Exception:
            mob.evaluate("() => { if (typeof dismissSplash === 'function') dismissSplash(); }")
        mob.wait_for_timeout(1500)
        mob.evaluate("() => { if (typeof loadHomeDiscover === 'function') loadHomeDiscover(true); }")
        mob.wait_for_timeout(1500)
        # Play the fixture (demo songs deleted 2026-11-10); a 2-song queue so
        # the swipe can change the track.
        try:
            mob_fixture = import_fixture(mob)
            mob.evaluate("(song) => { if (!song) return; const clone = Object.assign({}, song, { id: (song.localKey || song.id || 'fixture') + '#m2', localKey: (song.localKey || '') + '#m2', name: (song.name || 'fixture') + ' (2)' }); window.playQueue = [song, clone]; window.currentIdx = 0; return playQueueAt(0, { manual: true }); }", mob_fixture)
            mob.wait_for_timeout(4000)
        except Exception as e:
            print('mobile fixture play fail:', e)
        mob_audio_before = audio_state(mob)
        mob_track_before = mob.evaluate("() => (window.playQueue[window.currentIdx]||{}).name || ''")
        # swipe left (next) via touchscreen tap/drag simulation
        try:
            mob.touchscreen.tap(195, 400)  # ensure focus, no-op tap
        except Exception:
            pass
        # dispatch synthetic touch events for a left swipe on the stage
        mob.evaluate(
            """() => {
              const t = new Touch({ identifier: 1, target: document.body, clientX: 300, clientY: 400 });
              const t2 = new Touch({ identifier: 1, target: document.body, clientX: 120, clientY: 405 });
              document.dispatchEvent(new TouchEvent('touchstart', { touches: [t], bubbles: true, cancelable: true }));
              document.dispatchEvent(new TouchEvent('touchend', { touches: [], changedTouches: [t2], bubbles: true, cancelable: true }));
            }""")
        mob.wait_for_timeout(5000)
        mob_track_after = mob.evaluate("() => (window.playQueue[window.currentIdx]||{}).name || ''")
        mob_audio_after = audio_state(mob)
        media = mob.evaluate(
            """() => {
              const ms = navigator.mediaSession;
              const md = ms ? ms.metadata : null;
              return { supported: !!ms, title: md ? md.title : null,
                       artist: md ? md.artist : null,
                       playbackState: ms ? ms.playbackState : null }; }""")
        overflow = mob.evaluate(
            "() => ({ scrollW: document.documentElement.scrollWidth, innerW: window.innerWidth,"
            " dvh: getComputedStyle(document.body).height })")
        mob.screenshot(path='/tmp/sw-v2-mobile.png')
        report['mobile'] = {'audio_before': mob_audio_before, 'audio_after': mob_audio_after,
                            'track_before': mob_track_before, 'track_after': mob_track_after,
                            'swipe_changed_track': bool(mob_track_before and mob_track_after
                                                        and mob_track_before != mob_track_after),
                            'media_session': media, 'overflow': overflow}
        print(json.dumps(report['mobile'], ensure_ascii=False, indent=1))
        mob.close()

        print('== (a) errors')
        print('console errors (%d):' % len(report['console_errors']))
        for e in report['console_errors']:
            print('  CONSOLE-ERROR:', e[:400])
        print('page errors (%d):' % len(report['page_errors']))
        for e in report['page_errors']:
            print('  PAGE-ERROR:', e[:400])
        print('failed requests (%d):' % len(report['failed_requests']))
        for e in report['failed_requests']:
            print('  REQ-FAIL:', e[:300])
        print('secret scan hits:', report['secret_scan'])
        browser.close()
        if relay_proc:
            relay_proc.terminate()

    with open('/tmp/sw-phase2-verify-report.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print('report written to /tmp/sw-phase2-verify-report.json')


if __name__ == '__main__':
    main()
