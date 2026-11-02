"""Serve only this episode's finished video and poster for a temporary tunnel."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
import re

ROOT = Path(__file__).resolve().parent
PAGE = '''<!doctype html><html lang="ko"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>엄마의 달력 · 첫 영상 수정본</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#101813;color:#fff8e9;font-family:system-ui,sans-serif}
main{max-width:1120px;margin:auto;padding:24px;display:flex;gap:40px;align-items:center;justify-content:center;min-height:100svh}
video{display:block;width:min(100%,396px);max-height:84svh;aspect-ratio:9/16;background:#000;border-radius:12px}
section{max-width:390px}p{color:#c6d1c7;line-height:1.7}h1{font-size:28px;line-height:1.5;margin:12px 0 24px}
a,button{display:inline-block;border:0;border-radius:9px;padding:13px 18px;background:#e9bb75;color:#17201c;font:600 15px system-ui;cursor:pointer;text-decoration:none;margin:0 8px 12px 0}
small{display:block;color:#a9b5aa;line-height:1.7;margin-top:20px}
@media(max-width:720px){main{padding:16px;display:block}video{margin:auto;width:100%;max-height:78svh}section{margin:24px auto}h1{font-size:22px}}
</style><main>
<video id="film" controls playsinline preload="metadata" poster="poster.jpg" aria-label="첫 영상 수정본"><source src="final.mp4" type="video/mp4"></video>
<section><p>지혜이야기 · 첫 영상 수정본</p><h1>엄마가 가족 단톡방에<br>달력 사진을 보낸 이유</h1>
<button id="toggle" type="button">처음부터 재생</button><a href="download.mp4" download="wisdom-episode-001-revised.mp4">영상 다운로드</a>
<p>자막 폰트와 위치, 메시지 배치와 달력 글씨를 수정했습니다.</p>
<small>1080 × 1920 · 77초<br>임시 미리보기입니다. PC와 Cloudflare 터널이 켜져 있는 동안 접속할 수 있습니다.</small>
<p id="status" aria-live="polite">재생 준비 중</p></section></main>
<script>
const v=document.getElementById('film'),s=document.getElementById('status');
document.getElementById('toggle').onclick=()=>{v.currentTime=0;v.play().catch(()=>s.textContent='영상의 재생 버튼을 눌러주세요');};
function status(){s.textContent=v.error?'영상 불러오기 실패':`${v.ended?'재생 완료':v.paused?'일시 정지':'재생 중'} · ${v.currentTime.toFixed(1)} / ${Number.isFinite(v.duration)?v.duration.toFixed(1):'—'}초`;}
['loadedmetadata','timeupdate','pause','play','ended','error'].forEach(e=>v.addEventListener(e,status));
</script></html>'''.encode('utf-8')

class Handler(BaseHTTPRequestHandler):
    def do_HEAD(self): self.serve(False)
    def do_GET(self): self.serve(True)
    def serve(self, body):
        route=urlsplit(self.path).path
        if route in ('/','/index.html'):
            self.send_response(200)
            self.send_header('Content-Type','text/html; charset=utf-8')
            self.send_header('Content-Length',str(len(PAGE)))
            self.send_header('Cache-Control','no-store')
            self.end_headers()
            if body: self.wfile.write(PAGE)
            return
        names={'/final.mp4':('final.mp4','video/mp4'),
               '/download.mp4':('final.mp4','video/mp4'),'/poster.jpg':('poster.jpg','image/jpeg')}
        if route not in names:
            self.send_error(404);return
        name,mime=names[route];path=ROOT/name
        if not path.is_file(): self.send_error(404);return
        size=path.stat().st_size;start,end=0,size-1
        request_range=self.headers.get('Range')
        if request_range:
            match=re.fullmatch(r'bytes=(\d*)-(\d*)',request_range)
            if not match or not any(match.groups()): self.send_error(416);return
            lo,hi=match.groups()
            if lo: start=int(lo);end=min(int(hi),end) if hi else end
            else: start=max(0,size-int(hi))
            if start>end or start>=size:
                self.send_response(416);self.send_header('Content-Range',f'bytes */{size}')
                self.end_headers();return
        self.send_response(206 if request_range else 200)
        self.send_header('Content-Type',mime)
        self.send_header('Content-Length',str(end-start+1))
        self.send_header('Accept-Ranges','bytes')
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        if request_range: self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
        if route=='/download.mp4':
            self.send_header('Content-Disposition','attachment; filename="wisdom-episode-001-revised.mp4"')
        self.end_headers()
        if body:
            try:
                with path.open('rb') as stream:
                    stream.seek(start);remaining=end-start+1
                    while remaining:
                        chunk=stream.read(min(262144,remaining))
                        if not chunk: break
                        self.wfile.write(chunk);remaining-=len(chunk)
            except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError): pass

if __name__=='__main__':
    ThreadingHTTPServer(('127.0.0.1',8897),Handler).serve_forever()
