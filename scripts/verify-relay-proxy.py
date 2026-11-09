# -*- coding: utf-8 -*-
"""TEST-ONLY local relay for Playwright verification.

Why: this VM's egress proxy MITMs TLS with a private CA (see
CURL_CA_BUNDLE=/run/hatch/egress-tls/ca-bundle.pem). curl works, but
Chromium's CONNECT to the proxy fails with ERR_TUNNEL_CONNECTION_FAILED
when credentials are attached, and the MITM cert is untrusted by Chromium.
This relay forwards Chromium's CONNECT verbatim to the egress proxy
(no credentials attached) so the browser can reach the internet;
combined with --ignore-certificate-errors in verify-phase1.py it lets
the real browser test run. It is test scaffolding only: it is NOT part
of the app, NOT copied by `npm run build:web` (build only copies
web/public), and holds no credentials. Start it before verify-phase1.py
or let verify-phase1.py spawn it.
Usage: python3 scripts/verify-relay-proxy.py   # listens on 127.0.0.1:18082
"""
import socket, threading, sys
UPSTREAM_HOST = '198.19.0.1'  # egress proxy IPv4 (hostname also resolves to a broken IPv6 listener for Chromium)
UPSTREAM_PORT = 3128
srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
srv.bind(('127.0.0.1', 18082))
srv.listen(5)
print('relay listening', flush=True)

def pump(src, dst, tag):
    try:
        while True:
            d = src.recv(65536)
            if not d: break
            dst.sendall(d)
    except Exception as e:
        print(tag, 'pump end', e, flush=True)
    try: dst.shutdown(socket.SHUT_WR)
    except Exception: pass

while True:
    client, addr = srv.accept()
    print('accepted', addr, flush=True)
    def handle(client):
        try:
            client.settimeout(10)
            req = b''
            while b'\r\n\r\n' not in req and len(req) < 16384:
                c = client.recv(4096)
                if not c: break
                req += c
            print('CONNECT-REQ:', repr(req), flush=True)
            up = socket.create_connection((UPSTREAM_HOST, UPSTREAM_PORT), timeout=10)
            up.sendall(req)
            resp = b''
            up.settimeout(10)
            try:
                while b'\r\n\r\n' not in resp:
                    c = up.recv(4096)
                    if not c: break
                    resp += c
            except Exception as e:
                print('resp read err', e, flush=True)
            print('PROXY-RESP:', repr(resp[:600]), flush=True)
            client.sendall(resp)
            is_connect = req.startswith(b'CONNECT')
            first_line = resp.split(b'\r\n')[0]
            # CONNECT tunnels succeed only on 200; plain-HTTP proxy requests
            # forward whatever the origin returns (200, 206, 403, ...) and
            # stream the body. (Bug history: checking b'200' in the status
            # line truncated 206 Partial Content audio responses.)
            if is_connect and b'200' not in first_line:
                client.close(); up.close(); return
            client.settimeout(None); up.settimeout(None)
            t1 = threading.Thread(target=pump, args=(client, up, 'c2u'), daemon=True)
            t2 = threading.Thread(target=pump, args=(up, client, 'u2c'), daemon=True)
            t1.start(); t2.start()
            t1.join(); t2.join()
        except Exception as e:
            print('handle err', repr(e), flush=True)
        finally:
            try: client.close()
            except Exception: pass
    threading.Thread(target=handle, args=(client,), daemon=True).start()
