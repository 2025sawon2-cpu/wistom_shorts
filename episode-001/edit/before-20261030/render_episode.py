"""One-film edit using preserved art, five motion clips and the web narration."""
from pathlib import Path
import subprocess,json,sys
from PIL import Image,ImageDraw,ImageFont
from compose_text import font,centered

ROOT=Path(__file__).resolve().parent
BUILD=ROOT/'edit'; BUILD.mkdir(exist_ok=True)
W,H,FPS=1080,1920,24
def run(args):
    subprocess.run(['ffmpeg','-y','-hide_banner','-loglevel','error',*args],check=True,cwd=ROOT)

# Caption text follows the script; timing follows the downloaded speech.
CUES=[
(0,2.48,'엄마가 올린\n달력 사진 한 장에'),(2.48,5.55,'가족 단톡방이\n조용해졌습니다'),
(5.92,8.5,'며칠 전,\n엄마가 물었습니다'),(9.05,10.95,'“숙소는 어디로 할까?”'),
(11.35,13.45,'아빠는 “아무 데나”'),(13.6,16.1,'식당을 묻자 딸은'),(16.1,17.95,'“맛있는 데로”'),
(18.35,20.55,'그런데 막상 고르면'),(20.65,22.52,'“거긴 멀어”'),(22.65,24.05,'“다른 데는 없어?”'),
(24.65,27.9,'휴대폰을 넘기던\n엄마의 손이 멈췄습니다'),
(28.35,32.55,'교통, 숙소,\n식당, 준비물'),(33.05,34.98,'달력에 적힌 담당자는'),(34.98,36.95,'전부 엄마였습니다'),
(37.45,40.95,'엄마는 그 사진 아래\n한 줄을 보냈습니다'),
(41.35,42.75,'“나도 이번에는'),(42.75,45.05,'여행 가는 사람이\n되고 싶어”'),
(45.35,48.05,'한동안 답이 없었습니다'),(48.65,50.55,'잠시 뒤, 딸이 썼습니다'),
(50.95,52.65,'“숙소는 내가 맡을게'),(52.8,55.15,'오늘 여덟 시까지\n예약할게”'),
(55.65,57.25,'일곱 시 사십 분'),(57.25,58.88,'예약을 마친 딸이'),
(58.88,61.05,'달력의 ‘엄마’를 지우고'),(61.05,62.95,'자기 이름을 적었습니다'),
(63.15,65.18,'남은 일은 여전했지만'),(65.18,67.05,'이제 한 줄은'),
(67.05,68.95,'엄마의 몫이 아니었습니다'),
(69.5,72.5,'다음에는 이렇게\n물어보면 어떨까요'),(72.9,77.2,'“내가 무엇을,\n언제까지 맡으면 될까?”')]

def stamp(t):
    cs=round(t*100);return f'{cs//360000}:{cs//6000%60:02}:{cs//100%60:02}.{cs%100:02}'

def subtitles():
    header='''[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 2
[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Malgun Gothic,64,&H00FFFFFF,&H000000FF,&H0017201C,&H0017201C,-1,0,0,0,100,100,0,0,3,18,0,2,70,70,220,1
[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
'''
    rows=[];srt=[]
    for i,(a,b,txt) in enumerate(CUES,1):
        rows.append(f'Dialogue: 0,{stamp(a)},{stamp(b)},Default,,0,0,0,,{{\\fad(70,70)}}'+txt.replace('\n','\\N'))
        def srtt(t):
            ms=round(t*1000);return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'
        srt.append(f'{i}\n{srtt(a)} --> {srtt(b)}\n{txt}\n')
    (ROOT/'captions.ass').write_text(header+'\n'.join(rows),encoding='utf-8-sig')
    (ROOT/'captions.srt').write_text('\n'.join(srt),encoding='utf-8-sig')

def opening():
    im=Image.new('RGB',(1080,1620),'#e8dfcf');d=ImageDraw.Draw(im)
    d.text((82,60),'가족 대화',font=font(44,True),fill='#29332d')
    d.line((70,142,1010,142),fill='#c9bdab',width=2)
    d.text((84,190),'엄마',font=font(35,True),fill='#526454')
    art=Image.open(ROOT/'images/04-calendar-before.png').convert('RGB').resize((570,855),Image.Resampling.LANCZOS)
    im.paste(art,(82,265))
    d.rounded_rectangle((82,1155,700,1260),radius=28,fill='#fff8e9')
    d.text((118,1180),'사진 한 장을 보냈습니다',font=font(38),fill='#29332d')
    im.save(BUILD/'opening.png')

# Boundaries are rounded to the video frame grid, so the concat has no drift.
SCENES=[
('opening',0,5.75,'edit/opening.png',False),
('family',5.75,18.17,'clips/02-family-veo.mp4',True),
('mother',18.17,28.08,'clips/03-mother-phone-veo.mp4',True),
('calendar',28.08,37.08,'images/04-calendar-before.png',False),
('reading',37.08,48.25,'clips/05-daughter-phone-veo.mp4',True),
('booking',48.25,58.92,'clips/06-daughter-laptop-veo.mp4',True),
('before',58.92,60.75,'images/04-calendar-before.png',False),
('after',60.75,69.17,'images/07-calendar-after.png',False),
('rest',69.17,77.25,'clips/08-mother-rest-veo.mp4',True)]

def render_scene(name,a,b,source,moving):
    n=round(b*FPS)-round(a*FPS); duration=n/FPS
    out=BUILD/(name+'.mp4')
    args=['-i',source] if moving else ['-loop','1','-framerate',str(FPS),'-i',source]
    args+=['-i','graphics/title.png']
    if moving:
        vf=f'[0:v]crop=720:1080:0:100,setpts={duration/6:.8f}*PTS,scale=1080:1620:flags=lanczos,fps=24,tpad=stop_mode=clone:stop_duration=1'
    else:
        vf='[0:v]scale=1080:1620:flags=lanczos,setsar=1'
    vf+=',pad=1080:1920:0:300:color=0x17201c[v0];[v0][1:v]overlay=0:0[v1]'
    last='v1';extra=[]
    if name=='reading': extra=[('mother-message.png',41.1-a,48.25-a)]
    if name=='booking': extra=[('daughter-reply.png',50.6-a,55.4-a),('booking-confirmed.png',55.4-a,duration)]
    for i,(png,start,end) in enumerate(extra,2):
        args+=['-i','graphics/'+png]
        nxt=f'v{i}'
        vf+=f';[{last}][{i}:v]overlay=0:0:enable=\'between(t,{start:.3f},{end:.3f})\'[{nxt}]'
        last=nxt
    args+=['-filter_complex',vf,'-map',f'[{last}]','-frames:v',str(n),'-an','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p',str(out)]
    run(args)
    print(f'{name}: {n} frames',flush=True)
    return out

def main():
    subtitles();opening()
    paths=[BUILD/(s[0]+'.mp4') for s in SCENES] if '--finish-only' in sys.argv else [render_scene(*scene) for scene in SCENES]
    (BUILD/'concat.txt').write_text('\n'.join("file '"+p.as_posix()+"'" for p in paths),encoding='utf-8')
    run(['-f','concat','-safe','0','-i',str(BUILD/'concat.txt'),'-i','audio/narration-arlo.wav',
         '-vf','ass=captions.ass,fade=t=out:st=76.85:d=0.4','-af','loudnorm=I=-16:TP=-1.5:LRA=7,apad',
         '-t','77.25','-c:v','libx264','-preset','fast','-crf','18','-c:a','aac','-b:a','192k',
         '-pix_fmt','yuv420p','-movflags','+faststart','final.mp4'])
    (BUILD/'timeline.json').write_text(json.dumps(SCENES,ensure_ascii=False,indent=2),encoding='utf-8')
    print(ROOT/'final.mp4',flush=True)

if __name__=='__main__':main()
