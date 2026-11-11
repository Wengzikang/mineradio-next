# -*- coding: utf-8 -*-
"""StarWave blur-fix verification (targeted, exit 0 only if all pass).
Serves a web root (default web/public; set SW_VERIFY_ROOT to docs/ to
re-verify the deploy copy) on 127.0.0.1:4174 and drives it with Playwright
at 390x844 DPR=3 (iPhone-like) through the test relay 127.0.0.1:18082.
READ-ONLY w.r.t. project code: never edits, never logs in.
Checks (2026-11-11 blur fix):
  S1 render pixel ratio == 3 at load (before the perf governor can step down)
  S2 Three.js background canvas backing ratio >= 2.9
  S3 pet canvas backing ratio == 3, CSS size still 180x110
  S4 #sw4b-particles backing ratio == 3 (regression: was already correct)
  S5 idle-guide canvas backing ratio == 3
  S6 default particle type is 'blocks'
  S7 FX panel particle select contains the 'blocks' option
  S8 while fixture is playing: audioActive true, band levels live and moving
  S9 after pause: audioActive false (ambient fallback, no fake audio data)
  S10 no page errors; no shadowBlur in phase4b; no filter/transform on #sw4b-particles
  S11 git status: changed files are only the allowlist + the known Phase 5C set
Report JSON: /tmp/sw-blur-fix-report.json
Screenshots: /tmp/sw-blur/after-*.png
Usage:
  ~/workspace/.venv-playwright/bin/python scripts/verify-blur-fix.py
  SW_VERIFY_ROOT=docs ~/workspace/.venv-playwright/bin/python scripts/verify-blur-fix.py
"""
import json, os, re, socket, subprocess, sys, time
from playwright.sync_api import sync_playwright

RELAY_PORT = 18082
PORT = 4174
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SERVE_ROOT = os.environ.get('SW_VERIFY_ROOT') or os.path.join(ROOT, 'web/public')
BASE_URL = 'http://127.0.0.1:%d/' % PORT
LOCAL_MP3 = '/tmp/sw-local-test-tremolo.mp3'  # white noise + 0.5Hz tremolo (depth 0.9):
# plain white noise is spectrally stationary, so after the analyser/smoothing
# warm-up the band levels sit flat and a "bands move" check measures nothing;
# the tremolo makes the level genuinely swing loud/quiet every 2s.
OUT = '/tmp/sw-blur'
REPORT = '/tmp/sw-blur-fix-report.json'
os.makedirs(OUT, exist_ok=True)

report = {'checks': {}, 'failures': []}

def check(name, ok, detail=None):
    report['checks'][name] = {'ok': bool(ok), 'detail': detail}
    if not ok:
        report['failures'].append(name)
    print(('PASS ' if ok else 'FAIL ') + name + ((' :: ' + str(detail)) if detail is not None else ''))

def port_open(port):
    s = socket.socket()
    try:
        return s.connect_ex(('127.0.0.1', port)) == 0
    finally:
        s.close()

def main():
    if not port_open(RELAY_PORT):
        print('relay 127.0.0.1:18082 is closed; start scripts/verify-relay-proxy.py first')
        return 2
    if not os.path.exists(LOCAL_MP3):
        print('missing fixture mp3 %s; generate with:' % LOCAL_MP3)
        print("  ffmpeg -y -f lavfi -i 'anoisesrc=color=white:duration=30' -af 'tremolo=f=0.5:d=0.9' -codec:a libmp3lame -q:a 4 %s" % LOCAL_MP3)
        return 2
    # S11: changed-files allowlist
    allowed = {
        'web/public/index.html', 'web/public/starwave-phase4b.js',
        'docs/index.html', 'docs/starwave-phase4b.js',
        'scripts/verify-blur-fix.py', 'scripts/verify-phase4b.py',
        # 2026-11-11 SW 缓存根治（父级授权新增范围）：CACHE_NAME 升版 v2、
        # .js 网络优先、CORE_ASSETS 预缓存、phase5 clearCaches 按前缀排除。
        'web/public/pwa-service-worker.js', 'docs/pwa-service-worker.js',
        'web/public/starwave-phase5.js', 'docs/starwave-phase5.js',
        # 2026-11-11 第三轮粒子清晰度（Ma 15:46 反馈新增范围）：总督降档
        # 只在本次会话生效、不再持久化 + 存量 eco 档位一次性迁移回 high。
        'web/public/starwave-phase2.js', 'docs/starwave-phase2.js',
    }
    known_5c = {
        'NOTICE.md', 'scripts/verify-phase5c.py',
        'web/public/starwave-phase5-automix.js', 'web/public/starwave-phase5-dj-worker.js',
    }
    st = subprocess.run(['git', 'status', '--short'], cwd=ROOT, capture_output=True, text=True)
    changed = set()
    for line in (st.stdout or '').splitlines():
        parts = line.strip().split()
        if len(parts) >= 2:
            changed.add(parts[-1])
    unexpected = sorted(c for c in changed if c not in allowed and c not in known_5c)
    check('S11-changed-files-only-allowlist-plus-5c', not unexpected,
          'changed=%s unexpected=%s' % (sorted(changed), unexpected))
    # static: no shadowBlur property use in phase4b (the word alone appears
    # in a comment explaining that blocks deliberately avoid it)
    with open(os.path.join(ROOT, 'web/public/starwave-phase4b.js'), encoding='utf-8') as f:
        src = f.read()
    check('S10a-no-shadowBlur-in-phase4b', '.shadowBlur' not in src)
    m = re.search(r"cv\.id = 'sw4b-particles';[\s\S]{0,300}?cv\.style\.cssText = '([^']*)'", src)
    check('S10b-no-transform-on-particle-canvas-style', bool(m) and 'transform' not in m.group(1),
          m.group(1) if m else 'cssText not found')

    srv = subprocess.Popen([sys.executable, '-m', 'http.server', str(PORT),
                            '--directory', SERVE_ROOT],
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    time.sleep(1.5)
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(args=[
                '--proxy-server=http://127.0.0.1:%d' % RELAY_PORT,
                '--autoplay-policy=no-user-gesture-required',
                '--ignore-certificate-errors', '--no-sandbox'])
            ctx = browser.new_context(viewport={'width': 390, 'height': 844},
                device_scale_factor=3, is_mobile=True, has_touch=True,
                user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1')
            page = ctx.new_page()
            errs = []
            failed_urls = []
            page.on('pageerror', lambda e: errs.append('pageerror: ' + str(e)))
            page.on('console', lambda m: errs.append('console.error: ' + m.text) if m.type == 'error' else None)
            page.on('response', lambda r: failed_urls.append(r.url) if r.status >= 400 else None)
            page.goto(BASE_URL, wait_until='networkidle', timeout=60000)
            # Wait for init (document complete + particle canvas exists) and
            # measure IMMEDIATELY: the perf governor steps quality down after
            # 3 low-fps ticks (2s apart), so a fixed sleep can land after it.
            page.wait_for_function("() => document.readyState === 'complete' && !!document.getElementById('sw4b-particles')", timeout=30000)
            early = page.evaluate(r"""() => {
              const o = {};
              try { o.quality = fx.performanceQuality; o.ratio = +getRenderPixelRatio().toFixed(2); } catch (e) { o.err = String(e); }
              const out = {};
              document.querySelectorAll('canvas').forEach((cv) => {
                const r = cv.getBoundingClientRect();
                out[cv.id || '(no id)'] = { cssW: Math.round(r.width), cssH: Math.round(r.height),
                  backW: cv.width, backH: cv.height,
                  ratio: r.width ? +(cv.width / r.width).toFixed(2) : 0 };
              });
              o.canvases = out;
              const pc = document.getElementById('sw4b-particles');
              if (pc) { const s = getComputedStyle(pc); o.particleFx = { transform: s.transform, filter: s.filter }; }
              try { const p4b = window.starwavePhase4b; o.particleType = p4b ? p4b.particles.state().type : null; } catch (e) {}
              return o;
            }""")
            report['early'] = early
            check('S1-render-pixel-ratio-3', early.get('ratio') == 3, early)
            bg = (early.get('canvases') or {}).get('(no id)') or {}
            check('S2-threejs-canvas-ratio-ge-2.9', (bg.get('ratio') or 0) >= 2.9, bg)
            pet = (early.get('canvases') or {}).get('sw4b-pet') or {}
            check('S3-pet-canvas-ratio-3', pet.get('ratio') == 3 and pet.get('cssW') == 180 and pet.get('cssH') == 110, pet)
            pc = (early.get('canvases') or {}).get('sw4b-particles') or {}
            check('S4-particle-canvas-ratio-3', pc.get('ratio') == 3, pc)
            ig = (early.get('canvases') or {}).get('idle-guide-canvas') or {}
            check('S5-idle-guide-canvas-ratio-3', ig.get('ratio') == 3, ig)
            check('S6-default-particle-type-blocks', early.get('particleType') == 'blocks', early.get('particleType'))
            check('S10c-no-filter-transform-on-particle-canvas',
                  (early.get('particleFx') or {}).get('transform') in (None, 'none') and
                  (early.get('particleFx') or {}).get('filter') in (None, 'none'), early.get('particleFx'))
            # S7: FX panel select contains blocks
            try:
                page.evaluate("() => { try { window.starwavePhase4b.openPanel('visual'); } catch (e) {} return true; }")
                page.wait_for_timeout(800)
                opts = page.evaluate("""() => { const s = document.getElementById('sw4b-particle-type');
                  return s ? Array.prototype.map.call(s.options, (o) => o.value + ':' + o.text) : null; }""")
            except Exception as e:
                opts = {'error': str(e)}
            check('S7-fx-panel-has-blocks-option', isinstance(opts, list) and any(str(o).startswith('blocks:') for o in opts), opts)
            # S8: play fixture, bands must be live and moving
            page.mouse.click(195, 422)  # dismiss splash if still present
            page.wait_for_timeout(1500)
            page.set_input_files('#file-input', LOCAL_MP3)
            page.wait_for_timeout(1500)
            song = page.evaluate("() => { const s = window.currentLocalSong || (window.playQueue && window.playQueue[0]) || null; return s ? { name: s.name } : null; }")
            played = False
            if song:
                page.evaluate("""(song) => { window.playQueue = [song]; window.currentIdx = 0; return playQueueAt(0, { manual: true }); }""", song)
                page.wait_for_timeout(1500)
                played = page.evaluate("""async () => { const a = window.audio; if (!a) return false;
                  if (a.paused) { try { await a.play(); } catch (e) {} } return !a.paused; }""")
            check('S8a-fixture-playing', played, 'song=%s' % (song,))
            # Headless rAF is only ~2-5fps, but Phase 3's stale-chain recovery
            # needs 90 sampleRealAnalyser calls (1.5s on a real 60fps phone,
            # ~36s in headless). Drive it at 10Hz with the exposed sampleBeat()
            # hook — its own comment says it exists for exactly this
            # ("供定时器/验证调用；无头环境 rAF 只有 1–5fps…10Hz 手动采样").
            page.evaluate("""() => { if (!window.__swBlurBeatTimer) { window.__swBlurBeatTimer = setInterval(function () { try { window.starwavePhase3.sampleBeat(); } catch (e) {} }, 100); } return true; }""")
            # Bands update inside particleTick every 3rd frame; headless rAF
            # is slow (~2-5 fps), so poll up to 20s for the first live sample,
            # then take 6 samples ~1s apart to prove the levels move.
            # Every poll tick is recorded (with audio + analyser state) so a
            # failure shows WHY instead of just "no live sample".
            samples = []
            poll_log = []
            first_live = None
            for _ in range(20):
                page.wait_for_timeout(1000)
                s = page.evaluate("""() => { const st = window.starwavePhase4b.particles.state();
                  const b = st.bands || []; const mx = b.length ? Math.max.apply(null, b) : 0;
                  const a = window.audio; let fdMax = -1;
                  try { const fd = window.frequencyData; if (fd) { for (let i = 0; i < fd.length; i++) if (fd[i] > fdMax) fdMax = fd[i]; } } catch (e) {}
                  return { audioActive: !!st.audioActive, bandsMax: +mx.toFixed(3), bands: b, frame: st.frame,
                    audioPaused: a ? !!a.paused : null, audioTime: a ? +a.currentTime.toFixed(1) : null, fdMax }; }""")
                poll_log.append(s)
                if s.get('audioActive') and s.get('bandsMax', 0) > 0.2:
                    first_live = s
                    break
            report['bandPollLog'] = poll_log
            if first_live is not None:
                samples.append(first_live)
                # Keep sampling until the particle frame has advanced >= 10
                # (guarantees >= 3 band re-reads at the %3 cadence, however
                # slow headless rAF is) or 25s pass, then compare first/last.
                start_frame = first_live.get('frame') or 0
                for _ in range(25):
                    page.wait_for_timeout(1000)
                    s = page.evaluate("""() => { const st = window.starwavePhase4b.particles.state();
                      const b = st.bands || []; const mx = b.length ? Math.max.apply(null, b) : 0;
                      return { audioActive: !!st.audioActive, bandsMax: +mx.toFixed(3), bands: b, frame: st.frame }; }""")
                    samples.append(s)
                    if (s.get('frame') or 0) - start_frame >= 10:
                        break
            report['bandSamples'] = samples
            page.evaluate("() => { if (window.__swBlurBeatTimer) { clearInterval(window.__swBlurBeatTimer); window.__swBlurBeatTimer = null; } return true; }")
            live = [s for s in samples if s.get('audioActive') and s.get('bandsMax', 0) > 0.2]
            moving = False
            if len(samples) >= 2:
                for i in range(1, len(samples)):
                    d = sum(abs((samples[i]['bands'] or [0]*24)[j] - (samples[i-1]['bands'] or [0]*24)[j]) for j in range(24))
                    if d > 0.05:
                        moving = True
            check('S8b-bands-live-while-playing', len(live) > 0, samples)
            check('S8c-bands-moving-across-samples', moving, samples)
            # S8c-per-band: the aggregate check above passes if ANY band moves;
            # it cannot catch a dead segment (review round 1: band 1 was empty).
            # With the tremolo fixture every band must carry energy and move.
            if len(samples) >= 2:
                # Per-band range across ALL samples (first-vs-last alone can
                # land on the same tremolo phase and hide real movement).
                ranges = []
                for j in range(24):
                    vals = [(s.get('bands') or [0] * 24)[j] or 0 for s in samples]
                    ranges.append(max(vals) - min(vals))
                changed = sum(1 for r in ranges if r > 0.01)
                dead = [j for j in range(24)
                        if max((s.get('bands') or [0] * 24)[j] or 0 for s in samples) <= 0.02]
            else:
                changed, dead = 0, list(range(24))
            check('S8c2-per-band-movement', changed >= 20 and not dead,
                  'changedBands=%d/24 deadBands=%s' % (changed, dead))
            # S8d: band edges are 25 strictly-increasing values, 2..560, every
            # segment >= 1 bin (guards the band-1 empty-segment bug).
            edges = page.evaluate("() => window.starwavePhase4b.particles.state().bandEdges || []")
            edges_ok = (len(edges) == 25 and edges[0] == 2 and edges[-1] == 560
                        and all(edges[i + 1] > edges[i] for i in range(24)))
            check('S8d-band-edges-strictly-increasing', edges_ok, edges)
            page.screenshot(path='%s/after-playing-full.png' % OUT)
            page.screenshot(path='%s/after-playing-player.png' % OUT,
                            clip={'x': 0, 'y': 844 - 320, 'width': 390, 'height': 320})
            page.screenshot(path='%s/after-playing-center.png' % OUT,
                            clip={'x': 0, 'y': 150, 'width': 390, 'height': 400})
            # S9: pause -> audioActive must go false (ambient fallback, no fake audio)
            page.evaluate("() => { const a = window.audio; if (a) a.pause(); return true; }")
            paused_off = False
            for _ in range(20):
                page.wait_for_timeout(800)
                st = page.evaluate("() => { const s = window.starwavePhase4b.particles.state(); return { audioActive: !!s.audioActive, bandsMax: +(Math.max.apply(null, s.bands || [0])).toFixed(3) }; }")
                if not st.get('audioActive'):
                    paused_off = True
                    break
            check('S9-audioActive-false-after-pause', paused_off, st)
            # S10d: no page errors. Two console errors are KNOWN BENIGN artifacts
            # of the local test fixture (not of this change): playQueueAt on a
            # local file with no NetEase id requests /api/song/url?id=undefined,
            # which 404s on the plain http.server (no such endpoint); the app
            # then tries response.json() on the 404 HTML page, which throws
            # "Unexpected token '<' ... is not valid JSON" (hence the
            # 'Unexpected token' whitelist term), logs "Play failed ...
            # source-url ...", and falls back to direct play (S8a proves the
            # fallback works). A 404 line is benign only when that
            # /api/song/url request was actually observed. Anything else fails.
            def benign(e):
                if 'Play failed' in e and 'source-url' in e and 'Unexpected token' in e:
                    return True
                if 'Failed to load resource' in e:
                    return any('/api/song/url' in u for u in failed_urls)
                return False
            real_errs = [e for e in errs if not benign(e)]
            check('S10d-no-page-errors', len(real_errs) == 0, errs[:5])
            browser.close()
    finally:
        srv.terminate()
    with open(REPORT, 'w') as f:
        json.dump(report, f, indent=1, ensure_ascii=False)
    print('failures:', report['failures'])
    print('report:', REPORT)
    return 0 if not report['failures'] else 1

if __name__ == '__main__':
    sys.exit(main())
