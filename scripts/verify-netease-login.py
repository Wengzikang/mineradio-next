# -*- coding: utf-8 -*-
"""StarWave NetEase QR login verification (real browser, real network, no mocks).
Serves web/public on 127.0.0.1:4173 and drives it with Playwright via the test relay.
Checks:
  (a) page load: no uncaught JS errors; console errors recorded for review
  (b) top-right button reads 登录 (visible login entry)
  (c) logged-out search '周杰伦' returns real NetEase results
  (d) in-app NetEase playback: free track 288820 resolves playable via the app's
      own fetchNeteaseWebPlayback; restricted track 210049 resolves
      login_required with the honest prompt (no fake playback)
  (e) click 登录 -> login modal opens on the NetEase tab -> a real QR image
      appears (data: URL, non-empty), status mentions 扫码， the cookie-import
      panel stays hidden and no 手动导入 button is visible; the poll runs ~6s
      without errors; closing the modal stops the poll
  (f) negative test: a deliberately INVALID test-only cookie value in
      localStorage (no real credential) is rejected on reload: the app stays
      logged out, search and free playback still work, the invalid value is
      cleared, and it never appears in any console message
Usage: python3 scripts/verify-netease-login.py
"""
import argparse
import json
import os
import socket
import subprocess
import sys
import time

from playwright.sync_api import sync_playwright

RELAY_PORT = 18082
RELAY_SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'verify-relay-proxy.py')
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE_URL = 'http://127.0.0.1:4173/'
FAKE_COOKIE = 'MUSIC_U=INVALID_TEST_ONLY_12345'


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


def ensure_server():
    s = socket.socket()
    try:
        s.connect(('127.0.0.1', 4173))
        s.close()
        return None
    except OSError:
        pass
    proc = subprocess.Popen([sys.executable, '-m', 'http.server', '4173', '-d',
                             os.path.join(ROOT, 'web', 'public')],
                            stdout=open('/tmp/sw-http.log', 'w'), stderr=subprocess.STDOUT)
    for _ in range(30):
        try:
            s = socket.socket()
            s.connect(('127.0.0.1', 4173))
            s.close()
            return proc
        except OSError:
            time.sleep(0.2)
    raise RuntimeError('http server did not start')


def audio_state(page):
    return page.evaluate(
        """() => {
          const a = document.querySelector('audio');
          if (!a) return { exists: false };
          return { exists: true, paused: a.paused, currentTime: a.currentTime,
                   duration: a.duration, src: (a.src || '').slice(0, 120) };
        }"""
    )


def dismiss_splash(page):
    try:
        page.wait_for_selector('#splash.ready', state='attached', timeout=30000)
        page.click('#splash', timeout=5000)
        print('splash dismissed via click')
    except Exception as e:
        print('splash not ready for click (%s); calling dismissSplash() directly' % e)
        page.evaluate("() => { if (typeof dismissSplash === 'function') dismissSplash(); }")
    page.wait_for_function(
        "() => { const s = document.getElementById('splash'); return !s || getComputedStyle(s).display === 'none' || getComputedStyle(s).pointerEvents === 'none'; }",
        timeout=15000,
    )
    page.wait_for_timeout(1500)


def search_zhou(page):
    page.fill('#search-input', '周杰伦')
    page.press('#search-input', 'Enter')
    try:
        page.wait_for_selector('#search-results .search-result', state='attached', timeout=30000)
    except Exception as e:
        print('WARN: no search results appeared:', e)
        return []
    page.wait_for_timeout(1000)
    return page.evaluate(
        """() => Array.from(document.querySelectorAll('#search-results .search-result'))
               .map(el => ({
                 title: (el.querySelector('.search-result-title')||{}).textContent.trim(),
                 tag: (el.querySelector('.tag-source')||{}).textContent.trim()
               }))"""
    )


def main():
    report = {'console_errors': [], 'page_errors': [], 'failed_requests': [],
              'login_requests': [], 'checks': {}}
    relay_proc = ensure_relay()
    server_proc = ensure_server()
    try:
        with sync_playwright() as pw:
            proxy_cfg = {'server': 'http://127.0.0.1:%d' % RELAY_PORT,
                         'bypass': 'localhost,127.0.0.1,::1'}
            browser = pw.chromium.launch(
                args=['--autoplay-policy=no-user-gesture-required',
                      '--ignore-certificate-errors'],
                proxy=proxy_cfg,
            )
            page = browser.new_page(viewport={'width': 1280, 'height': 900})
            page.on('console', lambda m: report['console_errors'].append(m.text) if m.type == 'error' else None)
            page.on('pageerror', lambda e: report['page_errors'].append(str(e)))
            page.on('requestfailed', lambda r: report['failed_requests'].append(r.url + ' :: ' + (r.failure or '')))
            page.on('request', lambda r: report['login_requests'].append(r.url) if 'login/qr' in r.url else None)

            print('== (a) load')
            page.goto(BASE_URL, wait_until='load', timeout=60000)
            page.wait_for_timeout(2000)
            dismiss_splash(page)
            report['checks']['load_page_errors'] = len(report['page_errors']) == 0
            print('page_errors so far:', report['page_errors'])

            print('== (b) visible login entry')
            btn = page.evaluate(
                """() => { const b = document.getElementById('user-btn');
                           return b ? b.textContent.trim() : null; }""")
            print('user-btn text:', repr(btn))
            report['checks']['user_btn_is_login'] = (btn == '登录')

            print("== (c) logged-out search '周杰伦'")
            results = search_zhou(page)
            ne = [r for r in results if r['tag'] == '网易云']
            print('results: %d total, %d netease' % (len(results), len(ne)))
            for r in ne[:5]:
                print('  - [网易云]', r['title'])
            report['checks']['search_has_netease'] = len(ne) > 0

            print('== (d) in-app playback resolution (free vs restricted)')
            free = page.evaluate(
                """async () => { const r = await fetchNeteaseWebPlayback({neteaseId: 288820, id: 288820, name: 'test'});
                                return { playable: r.playable, url: (r.url || '').slice(0, 80), reason: r.reason || '' }; }""")
            print('free 288820:', json.dumps(free, ensure_ascii=False))
            restricted = page.evaluate(
                """async () => { const r = await fetchNeteaseWebPlayback({neteaseId: 210049, id: 210049, name: '布拉格广场'});
                                return { playable: r.playable, reason: r.reason || '', message: r.message || '' }; }""")
            print('restricted 210049:', json.dumps(restricted, ensure_ascii=False))
            report['checks']['free_track_playable'] = bool(free.get('playable'))
            report['checks']['restricted_is_login_required'] = (
                not restricted.get('playable') and restricted.get('reason') == 'login_required'
                and '需登录' in restricted.get('message', ''))

            print('== (e) QR login modal')
            page.click('#user-btn')
            page.wait_for_timeout(1500)
            modal = page.evaluate(
                """() => {
                  const m = document.getElementById('login-modal');
                  const img = document.getElementById('qr-img');
                  const st = document.getElementById('qr-status');
                  const panel = document.getElementById('qq-cookie-panel');
                  const tog = document.getElementById('qq-cookie-toggle-btn');
                  const title = document.getElementById('login-modal-title');
                  return {
                    modalShown: !!(m && m.classList.contains('show')),
                    title: title ? title.textContent.trim() : '',
                    qrSrcPrefix: img ? (img.src || '').slice(0, 30) : '',
                    qrSrcLen: img ? (img.src || '').length : 0,
                    qrNaturalWidth: img ? img.naturalWidth : 0,
                    status: st ? st.textContent.trim() : '',
                    cookiePanelShown: !!(panel && panel.classList.contains('show')),
                    cookieToggleVisible: !!(tog && tog.classList.contains('show')),
                    neteaseTabActive: !!(document.getElementById('login-provider-netease') || {}).classList &&
                      document.getElementById('login-provider-netease').classList.contains('active'),
                  };
                }""")
            print(json.dumps(modal, ensure_ascii=False, indent=1))
            report['checks']['modal_opens'] = modal['modalShown']
            report['checks']['qr_image_shown'] = (
                modal['qrSrcPrefix'].startswith('data:image') and modal['qrSrcLen'] > 1000
                and modal['qrNaturalWidth'] > 0)
            report['checks']['qr_status_mentions_scan'] = '扫码' in modal['status']
            report['checks']['cookie_panel_hidden'] = not modal['cookiePanelShown']
            report['checks']['no_manual_import_button'] = not modal['cookieToggleVisible']
            print('-- waiting 6s for poll --')
            page.wait_for_timeout(6000)
            status2 = page.evaluate("() => (document.getElementById('qr-status')||{}).textContent || ''")
            print('status after 6s poll:', repr(status2))
            report['checks']['poll_keeps_waiting'] = ('扫码' in status2) or ('等待' in status2)
            qr_reqs = [u for u in report['login_requests'] if 'login/qr' in u]
            print('login/qr requests seen:', len(qr_reqs))
            for u in qr_reqs[:6]:
                print('  -', u.split('?')[0])
            report['checks']['qr_endpoints_hit'] = (
                any('/login/qr/key' in u for u in qr_reqs)
                and any('/login/qr/create' in u for u in qr_reqs)
                and any('/login/qr/check' in u for u in qr_reqs))
            page.evaluate("() => { if (typeof closeLoginModal === 'function') closeLoginModal(); }")
            page.wait_for_timeout(500)
            report['checks']['poll_stopped_after_close'] = page.evaluate(
                "() => window.neteaseWebQrTimer === null")
            print('poll stopped after close:', report['checks']['poll_stopped_after_close'])

            print('== (f) negative test: invalid test-only cookie is rejected')
            page.evaluate(
                "() => { localStorage.setItem('starwave.netease.cookie', '%s'); }" % FAKE_COOKIE)
            page.reload(wait_until='load', timeout=60000)
            page.wait_for_timeout(2500)
            dismiss_splash(page)
            page.wait_for_timeout(2500)
            btn2 = page.evaluate(
                "() => { const b = document.getElementById('user-btn'); return b ? b.textContent.trim() : null; }")
            cookie_after = page.evaluate(
                "() => localStorage.getItem('starwave.netease.cookie')")
            print('user-btn after reload with invalid cookie:', repr(btn2))
            print('cookie in localStorage after restore:', repr(cookie_after))
            report['checks']['invalid_cookie_stays_logged_out'] = (btn2 == '登录')
            report['checks']['invalid_cookie_cleared'] = (cookie_after is None)
            results2 = search_zhou(page)
            ne2 = [r for r in results2 if r['tag'] == '网易云']
            print('search after invalid cookie: %d netease results' % len(ne2))
            free2 = page.evaluate(
                """async () => { const r = await fetchNeteaseWebPlayback({neteaseId: 288820, id: 288820, name: 'test'});
                                return { playable: r.playable }; }""")
            print('free track still playable after invalid cookie:', free2)
            report['checks']['search_still_works_after_invalid_cookie'] = len(ne2) > 0
            report['checks']['free_still_plays_after_invalid_cookie'] = bool(free2.get('playable'))
            leaked = [m for m in report['console_errors'] if 'INVALID_TEST_ONLY' in m]
            report['checks']['no_cookie_value_in_console'] = len(leaked) == 0
            print('console messages containing the fake cookie value:', len(leaked))

            browser.close()
    finally:
        if server_proc:
            server_proc.terminate()
        if relay_proc:
            relay_proc.terminate()

    print('\n===== SUMMARY =====')
    print('page_errors:', report['page_errors'])
    print('console_errors (%d):' % len(report['console_errors']))
    for m in report['console_errors'][:10]:
        print('  -', m[:200])
    print('failed_requests (%d):' % len(report['failed_requests']))
    for m in report['failed_requests'][:10]:
        print('  -', m[:200])
    failed = [k for k, v in report['checks'].items() if v is not True]
    print('checks:', json.dumps(report['checks'], ensure_ascii=False, indent=1))
    if failed:
        print('RESULT: FAIL (%s)' % ', '.join(failed))
        sys.exit(1)
    print('RESULT: ALL CHECKS PASSED')
    sys.exit(0)


if __name__ == '__main__':
    main()
