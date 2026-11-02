"""PC-only production library. Python standard library; no YouTube API or worker."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
import json
import re
import threading

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parent
STATE = HERE / 'library.json'
PRODUCTION = HERE / 'production.json'
LOCK = threading.Lock()
PORT = 8901


def read_library():
    return json.loads(STATE.read_text(encoding='utf-8'))


class Handler(BaseHTTPRequestHandler):
    def reply(self, code, value):
        data = json.dumps(value, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self):
        # Only the page on this loopback server may edit metadata.
        if self.headers.get('Origin') != f'http://127.0.0.1:{PORT}':
            self.reply(403, {'error': '이 PC의 관리페이지에서 저장해주세요.'})
            return
        if urlsplit(self.path).path != '/library':
            self.reply(404, {'error': '없는 경로입니다.'})
            return
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 65536:
                raise ValueError('저장할 내용의 크기를 확인해주세요.')
            change = json.loads(self.rfile.read(length))
            title, description = change['title'], change['description']
            if not isinstance(title, str) or not title.strip() or len(title) > 100:
                raise ValueError('제목은 1~100자로 입력해주세요.')
            if not isinstance(description, str) or len(description) > 5000:
                raise ValueError('설명은 5,000자 이내로 입력해주세요.')
            if '<' in title or '>' in title or '<' in description or '>' in description:
                raise ValueError('제목과 설명에 꺾쇠 문자는 사용할 수 없습니다.')
            with LOCK:
                data = read_library()
                item = next((x for x in data if x['id'] == change['id']), None)
                if item is None:
                    raise ValueError('영상을 찾을 수 없습니다.')
                item['title'], item['description'] = title.strip(), description.strip()
                temp = STATE.with_suffix('.tmp')
                temp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
                temp.replace(STATE)
            self.reply(200, {'saved': True})
        except (KeyError, TypeError, ValueError) as error:
            self.reply(400, {'error': str(error)})
        except OSError:
            self.reply(500, {'error': '파일을 저장하지 못했습니다. 다시 시도해주세요.'})

    def do_HEAD(self):
        self.serve(False)

    def do_GET(self):
        self.serve(True)

    def serve(self, body):
        route = urlsplit(self.path).path
        if route == '/production':
            try:
                data = json.loads(PRODUCTION.read_text(encoding='utf-8'))
            except (OSError, ValueError):
                self.reply(503, {'error': '제작 상태를 읽지 못했습니다.'})
                return
            if body:
                self.reply(200, data)
            else:
                self.send_response(200)
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
            return
        if route == '/library':
            data = read_library()
            for item in data:
                item['available'] = (PROJECT / item['file']).is_file()
            if body:
                self.reply(200, data)
            else:
                self.send_response(200)
                self.end_headers()
            return
        static = {'/': ('index.html', 'text/html; charset=utf-8'),
                  '/style.css': ('style.css', 'text/css; charset=utf-8'),
                  '/app.js': ('app.js', 'text/javascript; charset=utf-8'),
                  '/story-options': ('story-options.json', 'application/json; charset=utf-8'),
                  '/brand.svg': ('brand.svg', 'image/svg+xml')}
        download = False
        if route in static:
            name, mime = static[route]
            path = HERE / name
        else:
            match = re.fullmatch(r'/media/(episode-\d{3,})/(video|poster|download)', route)
            if not match:
                self.send_error(404)
                return
            ident, kind = match.groups()
            item = next((x for x in read_library() if x['id'] == ident), None)
            if not item:
                self.send_error(404)
                return
            path = (PROJECT / item['poster' if kind == 'poster' else 'file']).resolve()
            if not path.is_relative_to(PROJECT):
                self.send_error(404)
                return
            mime = 'image/jpeg' if kind == 'poster' else 'video/mp4'
            download = kind == 'download'
        if not path.is_file():
            self.send_error(404)
            return
        size = path.stat().st_size
        start, end = 0, size - 1
        requested = self.headers.get('Range')
        if requested:
            match = re.fullmatch(r'bytes=(\d*)-(\d*)', requested)
            if not match or not any(match.groups()):
                self.send_error(416)
                return
            lo, hi = match.groups()
            if lo:
                start = int(lo)
                end = min(int(hi), end) if hi else end
            else:
                start = max(0, size - int(hi))
            if start > end or start >= size or (not lo and int(hi) == 0):
                self.send_response(416)
                self.send_header('Content-Range', f'bytes */{size}')
                self.end_headers()
                return
        self.send_response(206 if requested else 200)
        self.send_header('Content-Type', mime)
        self.send_header('Content-Length', str(end - start + 1))
        self.send_header('Accept-Ranges', 'bytes')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.send_header('Content-Security-Policy', "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; media-src 'self'; connect-src 'self'; frame-ancestors 'none'")
        if requested:
            self.send_header('Content-Range', f'bytes {start}-{end}/{size}')
        if download:
            self.send_header('Content-Disposition', f'attachment; filename="{ident}-{item["version"]}.mp4"')
        self.end_headers()
        if body:
            try:
                with path.open('rb') as stream:
                    stream.seek(start)
                    remaining = end - start + 1
                    while remaining:
                        chunk = stream.read(min(262144, remaining))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        remaining -= len(chunk)
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                pass


if __name__ == '__main__':
    print(f'Production library: http://127.0.0.1:{PORT}', flush=True)
    ThreadingHTTPServer(('127.0.0.1', PORT), Handler).serve_forever()
