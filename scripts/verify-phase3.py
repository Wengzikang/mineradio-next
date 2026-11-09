# -*- coding: utf-8 -*-
"""StarWave Phase 3 verification (real browser, real network).
Serves web/public via python http.server on 127.0.0.1:4173 and drives it with Playwright.
Covers task items 1-8 + regression:
  1 playback chain: demo / local file / netease free / iTunes 30s / radio
  2 queue: add/move/remove/clear/modes/next-prev/resume-after-reload, panel render
  3 lyrics sync: line highlight vs currentTime (demo LRC), +/-0.5s offset step
  4 spectrum: dual Analyser real data (demo/local) + BPM/Kick; synthetic labelled for x-origin
  5 audio FX: volume, 3-band EQ (white-noise file, low band +12 vs -12)
  6 favorites: demo/local/netease-free favorite/unfavorite/list (no login gate)
  7 history: record (seek 55% + switch), view, clear
  8 playlists: local CRUD, detail page lists tracks; netease public import -> honest reason
  9 regression: build:web, spotify/apple globals, cookie login still disabled
Usage: ~/workspace/.venv-playwright/bin/python scripts/verify-phase3.py
Serves web/public via the Range-capable scripts/range-http-server.py on
127.0.0.1:4174 (plain `python -m http.server` ignores Range, which breaks
seeking); the relay scripts/verify-relay-proxy.py is used for external hosts.
"""
import json
import os
import re
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
NOISE_WAV = '/tmp/sw-noise.wav'
KICK_WAV = '/tmp/sw-kick90.wav'
LOCAL_MP3 = '/tmp/sw-local-test.mp3'

report = {'console_errors': [], 'page_errors': [], 'failed_requests': []}


def _port_open(port):
    s = socket.socket()
    try:
        s.connect(('127.0.0.1', port))
        s.close()
        return True
    except OSError:
        return False


def _kill_relays():
    # kill stale relay processes (pattern built dynamically so pkill never
    # matches this script's own command line)
    pat = 'verify' + '-relay-proxy.py'
    subprocess.run(['pkill', '-f', pat], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(20):
        if not _port_open(RELAY_PORT):
            return
        time.sleep(0.2)


def _relay_probe_ok():
    """True if a real HTTPS fetch works through the relay (it can wedge
    after a crashed run; a wedged relay answers CONNECT with nothing)."""
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
        if _port_open(RANGE_PORT):
            return proc
        time.sleep(0.2)
    raise RuntimeError('range server did not start')


def audio_state(page):
    return page.evaluate(
        """() => {
          const a = window.audio;
          if (!a) return { exists: false };
          return { exists: true, paused: a.paused, currentTime: Math.round(a.currentTime*100)/100,
                   duration: Math.round((a.duration||0)*100)/100, src: (a.src || '').slice(0, 120),
                   volume: a.volume };
        }""")


def toast_text(page):
    return page.evaluate(
        "() => { const t = document.getElementById('toast');"
        " return t ? (t.textContent || '').trim() : ''; }")


def dismiss_splash(page):
    page.wait_for_timeout(1200)
    try:
        page.wait_for_selector('#splash.ready', state='attached', timeout=30000)
        page.click('#splash', timeout=5000)
    except Exception:
        page.evaluate("() => { if (typeof dismissSplash === 'function') dismissSplash(); }")
    page.wait_for_timeout(1200)


def play_demos(page):
    """Put the 6 demo songs in the queue and play idx 0. Returns queue state."""
    page.evaluate(
        """async () => {
          const songs = await window.starwavePhase3.demoSongs();
          window.playQueue = songs;
          window.currentIdx = 0;
          await playQueueAt(0, { manual: true });
          return songs.length;
        }""")
    page.wait_for_timeout(4000)
    return page.evaluate("() => window.starwavePhase3.queueState()")


def lrc_expected(lrc_path, t):
    """Expected lyric line index at time t from a .lrc file (same rule as tickLyricsParticles)."""
    times = []
    with open(lrc_path, encoding='utf-8', errors='ignore') as f:
        for line in f:
            m = re.match(r'\[(\d+):(\d+)\.(\d+)\]', line)
            if m:
                times.append(int(m.group(1)) * 60 + int(m.group(2)) + int(m.group(3)) / 100.0)
    idx = -1
    for i, ts in enumerate(times):
        if ts <= t + 0.05:
            idx = i
        else:
            break
    return idx, len(times)


def prepare_test_files():
    """(Re)generate deterministic test audio in /tmp (lost on VM restart)."""
    import math
    import random
    import shutil
    import struct
    import wave
    sr = 44100
    # white noise, 8 s (EQ band test)
    random.seed(7)
    w = wave.open(NOISE_WAV, 'wb')
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
    frames = bytearray()
    for _ in range(sr * 8):
        frames += struct.pack('<h', int(random.uniform(-1, 1) * 12000))
    w.writeframes(bytes(frames)); w.close()
    # 90 BPM kick (55 Hz sine bursts, 0.45 s decay), 18 s
    period = 60.0 / 90
    w = wave.open(KICK_WAV, 'wb')
    w.setnchannels(1); w.setsampwidth(2); w.setframerate(sr)
    frames = bytearray()
    for i in range(int(sr * 18)):
        t = i / sr
        ph = t % period
        env = math.exp(-ph * 9.0) if ph < 0.6 else 0.0
        v = math.sin(2 * math.pi * 55 * t) * env * 0.9
        frames += struct.pack('<h', int(max(-1, min(1, v)) * 30000))
    w.writeframes(bytes(frames)); w.close()
    # a renamed demo copy, treated as a plain local file on import
    shutil.copyfile(os.path.join(ROOT, 'web', 'public', 'demo', 'sakura.mp3'), LOCAL_MP3)


def main():
    prepare_test_files()
    relay_proc = ensure_relay()
    range_proc = ensure_range_server()
    with sync_playwright() as pw:
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

        print('== (0) load')
        page.goto(BASE_URL, wait_until='load', timeout=60000)
        dismiss_splash(page)
        report['phase3'] = page.evaluate(
            "() => ({ type: typeof window.starwavePhase3, version: window.starwavePhase3 && window.starwavePhase3.version,"
            " btn: !!document.getElementById('starwave-phase3-btn'),"
            " spotify: typeof window.starwaveSpotify, apple: typeof window.starwaveAppleMusic,"
            " radio: typeof window.starwaveRadio })")
        print(json.dumps(report['phase3'], ensure_ascii=False))
        page.evaluate("() => window.starwavePhase3.clearHistory()")
        page.wait_for_timeout(500)

        print('== (1a) demo play + spectrum')
        qs = play_demos(page)
        st = audio_state(page)
        print('demo queue:', json.dumps(qs, ensure_ascii=False), 'audio:', json.dumps(st, ensure_ascii=False))
        report['demo_play'] = {'queue': qs, 'audio': st}
        s1 = page.evaluate("() => window.starwavePhase3.spectrumSample()")
        page.wait_for_timeout(1500)
        s2 = page.evaluate("() => window.starwavePhase3.spectrumSample()")
        beat = page.evaluate("() => window.starwavePhase3.beatInfo()")
        print('spectrum1:', json.dumps({k: s1[k] for k in ('mode', 'max', 'mean', 'low', 'mid', 'high')}, ensure_ascii=False))
        print('spectrum2:', json.dumps({k: s2[k] for k in ('mode', 'max', 'mean', 'low', 'mid', 'high')}, ensure_ascii=False))
        print('beat:', json.dumps(beat, ensure_ascii=False))
        report['spectrum_demo'] = {'s1': s1, 's2': s2, 'beat': beat,
                                   'changed': s1.get('bins') != s2.get('bins')}
        # let kick onsets accumulate a bit longer for BPM
        page.wait_for_timeout(6000)
        beat2 = page.evaluate("() => window.starwavePhase3.beatInfo()")
        print('beat after +6s:', json.dumps(beat2, ensure_ascii=False))
        report['spectrum_demo']['beat_late'] = beat2

        print('== (3) lyrics sync (sakura LRC)')
        page.evaluate("() => { if (typeof toggleLyricsPanel === 'function') toggleLyricsPanel(true); }")
        try:
            page.wait_for_function("() => (window.lyricsLines || []).length >= 10", timeout=15000)
        except Exception as e:
            print('lyrics wait fail:', e)
        print('lyric lines:', page.evaluate("() => ({ n: (window.lyricsLines||[]).length, src: window.lyricsTimingSource })"))
        lyric_checks = []
        for seek_t in (20, 40):
            page.evaluate("() => { const a = window.audio; a.currentTime = %s; }" % seek_t)
            page.wait_for_timeout(3000)
            ls = page.evaluate("() => window.starwavePhase3.lyricState()")
            exp_idx, total = lrc_expected(os.path.join(ROOT, 'web', 'public', 'demo', 'sakura.lrc'), seek_t)
            print('seek', seek_t, 'lyricState:', json.dumps(ls, ensure_ascii=False), 'expected_idx:', exp_idx)
            lyric_checks.append({'seek': seek_t, 'state': ls, 'expected_idx': exp_idx, 'total': total})
        # offset step: pause just before line 2 (33.23s); +0.5s must move expected line 1 -> 2
        page.evaluate("() => { const a = window.audio; a.pause(); a.currentTime = 33.0; }")
        page.wait_for_timeout(800)
        ls0 = page.evaluate("() => window.starwavePhase3.lyricState()")
        off = page.evaluate("() => window.starwavePhase3.setLyricOffsetMs(500)")
        ls1 = page.evaluate("() => window.starwavePhase3.lyricState()")
        page.evaluate("() => { const a = window.audio; a.play(); }")
        page.wait_for_timeout(2500)
        ls1_live = page.evaluate("() => window.starwavePhase3.lyricState()")
        off_back = page.evaluate("() => window.starwavePhase3.setLyricOffsetMs(0)")
        print('offset paused@33.0:', json.dumps(ls0, ensure_ascii=False), '-> +500ms:', off, json.dumps(ls1, ensure_ascii=False),
              'live after resume:', json.dumps(ls1_live, ensure_ascii=False), 'back:', off_back)
        report['lyrics'] = {'checks': lyric_checks,
                            'offset_test': {'paused_at33_offset0': ls0, 'set_ms': off, 'paused_at33_offset500': ls1,
                                            'live_after_resume': ls1_live, 'reset_ms': off_back}}

        print('== (5) volume + EQ (white noise local file for deterministic bands)')
        vol = page.evaluate("() => window.starwavePhase3.setVolume(0.5)")
        print('volume after set 0.5:', json.dumps(vol, ensure_ascii=False))
        report['volume'] = vol
        # import white-noise wav as a local file, play it (native analyser path)
        page.set_input_files('#file-input', NOISE_WAV)
        page.wait_for_timeout(4000)
        local_st = audio_state(page)
        local_q = page.evaluate("() => window.starwavePhase3.queueState()")
        local_mode = page.evaluate("() => window.starwavePhase3.analyserMode()")
        print('local import:', json.dumps(local_st, ensure_ascii=False), json.dumps(local_q, ensure_ascii=False), 'mode:', local_mode)
        report['local_import'] = {'audio': local_st, 'queue': local_q, 'analyser_mode': local_mode,
                                  'local_song': page.evaluate("() => window.currentLocalSong && { name: window.currentLocalSong.name, type: window.currentLocalSong.type }")}
        # EQ: low +12 vs -12 on white noise (analyser sits after EQ)
        def avg_low(n=5):
            vals = []
            for _ in range(n):
                vals.append(page.evaluate("() => window.starwavePhase3.spectrumSample().low"))
                page.wait_for_timeout(400)
            return sum(vals) / len(vals), vals
        page.evaluate("() => window.starwavePhase3.setBand('low', 12)")
        page.wait_for_timeout(2000)
        hi_avg, hi_vals = avg_low()
        page.evaluate("() => window.starwavePhase3.setBand('low', -12)")
        page.wait_for_timeout(2000)
        lo_avg, lo_vals = avg_low()
        page.evaluate("() => window.starwavePhase3.resetEq()")
        print('EQ low +12 avg:', hi_avg, hi_vals, ' low -12 avg:', lo_avg, lo_vals)
        report['eq'] = {'low_plus12_avg': hi_avg, 'low_plus12_vals': hi_vals,
                        'low_minus12_avg': lo_avg, 'low_minus12_vals': lo_vals,
                        'ratio': (hi_avg / lo_avg) if lo_avg else None}
        # resume must exclude the local (blob) track from the saved queue
        page.evaluate("() => window.starwavePhase3.saveResume(true)")
        rs = page.evaluate("() => window.starwavePhase3.resumeState()")
        print('resume after local import (local must be excluded):', json.dumps(rs, ensure_ascii=False))
        report['resume_excludes_local'] = rs

        print('== (4b) BPM/Kick on a deterministic 90 BPM kick file')
        # small viewport for this section only: the full-size WebGL scene
        # saturates the main thread (rAF 1-5 fps) and starves the beat sampler
        page.set_viewport_size({'width': 320, 'height': 240})
        page.set_input_files('#file-input', KICK_WAV)
        page.wait_for_timeout(3000)
        kick = {'audio': audio_state(page),
                'analyser_mode': page.evaluate("() => window.starwavePhase3.analyserMode()")}
        # drive the beat detector at 10 Hz: headless rAF is only 1-5 fps, which
        # quantises onset times to the frame interval and BPM never converges
        page.evaluate("() => { window.__sw3BeatTimer = setInterval(() => window.starwavePhase3.sampleBeat(), 100); }")
        # the VM's headless audio pipeline plays slower than wall clock
        # (measured ~0.65x); BPM is computed from wall-clock onset gaps, so
        # record the audio-clock ratio and the normalised BPM next to it
        t0 = time.time()
        ct0 = page.evaluate("() => window.audio.currentTime")
        beats = []
        for _ in range(24):
            page.wait_for_timeout(500)
            beats.append(page.evaluate("() => window.starwavePhase3.beatInfo()"))
        t1 = time.time()
        ct1 = page.evaluate("() => window.audio.currentTime")
        page.evaluate("() => { clearInterval(window.__sw3BeatTimer); window.__sw3BeatTimer = null; }")
        page.set_viewport_size({'width': 1280, 'height': 800})
        wall = t1 - t0
        audio_dt = ct1 - ct0
        kick['speed_ratio'] = round(audio_dt / wall, 3) if wall > 0 else None
        kick['bpm_normalized'] = (round(beats[-1]['bpm'] / kick['speed_ratio'], 1)
                                  if kick['speed_ratio'] else None)
        page.evaluate("() => { clearInterval(window.__sw3BeatTimer); window.__sw3BeatTimer = null; }")
        kick['samples'] = beats[-3:]
        kick['max_kick'] = max(b.get('kick', 0) for b in beats)
        kick['max_onsets'] = max(b.get('onsets', 0) for b in beats)
        kick['last_bpm'] = beats[-1].get('bpm')
        kick['last_bpm_conf'] = beats[-1].get('bpmConfidence')
        print('kick90:', json.dumps(kick, ensure_ascii=False))
        report['bpm_kick90'] = kick

        print('== (1b) local mp3 import (sakura copy)')
        page.set_input_files('#file-input', LOCAL_MP3)
        page.wait_for_timeout(4000)
        mp3 = {'audio': audio_state(page),
               'local_song': page.evaluate("() => window.currentLocalSong && { name: window.currentLocalSong.name }"),
               'queue': page.evaluate("() => window.starwavePhase3.queueState()")}
        print(json.dumps(mp3, ensure_ascii=False))
        report['local_mp3_import'] = mp3

        print('== (1c) netease free track')
        # the api-enhanced result order varies run to run; a single query's
        # top-10 sometimes has no fee-0 track at all -> poll several queries.
        # NOTE: search fee=0 does NOT guarantee playability: /song/url/v1 may
        # still return an empty URL for that track (per-track restriction
        # upstream), in which case the app must report login_required honestly.
        # So collect fee-0 candidates and try playing each until one plays.
        ne = []
        ne_err = ''
        candidates = []
        for q in ['周杰伦', '邓丽君', '刘德华', '陈奕迅']:
            for attempt in range(2):
                try:
                    ne = page.evaluate(
                        """async (q) => {
                          const songs = await fetchNeteaseWebSearchResults(q);
                          return songs.map(s => ({ name: s.name, artist: s.artist, fee: s.fee, id: s.id }));
                        }""", q)
                    if ne:
                        break
                except Exception as e:
                    ne_err = str(e)[:200]
                page.wait_for_timeout(3000)
            print('netease search %s: %d results' % (q, len(ne)))
            for cand in ne:
                if cand.get('fee') == 0 and cand['id'] not in [c['id'] for c in candidates]:
                    candidates.append(cand)
        # fallback fixture: id 288820 (结尾曲-友谊地久天长 Live) was verified
        # playable in earlier runs (direct /song/url/v1 returns a real URL),
        # while 110740/110191 return url:null code:404 despite fee=0.
        if 288820 not in [c['id'] for c in candidates]:
            candidates.append({'name': '结尾曲-友谊地久天长(Live)', 'artist': '宋祖英 / 郎朗 / 多明戈 / 周杰伦', 'fee': 0, 'id': 288820})
        print('netease fee-0 candidates:', json.dumps(candidates, ensure_ascii=False), 'err:', ne_err)
        attempts = []
        played = None
        for cand in candidates[:6]:
            try:
                res = page.evaluate(
                    """async (cand) => {
                      let s = null;
                      for (const q of ['周杰伦', '邓丽君', '刘德华', '陈奕迅']) {
                        const songs = await fetchNeteaseWebSearchResults(q);
                        s = songs.find(x => String(x.id) === String(cand.id));
                        if (s) break;
                      }
                      if (!s) {
                        // not in any top-10 this run: build a minimal song
                        // object from the id (fetchNeteaseWebPlayback only
                        // needs neteaseId) and try it directly
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
                                     duration: a.duration, src: (a.src || '').slice(0, 80), volume: a.volume } : null,
                        toast: (document.getElementById('toast') || {}).textContent || ''
                      };
                    }""", cand)
            except Exception as e:
                res = {'play_error': str(e)[:300]}
            attempts.append({'name': cand['name'], 'id': cand['id'], 'result': res})
            a = (res or {}).get('audio') or {}
            if a.get('paused') is False and 'music.126.net' in (a.get('src') or ''):
                played = {'name': cand['name'], 'id': cand['id'], 'audio': a}
                # stash the played song id for sections (6)/(8) (survives the
                # reload in section (2b); window state does not)
                page.evaluate("() => { try { localStorage.setItem('__sw3FreeSongId', String(window.playQueue[window.currentIdx].id)); } catch (e) {} }")
                break
            print('netease free attempt %s: not playable (%s)' % (cand['name'], (res or {}).get('toast', '')))
        ne_play = {'candidates': candidates, 'attempts': attempts, 'played': played, 'search_error': ne_err}
        print('netease free play:', json.dumps(ne_play, ensure_ascii=False))
        report['netease_free'] = ne_play
        # VIP (fee>0) must fail honestly, not fake-play
        vip = next((c for c in ne if (c.get('fee') or 0) > 0), None)
        if vip:
            try:
                vip_res = {'song': vip}
                vip_res.update(page.evaluate(
                    """async (id) => {
                      let s = null;
                      for (const q of ['周杰伦', '邓丽君', '刘德华', '陈奕迅']) {
                        const songs = await fetchNeteaseWebSearchResults(q);
                        s = songs.find(x => String(x.id) === String(id));
                        if (s) break;
                      }
                      if (!s) return { play_error: 'song not in search results' };
                      window.__sw3VipSong = s;
                      window.playQueue = [s];
                      window.currentIdx = 0;
                      await playQueueAt(0, { manual: true });
                      await new Promise(r => setTimeout(r, 5000));
                      const a = window.audio;
                      return {
                        audio: a ? { exists: true, paused: a.paused, currentTime: a.currentTime,
                                     duration: a.duration, src: (a.src || '').slice(0, 80), volume: a.volume } : null,
                        toast: (document.getElementById('toast') || {}).textContent || ''
                      };
                    }""", vip['id']))
            except Exception as e:
                vip_res = {'song': vip, 'play_error': str(e)[:300]}
            print('netease VIP attempt:', json.dumps(vip_res, ensure_ascii=False))
            report['netease_vip_attempt'] = vip_res

        print('== (1d) iTunes 30s preview')
        it = []
        it_err = ''
        for attempt in range(3):
            try:
                it = page.evaluate(
                    """async () => {
                      const songs = await fetchItunesPublicSearchResults('Taylor Swift');
                      return songs.slice(0, 3).map(s => ({ name: s.name, artist: s.artist, url: (s.publicAudioUrl||s.previewUrl||'').slice(0,80), duration: s.duration }));
                    }""")
                if it:
                    break
            except Exception as e:
                it_err = str(e)[:200]
            print('itunes search attempt %d empty/failed, retrying...' % (attempt + 1))
            page.wait_for_timeout(4000)
        print('itunes:', json.dumps(it, ensure_ascii=False), 'err:', it_err)
        it_play = {'search': it, 'search_error': it_err}
        if it:
            # single evaluate: search once, play the same objects
            try:
                it_play.update(page.evaluate(
                    """async () => {
                      const songs = await fetchItunesPublicSearchResults('Taylor Swift');
                      const out = { search_count: songs.length };
                      if (!songs.length) return { ...out, play_error: 'empty search results' };
                      window.playQueue = songs.slice(0, 3);
                      window.currentIdx = 0;
                      await playQueueAt(0, { manual: true });
                      await new Promise(r => setTimeout(r, 6000));
                      const a = window.audio;
                      out.audio = a ? { exists: true, paused: a.paused, currentTime: a.currentTime,
                                        duration: a.duration, src: (a.src || '').slice(0, 80), volume: a.volume } : null;
                      out.toast = (document.getElementById('toast') || {}).textContent || '';
                      out.analyser_mode = window.starwavePhase3.analyserMode();
                      out.spectrum = window.starwavePhase3.spectrumSample();
                      return out;
                    }"""))
            except Exception as e:
                it_play['play_error'] = str(e)[:300]
            print('itunes play:', json.dumps(it_play, ensure_ascii=False))
        report['itunes'] = it_play

        print('== (1e) radio regression')
        page.evaluate("() => window.starwaveRadio.start('relax')")
        page.wait_for_timeout(12000)
        radio1 = page.evaluate(
            "() => ({ queue: window.starwavePhase3.queueState(), audio: { paused: window.audio && window.audio.paused } })")
        first = radio1['queue']['current']['name'] if radio1['queue'].get('current') else None
        page.evaluate("() => { if (typeof nextTrack === 'function') nextTrack(); }")
        page.wait_for_timeout(5000)
        radio2 = page.evaluate("() => window.starwavePhase3.queueState()")
        print('radio:', json.dumps(radio1, ensure_ascii=False), 'after next:', json.dumps(radio2, ensure_ascii=False))
        report['radio'] = {'start': radio1, 'first': first, 'after_next': radio2,
                           'next_changed': bool(first and radio2.get('current') and radio2['current']['name'] != first)}
        page.evaluate("() => window.starwaveRadio.stop()")

        print('== (2) queue ops')
        play_demos(page)
        q0 = page.evaluate("() => window.starwavePhase3.queueState()")
        add1 = page.evaluate(
            """async () => {
              const songs = await window.starwavePhase3.demoSongs();
              return { added_idx: window.starwavePhase3.addToQueue(songs[3]),
                       added_next_idx: window.starwavePhase3.addToQueue(songs[4], 'next'),
                       state: window.starwavePhase3.queueState() };
            }""")
        print('after adds:', json.dumps(add1, ensure_ascii=False))
        mv = page.evaluate(
            """() => {
              const before = window.starwavePhase3.queueState().items.slice();
              const ok = window.starwavePhase3.moveQueueItem(1, 1);
              const after = window.starwavePhase3.queueState().items.slice();
              const bad = window.starwavePhase3.moveQueueItem(0, -1);
              return { before: before, moved: ok, after: after, move_out_of_range: bad };
            }""")
        print('move:', json.dumps(mv, ensure_ascii=False))
        rm = page.evaluate(
            """() => {
              const before = window.starwavePhase3.queueState().length;
              removeFromQueue(window.starwavePhase3.queueState().length - 1);
              const after = window.starwavePhase3.queueState();
              return { before: before, after: after };
            }""")
        print('remove last:', json.dumps(rm, ensure_ascii=False))
        modes = page.evaluate(
            """() => {
              const out = [];
              ['loop', 'shuffle', 'single', 'loop'].forEach(m => {
                window.starwavePhase3.setPlayMode(m);
                out.push(window.starwavePhase3.playMode());
              });
              return out;
            }""")
        nxt = page.evaluate(
            """() => {
              const a = window.starwavePhase3.queueState();
              if (typeof nextTrack === 'function') nextTrack();
              return { before: a };
            }""")
        page.wait_for_timeout(4000)
        nxt_after = page.evaluate("() => window.starwavePhase3.queueState()")
        prv = page.evaluate("() => { if (typeof prevTrack === 'function') prevTrack(); return true; }")
        page.wait_for_timeout(4000)
        prv_after = page.evaluate("() => window.starwavePhase3.queueState()")
        print('modes:', modes, 'next:', json.dumps(nxt_after, ensure_ascii=False), 'prev:', json.dumps(prv_after, ensure_ascii=False))
        # queue panel DOM render
        page.evaluate("() => { if (typeof togglePlaylistPanel === 'function') togglePlaylistPanel(true); if (typeof switchPlaylistTab === 'function') switchPlaylistTab('queue'); }")
        page.wait_for_timeout(1200)
        panel = page.evaluate(
            "() => ({ rows: document.querySelectorAll('#queue-list .queue-item').length,"
            " state_len: window.starwavePhase3.queueState().length })")
        print('queue panel rows:', json.dumps(panel, ensure_ascii=False))
        clr = page.evaluate("() => { if (typeof clearQueue === 'function') clearQueue(); return window.starwavePhase3.queueState(); }")
        print('after clear:', json.dumps(clr, ensure_ascii=False))
        report['queue'] = {'initial': q0, 'adds': add1, 'move': mv, 'remove': rm,
                           'modes': modes, 'next_after': nxt_after, 'prev_after': prv_after,
                           'panel': panel, 'after_clear': clr}
        page.evaluate("() => { if (typeof togglePlaylistPanel === 'function') togglePlaylistPanel(false); }")

        print('== (2b) resume after reload')
        play_demos(page)
        page.evaluate("() => { const a = window.audio; a.currentTime = 30; }")
        page.wait_for_timeout(6500)
        rs_before = page.evaluate("() => window.starwavePhase3.resumeState()")
        print('resume saved:', json.dumps(rs_before, ensure_ascii=False))
        page.reload(wait_until='load', timeout=60000)
        dismiss_splash(page)
        page.wait_for_timeout(1500)
        restored = page.evaluate("() => window.starwavePhase3.restoreResume()")
        page.wait_for_timeout(4000)
        rs_after = {'restore': restored, 'audio': audio_state(page),
                    'queue': page.evaluate("() => window.starwavePhase3.queueState()"),
                    'resume_state': page.evaluate("() => window.starwavePhase3.resumeState()")}
        print('resume after reload:', json.dumps(rs_after, ensure_ascii=False))
        report['resume'] = {'before_reload': rs_before, 'after_reload': rs_after}
        page.evaluate("() => { try { if (window.audio) window.audio.pause(); } catch(e){} }")

        print('== (6) favorites (no login gate)')
        fav = page.evaluate(
            """async () => {
              const demos = await window.starwavePhase3.demoSongs();
              const r1 = window.starwavePhase3.toggleFavorite(demos[0]);
              const r2 = window.starwavePhase3.toggleFavorite(demos[1]);
              const out = { demo_fav: r1, demo2_fav: r2, is_fav0: window.starwavePhase3.isFavorite(demos[0]) };
              // (2b) reloaded the page, so re-find a free netease song here
              let free = null;
              for (const q of ['周杰伦', '邓丽君', '刘德华', '陈奕迅']) {
                const songs = await fetchNeteaseWebSearchResults(q);
                free = songs.find(s => s.fee === 0);
                if (free) break;
              }
              if (free) out.netease_free_fav = window.starwavePhase3.toggleFavorite(free);
              out.list_len = window.starwavePhase3.listFavorites().length;
              out.list = window.starwavePhase3.listFavorites().map(f => f.song.name + '|' + (f.song.provider||''));
              return out;
            }""")
        print('favorites:', json.dumps(fav, ensure_ascii=False))
        # old bug: openCollectModal on a demo song must open local collect UI, not reject
        page.evaluate(
            """async () => {
              const demos = await window.starwavePhase3.demoSongs();
              openCollectModal(demos[0]);
            }""")
        page.wait_for_timeout(1200)
        collect_ui = page.evaluate(
            "() => ({ modal_shown: !!document.querySelector('#starwave-phase3-modal.show'),"
            " body_has_collect: (document.getElementById('sw3-body')||{}).textContent ? document.getElementById('sw3-body').textContent.indexOf('正在收藏') >= 0 : false,"
            " toast: (document.getElementById('toast')||{}).textContent || '' })")
        print('collect modal on demo:', json.dumps(collect_ui, ensure_ascii=False))
        page.evaluate("() => window.starwavePhase3.closeLibraryModal()")
        # old bug: toggleLikeSong on a demo song must favorite locally, not reject
        like = page.evaluate(
            """async () => {
              const before = window.starwavePhase3.listFavorites().length;
              const demos = await window.starwavePhase3.demoSongs();
              toggleLikeSong(demos[2]);
              await new Promise(r => setTimeout(r, 300));
              return { before: before, after: window.starwavePhase3.listFavorites().length,
                       toast: (document.getElementById('toast')||{}).textContent || '' };
            }""")
        print('toggleLike on demo:', json.dumps(like, ensure_ascii=False))
        # modal favorites tab renders rows
        page.evaluate("() => window.starwavePhase3.openLibraryModal('favorites')")
        page.wait_for_timeout(1000)
        fav_rows = page.evaluate("() => document.querySelectorAll('#sw3-body .sw3-row').length")
        print('favorites modal rows:', fav_rows)
        page.evaluate("() => window.starwavePhase3.closeLibraryModal()")
        # unfavorite one
        unfav = page.evaluate(
            """async () => {
              const demos = await window.starwavePhase3.demoSongs();
              const r = window.starwavePhase3.toggleFavorite(demos[0]);
              return { unfav: r, list_len: window.starwavePhase3.listFavorites().length };
            }""")
        print('unfavorite:', json.dumps(unfav, ensure_ascii=False))
        report['favorites'] = {'fav': fav, 'collect_ui': collect_ui, 'toggle_like': like,
                               'modal_rows': fav_rows, 'unfav': unfav}

        print('== (7) history')
        page.evaluate("() => window.starwavePhase3.clearHistory()")
        play_demos(page)
        page.evaluate("() => { const a = window.audio; a.currentTime = (a.duration || 209) * 0.55; }")
        page.wait_for_timeout(3000)
        page.evaluate("() => { if (typeof nextTrack === 'function') nextTrack(); }")
        page.wait_for_timeout(5000)
        hs = page.evaluate("() => window.starwavePhase3.historyState()")
        print('history after 55% + switch:', json.dumps(hs, ensure_ascii=False))
        # Phase 3 fix check: the switch must NOT record the incoming song with
        # ~0ms (old bug: old track's 55% progress was credited to the new song)
        hs_phantom = [e for e in hs['entries'] if e['name'] == '茉莉花']
        print('history phantom check: names=%s phantom_moli=%s'
              % ([e['name'] for e in hs['entries']], hs_phantom))
        page.evaluate("() => window.starwavePhase3.openLibraryModal('history')")
        page.wait_for_timeout(1000)
        hs_rows = page.evaluate("() => document.querySelectorAll('#sw3-body .sw3-row').length")
        print('history modal rows:', hs_rows)
        page.evaluate("() => window.starwavePhase3.closeLibraryModal()")
        hs_cleared = page.evaluate("() => window.starwavePhase3.clearHistory()")
        print('history after clear:', json.dumps(hs_cleared, ensure_ascii=False))
        report['history'] = {'after_listen': hs, 'modal_rows': hs_rows, 'after_clear': hs_cleared,
                             'phantom_moli': hs_phantom}

        print('== (8) local playlists + netease import honesty')
        pl = page.evaluate(
            """async () => {
              const demos = await window.starwavePhase3.demoSongs();
              let free = null;
              for (const q of ['周杰伦', '邓丽君', '刘德华', '陈奕迅']) {
                const songs = await fetchNeteaseWebSearchResults(q);
                free = songs.find(s => s.fee === 0);
                if (free) break;
              }
              const created = window.starwavePhase3.createLocalPlaylist('Phase3测试歌单');
              const a1 = window.starwavePhase3.addToLocalPlaylist(created.id, demos[0]);
              const a2 = window.starwavePhase3.addToLocalPlaylist(created.id, demos[1]);
              const a3 = free ? window.starwavePhase3.addToLocalPlaylist(created.id, free) : null;
              const dup = window.starwavePhase3.addToLocalPlaylist(created.id, demos[0]);
              const renamed = window.starwavePhase3.renameLocalPlaylist(created.id, 'Phase3改名歌单');
              const list = window.starwavePhase3.listLocalPlaylists().map(p => ({ id: p.id, name: p.name, n: p.tracks.length }));
              return { created: { id: created.id, name: created.name }, adds: [a1, a2, a3], dup_rejected: !dup,
                       renamed: renamed, list: list };
            }""")
        print('playlist CRUD:', json.dumps(pl, ensure_ascii=False))
        pid = pl['created']['id']
        # detail page must list tracks
        page.evaluate("() => { if (typeof togglePlaylistPanel === 'function') togglePlaylistPanel(true); if (typeof switchPlaylistTab === 'function') switchPlaylistTab('playlists'); }")
        page.evaluate("() => window.starwavePhase3.openLocalPlaylist('" + pid + "')")
        page.wait_for_timeout(1500)
        detail = page.evaluate(
            "() => ({ key: (window.playlistPanelDetailState||{}).key,"
            " tracks: ((window.playlistPanelDetailState||{}).tracks||[]).map(t => t.name),"
            " dom_rows: document.querySelectorAll('[data-pl-detail] .pl-detail-row').length,"
            " panel_text_has_name: (document.getElementById('pl-list')||{}).textContent ? document.getElementById('pl-list').textContent.indexOf('Phase3改名歌单') >= 0 : false })")
        print('playlist detail:', json.dumps(detail, ensure_ascii=False))
        # play the local playlist
        page.evaluate("() => window.starwavePhase3.playLocalPlaylist('" + pid + "')")
        page.wait_for_timeout(5000)
        pl_play = {'audio': audio_state(page), 'queue': page.evaluate("() => window.starwavePhase3.queueState()")}
        print('play local playlist:', json.dumps(pl_play, ensure_ascii=False))
        # remove one song, then delete the playlist
        rm_song = page.evaluate(
            """async () => {
              const demos = await window.starwavePhase3.demoSongs();
              const key = (function(){ try { return queueItemKey(demos[1]); } catch(e){ return demos[1].name + '|' + demos[1].artist; } })();
              const ok = window.starwavePhase3.removeFromLocalPlaylist('""" + pid + """', key);
              const after = window.starwavePhase3.listLocalPlaylists()[0];
              return { removed: ok, remaining: after ? after.tracks.length : -1 };
            }""")
        print('remove song from playlist:', json.dumps(rm_song, ensure_ascii=False))
        del_pl = page.evaluate("() => window.starwavePhase3.deleteLocalPlaylist('" + pid + "')")
        pl_after_del = page.evaluate(
            "() => ({ list_len: window.starwavePhase3.listLocalPlaylists().length,"
            " in_user_playlists: (window.userPlaylists||[]).some(p => String(p.id) === '" + pid + "') })")
        print('delete playlist:', del_pl, json.dumps(pl_after_del, ensure_ascii=False))
        # netease public playlist import must explain honestly, no fake data.
        # The honest notice goes to #source-fallback-notice (auto-hides after
        # 5s), not to the toast -- read it while it is shown.
        page.evaluate("() => { const i = document.getElementById('search-input'); if (i) { i.value = 'https://music.163.com/playlist?id=3778678'; } }")
        page.evaluate("() => { if (typeof runPlaylistImportFromSearch === 'function') runPlaylistImportFromSearch(); }")
        # importSharedPlaylist awaits ensureConnectorAvailable(1800) before
        # showing the honest 'needs connector' notice; read at 3s (notice
        # auto-hides 5s after it appears, ~1.8s in)
        page.wait_for_timeout(3000)
        imp = page.evaluate(
            "() => ({ notice_shown: !!((document.getElementById('source-fallback-notice')||{}).classList||{}).contains && document.getElementById('source-fallback-notice').classList.contains('show'),"
            " notice_title: (document.getElementById('source-fallback-title')||{}).textContent || '',"
            " notice_body: (document.getElementById('source-fallback-body')||{}).textContent || '',"
            " toast: (document.getElementById('toast')||{}).textContent || '',"
            " has_3778678: (window.userPlaylists||[]).some(p => String(p.id) === '3778678'),"
            " playlist_len: (window.playlist||[]).length })")
        print('netease import:', json.dumps(imp, ensure_ascii=False))
        report['playlists'] = {'crud': pl, 'detail': detail, 'play': pl_play,
                               'remove_song': rm_song, 'deleted': del_pl, 'after_delete': pl_after_del,
                               'netease_import': imp}

        print('== (9) regression: spotify/apple/cookie-login')
        reg = page.evaluate(
            """async () => {
              const apple = await window.starwaveAppleMusic.searchCatalog('周杰伦');
              let cookieToast = '';
              try { submitCookieLogin(); } catch (e) { cookieToast = 'threw:' + e.message; }
              await new Promise(r => setTimeout(r, 400));
              cookieToast = (document.getElementById('toast')||{}).textContent || cookieToast;
              return { spotify_type: typeof window.starwaveSpotify,
                       spotify_login_ttl: window.starwaveSpotify && window.starwaveSpotify.loginTtlMs,
                       apple_search: apple,
                       cookie_login_toast: cookieToast,
                       qishui_untouched: typeof window.starwaveQishui !== 'undefined' ? 'module-present' : 'n/a' };
            }""")
        print('regression:', json.dumps(reg, ensure_ascii=False))
        report['regression'] = reg

        print('== errors ==')
        print('console errors (%d):' % len(report['console_errors']))
        for e in report['console_errors']:
            print('  CONSOLE-ERROR:', e[:300])
        print('page errors (%d):' % len(report['page_errors']))
        for e in report['page_errors']:
            print('  PAGE-ERROR:', e[:300])
        print('failed requests (%d):' % len(report['failed_requests']))
        for e in report['failed_requests']:
            print('  REQ-FAIL:', e[:300])
        browser.close()
        if relay_proc:
            relay_proc.terminate()
        if range_proc:
            range_proc.terminate()

    with open('/tmp/sw-phase3-verify-report.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print('report written to /tmp/sw-phase3-verify-report.json')


if __name__ == '__main__':
    main()
