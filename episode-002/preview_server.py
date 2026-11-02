"""Temporary, exact-file-only delivery; never exposes the project directory."""
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit
import re
ROOT=Path(__file__).resolve().parent
PAGE='''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>목표를 떼었더니 · 지혜이야기 두 번째 편</title>
<style>*{box-sizing:border-box}body{margin:0;background:#111;color:#fff;font-family:system-ui,sans-serif}main{max-width:1100px;margin:auto;padding:24px;display:flex;gap:40px;align-items:center;justify-content:center;min-height:100svh}video{display:block;width:min(100%,396px);max-height:84svh;aspect-ratio:9/16;background:#000;border-radius:12px}section{max-width:390px}p{color:#c8c8c8;line-height:1.7}h1{font-size:28px;line-height:1.5}a,button{display:inline-block;border:0;border-radius:9px;padding:13px 18px;background:#efae62;color:#20170d;font:600 15px system-ui;cursor:pointer;text-decoration:none;margin:0 8px 12px 0}small{display:block;color:#aaa;line-height:1.7}@media(max-width:720px){main{padding:16px;display:block}video{margin:auto;width:100%;max-height:78svh}section{margin:24px auto}h1{font-size:22px}}</style>
<main><video id="film" controls playsinline preload="metadata" poster="/poster.jpg" aria-label="두 번째 영상"><source src="/final.mp4" type="video/mp4"></video>
<section><p>지혜이야기 · 두 번째 편</p><h1>목표를 떼었더니<br>의자가 완성됐다</h1><button id="toggle">처음부터 재생</button><a href="/download.mp4" download="wisdom-episode-002.mp4">영상 다운로드</a><p>큰 결심을 반복하던 목공 초보가<br>처음으로 의자를 완성한 이야기</p><small>1080 × 1920 · 약64초 · 60fps<br>PC와 임시 터널이 켜져 있는 동안 이용할 수 있습니다.</small><p id="status" aria-live="polite">재생 준비 중</p></section></main>
<script>const v=document.getElementById('film'),s=document.getElementById('status');document.getElementById('toggle').onclick=()=>{v.currentTime=0;v.play().catch(()=>s.textContent='영상의 재생 버튼을 눌러주세요');};function status(){s.textContent=v.error?'영상 불러오기 실패':`${v.ended?'재생 완료':v.paused?'일시 정지':'재생 중'} · ${v.currentTime.toFixed(1)} / ${Number.isFinite(v.duration)?v.duration.toFixed(1):'—'}초`;}['loadedmetadata','timeupdate','pause','play','ended','error'].forEach(e=>v.addEventListener(e,status));</script></html>'''.encode('utf-8')
class Handler(BaseHTTPRequestHandler):
 def do_HEAD(self):self.serve(False)
 def do_GET(self):self.serve(True)
 def serve(self,body):
  route=urlsplit(self.path).path
  if route in ['/','/index.html']:
   self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8');self.send_header('Content-Length',str(len(PAGE)));self.send_header('Cache-Control','no-store');self.end_headers()
   if body:self.wfile.write(PAGE)
   return
  names={'/final.mp4':('final.mp4','video/mp4'),'/download.mp4':('final.mp4','video/mp4'),'/poster.jpg':('poster.jpg','image/jpeg')}
  if route not in names:self.send_error(404);return
  name,mime=names[route];p=ROOT/name
  if not p.is_file():self.send_error(404);return
  size=p.stat().st_size;start=0;end=size-1;r=self.headers.get('Range')
  if r:
   m=re.fullmatch(r'bytes=(\d*)-(\d*)',r)
   if not m or not any(m.groups()):self.send_error(416);return
   lo,hi=m.groups()
   if lo:start=int(lo);end=min(int(hi),end) if hi else end
   else:start=max(0,size-int(hi))
   if start>end or start>=size:self.send_response(416);self.send_header('Content-Range',f'bytes */{size}');self.end_headers();return
  self.send_response(206 if r else 200);self.send_header('Content-Type',mime);self.send_header('Content-Length',str(end-start+1));self.send_header('Accept-Ranges','bytes');self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
  if r:self.send_header('Content-Range',f'bytes {start}-{end}/{size}')
  if route=='/download.mp4':self.send_header('Content-Disposition','attachment; filename="wisdom-episode-002.mp4"')
  self.end_headers()
  if body:
   try:
    with p.open('rb') as f:
     f.seek(start);remaining=end-start+1
     while remaining:
      chunk=f.read(min(262144,remaining))
      if not chunk:break
      self.wfile.write(chunk);remaining-=len(chunk)
   except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):pass
if __name__=='__main__':ThreadingHTTPServer(('127.0.0.1',8899),Handler).serve_forever()
