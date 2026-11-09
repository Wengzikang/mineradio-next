# -*- coding: utf-8 -*-
"""Diagnostic probe: why does an iTunes preview not start playing?
Instruments tryAutoPlaybackFallback / handlePlaybackUnavailable / playPhase
and dumps the audio element state after playQueueAt. Reuses the relay on
18082 and the range server on 4174 (both must already be running).
"""
import json
import subprocess
import sys
import time

sys.path.insert(0, '/home/hatch/workspace/.venv-playwright/lib/python3.12/site-packages')
from playwright.sync_api import sync_playwright

BASE_URL = 'http://127.0.0.1:4174/'


def main():
    with sync_playwright() as pw:
        browser = pw.chromium.launch(args=[
            '--ignore-certificate-errors',
            '--proxy-server=http://127.0.0.1:18082',
            '--autoplay-policy=no-user-gesture-required',
            '--mute-audio',
        ])
        page = browser.new_page(viewport={'width': 1280, 'height': 800})
        page.on('console', lambda m: print('CONSOLE', m.type, m.text[:300]) if m.type in ('error', 'warning') else None)
        page.on('pageerror', lambda e: print('PAGEERROR', str(e)[:300]))
        page.goto(BASE_URL, wait_until='load')
        page.wait_for_timeout(4000)
        out = page.evaluate("""async () => {
          window.__probe = { fallbackCalls: [], unavailable: [], phases: [] };
          const origFallback = window.tryAutoPlaybackFallback;
          window.tryAutoPlaybackFallback = async function(song, data, idx, token, opts) {
            window.__probe.fallbackCalls.push({ reason: data && data.reason, keepCurrent: !!(opts && opts.keepCurrentOnFallbackMiss) });
            const r = await origFallback(song, data, idx, token, opts);
            window.__probe.fallbackCalls.push({ returned: r });
            return r;
          };
          const origUnavail = window.handlePlaybackUnavailable;
          window.handlePlaybackUnavailable = function(song, data) {
            window.__probe.unavailable.push({ reason: data && data.reason, message: data && data.message });
            return origUnavail(song, data);
          };
          const songs = await fetchItunesPublicSearchResults('Taylor Swift');
          if (!songs.length) return { error: 'no itunes songs' };
          const s = songs[0];
          const key = songProviderKey(s);
          const data = await fetchPublicSourcePlayback(s);
          const tokenBefore = window.trackSwitchToken;
          const audioBefore = window.audio ? { src: (window.audio.src || '').slice(0, 80), paused: window.audio.paused } : null;
          window.playQueue = songs.slice(0, 3);
          window.currentIdx = 0;
          let playErr = '';
          try {
            await playQueueAt(0, { manual: true });
          } catch (e) { playErr = String((e && e.message) || e); }
          await new Promise(r => setTimeout(r, 6000));
          const a = window.audio;
          return {
            song: { name: s.name, provider: s.provider, trial: s.trial },
            providerKey: key,
            playbackData: { playable: data.playable, trial: data.trial, url: (data.url || '').slice(0, 80), level: data.level },
            tokenBefore, tokenAfter: window.trackSwitchToken,
            audioBefore,
            audioAfter: a ? { src: (a.src || '').slice(0, 80), paused: a.paused, currentTime: a.currentTime, duration: a.duration, error: a.error ? a.error.code : null } : null,
            playErr,
            toast: (document.getElementById('toast') || {}).textContent || '',
            lastAudioPlayError: window.lastAudioPlayError || '',
            probe: window.__probe
          };
        }""")
        print(json.dumps(out, ensure_ascii=False, indent=1))
        browser.close()


if __name__ == '__main__':
    main()
