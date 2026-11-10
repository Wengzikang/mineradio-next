# -*- coding: utf-8 -*-
"""Focused probe: (a) why does fixture currentTime jump back after seek?
(b) why does a local file import stay paused?
(Demo songs were deleted 2026-11-10 at Ma's order; the seek probe now uses
the generated fixture mp3 instead of the demo songs.)"""
import json
import os
import subprocess
import sys
import time

LOCAL_MP3 = '/tmp/sw-local-test.mp3'

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__))))
from playwright.sync_api import sync_playwright

RELAY_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'verify-relay-proxy.py')


def main():
    import socket
    if not os.path.exists(LOCAL_MP3):
        subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
                        '-f', 'lavfi', '-i', 'anoisesrc=color=white:duration=30',
                        '-codec:a', 'libmp3lame', '-q:a', '4', LOCAL_MP3], check=True)
    try:
        s = socket.socket(); s.connect(('127.0.0.1', 18082)); s.close()
    except OSError:
        subprocess.Popen([sys.executable, RELAY_SCRIPT],
                         stdout=open('/tmp/sw-relay.log', 'w'), stderr=subprocess.STDOUT)
        time.sleep(1)
    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            args=['--autoplay-policy=no-user-gesture-required', '--ignore-certificate-errors'],
            proxy={'server': 'http://127.0.0.1:18082', 'bypass': 'localhost,127.0.0.1,::1'})
        page = browser.new_page(viewport={'width': 1280, 'height': 900})
        errs = []
        page.on('pageerror', lambda e: errs.append(str(e)))
        page.on('console', lambda m: errs.append('CONSOLE:' + m.text) if m.type == 'error' else None)
        page.goto('http://127.0.0.1:4173/', wait_until='load', timeout=60000)
        page.wait_for_timeout(1500)
        try:
            page.wait_for_selector('#splash.ready', state='attached', timeout=30000)
            page.click('#splash', timeout=5000)
        except Exception:
            page.evaluate("() => { if (typeof dismissSplash === 'function') dismissSplash(); }")
        page.wait_for_timeout(1000)

        # instrument audio events + playQueueAt calls
        page.evaluate(
            """() => {
              window.__probeLog = [];
              const origPQA = window.playQueueAt;
              window.playQueueAt = function(idx, opts) {
                window.__probeLog.push([Date.now(), 'playQueueAt', idx, JSON.stringify(opts||{})]);
                return origPQA(idx, opts);
              };
              window.__armAudioProbe = () => {
                const a = window.audio;
                if (!a || a.__probed) return;
                a.__probed = true;
                ['seeked','seeking','playing','pause','ended','error','loadstart','loadedmetadata','canplay','stalled','suspend','abort'].forEach(ev => {
                  a.addEventListener(ev, () => window.__probeLog.push([Date.now(), 'audio:'+ev, 'ct='+(a.currentTime||0).toFixed(2), 'paused='+a.paused]));
                });
              };
            }""")
        page.set_input_files('#file-input', LOCAL_MP3)
        page.wait_for_timeout(4000)
        page.evaluate(
            """() => {
              const song = window.currentLocalSong || (window.playQueue && window.playQueue[0]) || null;
              if (!song) return;
              window.playQueue = [song];
              window.currentIdx = 0;
              return playQueueAt(0, { manual: true });
            }""")
        page.wait_for_timeout(4000)
        page.evaluate("() => window.__armAudioProbe()")
        print('before seek:', page.evaluate("() => ({ ct: window.audio.currentTime, paused: window.audio.paused, src: window.audio.src.slice(-20) })"))
        page.evaluate("() => { window.__seekAt = Date.now(); window.audio.currentTime = 20; }")
        for i in range(12):
            page.wait_for_timeout(500)
            print('t+%0.1fs' % ((i + 1) * 0.5), page.evaluate(
                "() => ({ ct: Math.round(window.audio.currentTime*100)/100, paused: window.audio.paused, seeking: window.audio.seeking, readyState: window.audio.readyState })"))
        print('probe log:', json.dumps(page.evaluate("() => window.__probeLog"), ensure_ascii=False))
        print('errors:', errs)

        print('--- local import probe ---')
        page.evaluate("() => { window.__probeLog = []; window.__armAudioProbe(); }")
        page.set_input_files('#file-input', '/tmp/sw-noise.wav')
        page.wait_for_timeout(1000)
        print('after 1s:', page.evaluate(
            "() => ({ ct: window.audio.currentTime, paused: window.audio.paused, src: (window.audio.src||'').slice(0,60),"
            " err: window.audio.error ? window.audio.error.code + '/' + window.audio.error.message : null,"
            " ctxState: window.audioCtx ? window.audioCtx.state : null,"
            " lastPlayErr: window.lastAudioPlayError ? String(window.lastAudioPlayError.message || window.lastAudioPlayError) : null,"
            " toast: (document.getElementById('toast')||{}).textContent || '' })"))
        page.wait_for_timeout(3000)
        print('after 4s:', page.evaluate(
            "() => ({ ct: window.audio.currentTime, paused: window.audio.paused,"
            " err: window.audio.error ? window.audio.error.code : null,"
            " toast: (document.getElementById('toast')||{}).textContent || '' })"))
        print('probe log:', json.dumps(page.evaluate("() => window.__probeLog"), ensure_ascii=False))
        manual = page.evaluate(
            """async () => {
              const a = window.audio;
              try { await a.play(); return { ok: true, paused: a.paused, ct: a.currentTime }; }
              catch (e) { return { ok: false, name: e.name, message: e.message }; }
            }""")
        print('manual play():', json.dumps(manual, ensure_ascii=False))
        page.wait_for_timeout(2000)
        print('after manual play:', page.evaluate(
            "() => ({ ct: window.audio.currentTime, paused: window.audio.paused })"))
        print('errors:', errs)
        browser.close()


if __name__ == '__main__':
    main()
