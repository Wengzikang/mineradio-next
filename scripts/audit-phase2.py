# -*- coding: utf-8 -*-
"""StarWave Phase 2 UI audit (real browser).
Enumerates clickable controls in each of the 8 views, checks the onclick
handler function exists, clicks visible ones, records page errors / toasts.
Views: home, search, lyrics stage, 3D shelf, playlist detail, DIY console,
listening profile, settings/about (added in Phase 2).
Usage: ~/workspace/.venv-playwright/bin/python scripts/audit-phase2.py
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
BASE_URL = 'http://127.0.0.1:4173/'


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


FN_RE = re.compile(r"^\s*(?:window\.)?([A-Za-z_$][\w$]*)\s*\(")
SKIP_ONCLICK = ('file-input', 'installStarWavePwa', 'toggleFullscreen',
                'requestDualLoginMode', 'openProviderWebLogin')
SKIP_IDS = {'install-app-btn'}


def first_fn(onclick):
    if not onclick:
        return None
    m = FN_RE.match(onclick.strip())
    return m.group(1) if m else None


def toast_text(page):
    try:
        return page.evaluate(
            "() => { const t = document.getElementById('toast');"
            " return t ? (t.textContent || '').trim() : ''; }")
    except Exception:
        return ''


def collect_buttons(page, root_selector):
    """Return list of {id, text, onclick, fn, fn_exists, visible} under root."""
    return page.evaluate(
        """(rootSel) => {
          const root = rootSel ? document.querySelector(rootSel) : document;
          if (!root) return [];
          const els = root.querySelectorAll('button, [onclick], input[type=button]');
          const out = [];
          els.forEach((el) => {
            const r = el.getBoundingClientRect();
            const cs = getComputedStyle(el);
            const visible = r.width > 0 && r.height > 0 && cs.display !== 'none'
              && cs.visibility !== 'hidden' && cs.pointerEvents !== 'none';
            out.push({
              id: el.id || '',
              tag: el.tagName,
              text: (el.textContent || '').trim().slice(0, 40),
              title: el.getAttribute('title') || '',
              cls: (el.className || '').toString().slice(0, 60),
              onclick: el.getAttribute('onclick') || '',
              visible: visible,
              disabled: !!el.disabled,
              ariaDisabled: el.getAttribute('aria-disabled') || ''
            });
          });
          return out;
        }""", root_selector)


def fn_exists(page, name):
    if not name:
        return None
    try:
        return bool(page.evaluate(
            "() => typeof window[%s] === 'function'" % json.dumps(name)))
    except Exception:
        return None


def audit_region(page, view, root_selector, opener_js=None):
    if opener_js:
        try:
            page.evaluate(opener_js)
        except Exception as e:
            print('  [%s] opener failed: %s' % (view, e))
        page.wait_for_timeout(900)
    btns = collect_buttons(page, root_selector)
    rows = []
    for b in btns:
        fn = first_fn(b['onclick'])
        row = dict(b)
        row['view'] = view
        row['fn'] = fn
        row['fn_exists'] = fn_exists(page, fn) if fn else None
        rows.append(row)
    return rows


def click_probe(page, view, rows):
    """Click visible, enabled buttons with a resolvable handler; record outcome."""
    results = []
    for row in rows:
        if not row['visible'] or row['disabled']:
            row['probe'] = 'skipped-hidden-disabled'
            results.append(row)
            continue
        oc = row['onclick'] or ''
        if any(s in oc for s in SKIP_ONCLICK) or row['id'] in SKIP_IDS:
            row['probe'] = 'skipped-system'
            results.append(row)
            continue
        if not row['fn']:
            row['probe'] = 'no-onclick-fn'
            results.append(row)
            continue
        if row['fn_exists'] is False:
            row['probe'] = 'dead-missing-fn'
            results.append(row)
            continue
        # click by id if present else by nth matching button in view root
        try:
            before_toast = toast_text(page)
            if row['id']:
                page.click('#' + row['id'], timeout=3000, force=True)
            else:
                page.evaluate(
                    """(txt) => {
                      const els = Array.from(document.querySelectorAll('button'));
                      const el = els.find(e => (e.textContent||'').trim().slice(0,40) === txt
                        && e.getBoundingClientRect().width > 0);
                      if (el) el.click();
                    }""", row['text'])
            page.wait_for_timeout(450)
            after_toast = toast_text(page)
            row['probe'] = 'clicked'
            row['toast_after'] = after_toast
            # close any modal that opened, to keep probing
            page.keyboard.press('Escape')
            page.wait_for_timeout(200)
            page.evaluate(
                """() => {
                  document.querySelectorAll('.modal-mask.show').forEach(m => {
                    const c = m.querySelector('.btn-row .modal-btn');
                    if (c) c.click();
                  });
                }""")
            page.wait_for_timeout(200)
        except Exception as e:
            row['probe'] = 'click-error: %s' % str(e)[:160]
        results.append(row)
    return results


def main():
    report = {'page_errors': [], 'console_errors': [], 'views': {}}
    with sync_playwright() as pw:
        relay_proc = ensure_relay()
        proxy_cfg = {'server': 'http://127.0.0.1:%d' % RELAY_PORT,
                     'bypass': 'localhost,127.0.0.1,::1'}
        browser = pw.chromium.launch(
            args=['--autoplay-policy=no-user-gesture-required',
                  '--ignore-certificate-errors'],
            proxy=proxy_cfg)
        page = browser.new_page(viewport={'width': 1280, 'height': 900})
        page.on('console', lambda m: report['console_errors'].append(m.text)
                if m.type == 'error' else None)
        page.on('pageerror', lambda e: report['page_errors'].append(str(e)))
        page.goto(BASE_URL, wait_until='load', timeout=60000)
        page.evaluate("""() => {
          window.__swStacks = [];
          window.addEventListener('error', (e) => {
            const err = e.error;
            window.__swStacks.push({ message: e.message,
              stack: err && err.stack ? String(err.stack).slice(0, 4000) : '(no stack)',
              time: Date.now() });
          });
        }""")
        page.wait_for_timeout(2000)
        try:
            page.wait_for_selector('#splash.ready', state='attached', timeout=30000)
            page.click('#splash', timeout=5000)
        except Exception:
            page.evaluate("() => { if (typeof dismissSplash === 'function') dismissSplash(); }")
        page.wait_for_timeout(1200)
        page.evaluate("() => { if (typeof loadHomeDiscover === 'function') loadHomeDiscover(true); }")
        page.wait_for_timeout(1500)

        # 1. home
        print('== home')
        rows = audit_region(page, 'home', '#empty-home')
        report['views']['home'] = click_probe(page, 'home', rows)
        print('  [audit] page errors after home: %d' % len(report['page_errors']))
        # 2. search
        print('== search')
        page.fill('#search-input', '周杰伦')
        page.press('#search-input', 'Enter')
        try:
            page.wait_for_selector('#search-results .search-result', state='attached', timeout=30000)
        except Exception as e:
            print('  search results missing:', e)
        page.wait_for_timeout(800)
        rows = audit_region(page, 'search', '#search-area')
        report['views']['search'] = click_probe(page, 'search', rows)
        print('  [audit] page errors after search: %d' % len(report['page_errors']))
        # 3. lyrics stage: play a demo track, then lyrics panel + stage
        print('== lyrics stage')
        try:
            page.locator('#home-preview-list .home-preview-track').first.click()
            page.wait_for_timeout(3500)
        except Exception as e:
            print('  demo click failed:', e)
        page.evaluate("() => { if (typeof toggleLyricsPanel === 'function') toggleLyricsPanel(true); }")
        page.wait_for_timeout(800)
        rows = audit_region(page, 'lyrics-stage', '#lyrics-panel')
        if not rows:
            rows = audit_region(page, 'lyrics-stage', 'body')
            rows = [r for r in rows if 'lyric' in (r['id'] + r['cls'] + r['text']).lower()]
        report['views']['lyrics-stage'] = click_probe(page, 'lyrics-stage', rows)
        print('  [audit] page errors after lyrics-stage: %d' % len(report['page_errors']))
        # stage-lyrics DOM state
        report['stage_lyrics'] = page.evaluate(
            """() => { const el = document.getElementById('stage-lyrics');
              return { exists: !!el, children: el ? el.children.length : 0,
                       display: el ? getComputedStyle(el).display : '' }; }""")
        # 4. 3D shelf: open playlist panel (shelf lives in scene; probe panel + shelf segs)
        print('== shelf / playlist panel')
        page.evaluate("() => { if (typeof togglePlaylistPanel === 'function') togglePlaylistPanel(true); }")
        page.wait_for_timeout(900)
        rows = audit_region(page, 'shelf', '#playlist-panel')
        report['views']['shelf'] = click_probe(page, 'shelf', rows)
        print('  [audit] page errors after shelf: %d' % len(report['page_errors']))
        # 5. playlist detail: open first playlist detail if available
        print('== playlist detail')
        detail_opened = page.evaluate(
            """() => {
              const cards = document.querySelectorAll('#playlist-panel [data-playlist-title], #playlist-panel .playlist-card');
              if (cards.length) { cards[0].click(); return cards.length; }
              if (typeof openPlaylistPanelDetail === 'function') return 'fn-only';
              return 0; }""")
        page.wait_for_timeout(900)
        report['playlist_detail_opened'] = detail_opened
        rows = audit_region(page, 'playlist-detail', '#playlist-panel')
        report['views']['playlist-detail'] = click_probe(page, 'playlist-detail', rows)
        print('  [audit] page errors after playlist-detail: %d' % len(report['page_errors']))
        page.evaluate("() => { if (typeof togglePlaylistPanel === 'function') togglePlaylistPanel(false); }")
        # 6. DIY console
        print('== DIY console')
        page.evaluate("() => { if (typeof openDiyRhythmConsole === 'function') openDiyRhythmConsole(); }")
        page.wait_for_timeout(1000)
        rows = audit_region(page, 'diy', '#fx-panel')
        report['views']['diy'] = click_probe(page, 'diy', rows)
        print('  [audit] page errors after diy: %d' % len(report['page_errors']))
        page.evaluate("() => { if (typeof toggleFxPanel === 'function') toggleFxPanel(false); }")
        # 7. listening profile
        print('== profile')
        page.evaluate("() => { if (typeof openHomeInsight === 'function') openHomeInsight(); }")
        page.wait_for_timeout(900)
        report['profile_toast'] = toast_text(page)
        report['profile_summary'] = page.evaluate(
            "() => { try { return homeListenSummary(); } catch (e) { return 'error: ' + e; } }")
        rows = audit_region(page, 'profile', '#empty-home')
        report['views']['profile'] = [r for r in rows if 'profile' in (r['id'] + r['text']).lower()]
        # 8. settings/about (Phase 2 modal; created lazily on open)
        print('== settings/about')
        page.evaluate("() => { if (typeof window.starwaveOpenAbout === 'function') window.starwaveOpenAbout(); }")
        page.wait_for_timeout(800)
        has_about = page.evaluate("() => !!document.getElementById('starwave-about-modal')")
        report['settings_about_exists'] = has_about
        if has_about:
            rows = audit_region(page, 'settings', '#starwave-about-modal')
            report['views']['settings'] = click_probe(page, 'settings', rows)
            print('  [audit] page errors after settings: %d' % len(report['page_errors']))
            page.evaluate("() => { if (typeof window.starwaveCloseAbout === 'function') window.starwaveCloseAbout(); }")
        else:
            report['views']['settings'] = []

        try:
            stacks = page.evaluate("() => window.__swStacks || []")
            with open('/tmp/sw-audit-stacks.json', 'w', encoding='utf-8') as f:
                json.dump(stacks, f, ensure_ascii=False, indent=2)
            print('stacks captured:', len(stacks))
            if stacks:
                print('FIRST STACK:'); print(stacks[0].get('stack', '')[:3000])
        except Exception as e:
            print('stack dump failed:', e)
        print('page errors (%d):' % len(report['page_errors']))
        for e in report['page_errors']:
            print('  PAGE-ERROR:', e[:300])
        print('console errors (%d):' % len(report['console_errors']))
        for e in report['console_errors']:
            print('  CONSOLE-ERROR:', e[:300])
        browser.close()
        if relay_proc:
            relay_proc.terminate()

    with open('/tmp/sw-phase2-audit.json', 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    # summary
    for view, rows in report['views'].items():
        dead = [r for r in rows if r.get('fn_exists') is False or r.get('probe') == 'dead-missing-fn']
        clicked = [r for r in rows if r.get('probe') == 'clicked']
        print('%-16s total=%d clicked=%d dead-missing-fn=%d' % (view, len(rows), len(clicked), len(dead)))
        for r in dead:
            print('   DEAD: id=%s text=%s fn=%s onclick=%s' % (r['id'], r['text'], r['fn'], r['onclick'][:100]))
    print('audit written to /tmp/sw-phase2-audit.json')


if __name__ == '__main__':
    main()
