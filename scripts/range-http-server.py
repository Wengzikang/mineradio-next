# -*- coding: utf-8 -*-
"""TEST-ONLY range-capable static server for Phase 3 verification.

Why: `python3 -m http.server` ignores Range requests (answers 200 with the
full file), so Chromium seeking in a long mp3 restarts playback from ~0.
Real hosting (GitHub Pages / Vercel) supports Range. This server adds
single-range 206 responses; nothing else. Serves web/public on 127.0.0.1:4174.
Not part of the app (not copied by `npm run build:web`).
Usage: python3 scripts/range-http-server.py [port] [directory]
"""
import functools
import http.server
import os
import re
import sys

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 4174
DIRECTORY = sys.argv[2] if len(sys.argv) > 2 else os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', 'web', 'public')


class RangeHandler(http.server.SimpleHTTPRequestHandler):
    def send_head(self):
        path = self.translate_path(self.path)
        if not os.path.isfile(path):
            return super().send_head()
        range_hdr = self.headers.get('Range')
        if not range_hdr:
            return super().send_head()
        m = re.match(r'bytes=(\d*)-(\d*)$', range_hdr.strip())
        if not m:
            return super().send_head()
        size = os.path.getsize(path)
        start = int(m.group(1)) if m.group(1) else 0
        end = int(m.group(2)) if m.group(2) else size - 1
        end = min(end, size - 1)
        if start >= size or start > end:
            self.send_response(416)
            self.send_header('Content-Range', 'bytes */%d' % size)
            self.end_headers()
            return None
        ctype = self.guess_type(path)
        f = open(path, 'rb')
        f.seek(start)
        self.send_response(206)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Range', 'bytes %d-%d/%d' % (start, end, size))
        self.send_header('Content-Length', str(end - start + 1))
        self.send_header('Accept-Ranges', 'bytes')
        self.end_headers()
        self._range_remaining = end - start + 1
        return f

    def copyfile(self, source, outputfile):
        remaining = getattr(self, '_range_remaining', None)
        if remaining is None:
            return super().copyfile(source, outputfile)
        while remaining > 0:
            chunk = source.read(min(65536, remaining))
            if not chunk:
                break
            outputfile.write(chunk)
            remaining -= len(chunk)
        self._range_remaining = None


if __name__ == '__main__':
    handler = functools.partial(RangeHandler, directory=DIRECTORY)
    with http.server.ThreadingHTTPServer(('127.0.0.1', PORT), handler) as httpd:
        print('range server on 127.0.0.1:%d serving %s' % (PORT, DIRECTORY), flush=True)
        httpd.serve_forever()
