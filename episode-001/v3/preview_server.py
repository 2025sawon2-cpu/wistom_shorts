"""Serve only this episode's finished video and poster for a temporary tunnel."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
import re

ROOT = Path(__file__).resolve().parent
PAGE = '''<!doctype html><html lang="ko"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>말 걸어도 돼? · 첫 영상 v3</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#101813;color:#fff8e9;font-family:system-ui,sans-serif}
main{max-width:1120px;margin:auto;padding:24px;display:flex;gap:40px;align-items:center;justify-content:center;min-height:100svh}
video{display:block;width:min(100%,396px);max-height:84svh;aspect-ratio:9/16;background:#000;border-radius:12px}
section{max-width:390px}p{color:#c6d1c7;line-height:1.7}h1{font-size:28px;line-height:1.5;margin:12px 0 24px}
a,button{display:inline-block;border:0;border-radius:9px;padding:13px 18px;background:#e9bb75;color:#17201c;font:600 15px system-ui;cursor:pointer;text-decoration:none;margin:0 8px 12px 0}
small{display:block;color:#a9b5aa;line-height:1.7;margin-top:20px}
@media(max-width:720px){main{padding:16px;display:block}video{margin:auto;width:100%;max-height:78svh}section{margin:24px auto}h1{font-size:22px}}
</style><main>
<video id="film" controls playsinline preload="metadata" poster="poster.jpg" aria-label="첫 영상 v3"><source src="final-v3.mp4" type="video/mp4"></video>
<section><p>지혜이야기 · 첫 영상 v3</p><h1>엄마, 오늘 아빠한테<br>말 걸어도 돼?</h1>
<button id="toggle" type="button">처음부터 재생</button><a href="download.mp4" download="wisdom-episode-001-v3.mp4">영상 다운로드</a>
<p>책의 생각에서 새로 쓴 이야기 · 한국어 내레이션 · 일러스트와 작은 움직임</p>
<small>1080 × 1920 · 112초<br>PC와 임시 터널이 켜져 있는 동안 이용할 수 있습니다.</small>
<p id="status" aria-live="polite">재생 준비 중</p></section></main>
<script>
const v=document.getElementById('film'),s=document.getElementById('status');
document.getElementById('toggle').onclick=()=>{v.currentTime=0;v.play().catch(()=>s.textContent='영상의 재생 버튼을 눌러주세요');};
function status(){s.textContent=v.error?'영상 불러오기 실패':`${v.ended?'재생 완료':v.paused?'일시 정지':'재생 중'} · ${v.currentTime.toFixed(1)} / ${Number.isFinite(v.duration)?v.duration.toFixed(1):'—'}초`;}
['loadedmetadata','timeupdate','pause','play','ended','error'].forEach(e=>v.addEventListener(e,status));
</script></html>'''.encode('utf-8')

PAGE_V4 = (PAGE.decode('utf-8').replace('첫 영상 v3', '속도·자막 수정본 v4')
           .replace('src="final-v3.mp4"', 'src="/final-v4.mp4"')
           .replace('poster="poster.jpg"', 'poster="/poster-v4.jpg"')
           .replace('href="download.mp4"', 'href="/download-v4.mp4"')
           .replace('wisdom-episode-001-v3.mp4', 'wisdom-episode-001-v4.mp4')
           .replace('1080 × 1920 · 112초', '1080 × 1920 · 65초')
           .replace('책의 생각에서 새로 쓴 이야기 · 한국어 내레이션 · 일러스트와 작은 움직임',
                    '긴 쉼을 줄인 빠른 진행 · 노란 대사 두 줄 · 의미 단위 자막')
           ).encode('utf-8')

PAGE_V5 = (PAGE_V4.decode('utf-8').replace('속도·자막 수정본 v4','대사 글꼴 수정본 v5')
           .replace('final-v4.mp4','final-v5.mp4').replace('poster-v4.jpg','poster-v5.jpg')
           .replace('download-v4.mp4','download-v5.mp4').replace('wisdom-episode-001-v4.mp4','wisdom-episode-001-v5.mp4')
           .replace('긴 쉼을 줄인 빠른 진행 · 노란 대사 두 줄 · 의미 단위 자막',
                    '노란 대사 명조체 · 화면마다 쌍따옴표 · 의미 단위 두 줄 자막')
           ).encode('utf-8')

PAGE_V6 = (PAGE_V5.decode('utf-8').replace('대사 글꼴 수정본 v5','움직임 수정본 v6')
           .replace('final-v5.mp4','final-v6.mp4').replace('poster-v5.jpg','poster-v6.jpg')
           .replace('download-v5.mp4','download-v6.mp4').replace('wisdom-episode-001-v5.mp4','wisdom-episode-001-v6.mp4')
           .replace('노란 대사 명조체 · 화면마다 쌍따옴표 · 의미 단위 두 줄 자막',
                    '더 매끈한 그림 움직임 · 노란 명조 대사 · 화면마다 쌍따옴표')
           .replace('1080 × 1920 · 65초','1080 × 1920 · 65초 · 60fps')
           ).encode('utf-8')

PAGE_V7 = (PAGE_V6.decode('utf-8').replace('움직임 수정본 v6','줌인·클로즈업 수정본 v7')
           .replace('final-v6.mp4','final-v7.mp4').replace('poster-v6.jpg','poster-v7.jpg')
           .replace('download-v6.mp4','download-v7.mp4').replace('wisdom-episode-001-v6.mp4','wisdom-episode-001-v7.mp4')
           .replace('더 매끈한 그림 움직임 · 노란 명조 대사 · 화면마다 쌍따옴표',
                    '딸 표정 줌인 · 아버지 표정 클로즈업 · 공책과 손 클로즈업')
           ).encode('utf-8')

class Handler(BaseHTTPRequestHandler):
    def do_HEAD(self): self.serve(False)
    def do_GET(self): self.serve(True)
    def serve(self, body):
        route=urlsplit(self.path).path
        if route in ('/','/index.html','/v4','/v4/','/v5','/v5/','/v6','/v6/','/v7','/v7/'):
            page = PAGE_V7 if route.startswith('/v7') else PAGE_V6 if route.startswith('/v6') else PAGE_V5 if route.startswith('/v5') else PAGE_V4 if route.startswith('/v4') else PAGE
            self.send_response(200)
            self.send_header('Content-Type','text/html; charset=utf-8')
            self.send_header('Content-Length',str(len(page)))
            self.send_header('Cache-Control','no-store')
            self.end_headers()
            if body: self.wfile.write(page)
            return
        names={'/final-v3.mp4':('final-v3.mp4','video/mp4'),
               '/download.mp4':('final-v3.mp4','video/mp4'),'/poster.jpg':('poster.jpg','image/jpeg'),
               '/final-v4.mp4':('final-v4.mp4','video/mp4'),
               '/download-v4.mp4':('final-v4.mp4','video/mp4'),
               '/poster-v4.jpg':('poster-v4.jpg','image/jpeg'),
               '/final-v5.mp4':('final-v5.mp4','video/mp4'),
               '/download-v5.mp4':('final-v5.mp4','video/mp4'),
               '/poster-v5.jpg':('poster-v5.jpg','image/jpeg'),
               '/final-v6.mp4':('final-v6.mp4','video/mp4'),
               '/download-v6.mp4':('final-v6.mp4','video/mp4'),
               '/poster-v6.jpg':('poster-v6.jpg','image/jpeg'),
               '/final-v7.mp4':('final-v7.mp4','video/mp4'),
               '/download-v7.mp4':('final-v7.mp4','video/mp4'),
               '/poster-v7.jpg':('poster-v7.jpg','image/jpeg')}
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
        if route in ('/download.mp4','/download-v4.mp4','/download-v5.mp4','/download-v6.mp4','/download-v7.mp4'):
            version = 'v7' if route=='/download-v7.mp4' else 'v6' if route=='/download-v6.mp4' else 'v5' if route=='/download-v5.mp4' else 'v4' if route=='/download-v4.mp4' else 'v3'
            self.send_header('Content-Disposition',f'attachment; filename="wisdom-episode-001-{version}.mp4"')
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
    ThreadingHTTPServer(('127.0.0.1',8898),Handler).serve_forever()
