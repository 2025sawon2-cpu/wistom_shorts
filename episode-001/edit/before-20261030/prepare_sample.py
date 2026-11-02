"""One-episode typography and silent local-motion trial; this is not the final film."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import math, subprocess, json

ROOT = Path(__file__).resolve().parent
FONT = 'C:/Windows/Fonts/malgun.ttf'
BOLD = 'C:/Windows/Fonts/malgunbd.ttf'
HAND = 'C:/Windows/Fonts/HANBatang.ttf'
def font(size, bold=False, hand=False):
    return ImageFont.truetype(HAND if hand else BOLD if bold else FONT, size)

def calendar(after=False):
    im = Image.open(ROOT/'images/04-calendar-blank.png').convert('RGB')
    d = ImageDraw.Draw(im)
    ink = '#4a4a3c'
    d.text((165,294), '11월', font=font(62,True),fill=ink)
    d.text((165,378), '7일 토요일 · 가족여행',font=font(36),fill=ink)
    days=['일','월','화','수','목','금','토']
    for k,day in enumerate(days):
        x=172+k*100
        d.text((x+12,455),day,font=font(25),fill='#867a65')
        d.text((x+15,506),str(k+1),font=font(31),fill=ink)
    d.ellipse((759,496,820,555),outline='#b07553',width=4)
    d.line((165,590,856,590),fill='#baa88c',width=2)
    d.text((170,628),'준비할 일',font=font(33,True),fill=ink)
    d.text((615,628),'담당',font=font(33,True),fill=ink)
    for i,item in enumerate(['교통','숙소','식당','준비물']):
        y=715+i*126
        d.text((180,y),item,font=font(45,hand=True),fill=ink)
        d.text((610,y),'엄마',font=font(45,hand=True),fill=ink)
        d.line((175,y+86,844,y+86),fill='#d8c8a9',width=2)
    if after:
        d.line((604,868,719,861),fill='#497372',width=4)
        d.text((719,844),'지은',font=font(42,True),fill='#497372')
        d.text((570,909),'19:40 예약 완료',font=font(25),fill='#497372')
    name='07-calendar-after.png' if after else '04-calendar-before.png'
    im.save(ROOT/'images'/name)
    return im

def centered(d,y,text,size,color,bold=True):
    f=font(size,bold)
    box=d.textbbox((0,0),text,font=f)
    d.text(((720-(box[2]-box[0]))/2,y),text,font=f,fill=color,stroke_width=0)

def motion_sample():
    # Smooth local displacement only, no zoom/pan; hands and head move independently.
    src=Image.open(ROOT/'images/03-mother-phone.png').convert('RGB').resize((720,1080),Image.Resampling.LANCZOS)
    w,h=src.size
    out=ROOT/'clips/03-local-motion-sample-silent.mp4'
    cmd=['ffmpeg','-y','-hide_banner','-loglevel','error','-f','rawvideo','-pixel_format','rgb24','-video_size','720x1280','-framerate','24','-i','pipe:0','-an','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',str(out)]
    p=subprocess.Popen(cmd,stdin=subprocess.PIPE)
    for n in range(144):
        t=n/24
        hand=math.sin(min(t/1.6,1)*math.pi/2)
        nod=(1-math.cos(min(max((t-1.4)/2,0),1)*math.pi))/2
        def point(x,y):
            a=math.exp(-(((x-421)/88)**2+((y-705)/86)**2)*2)
            b=math.exp(-(((x-365)/180)**2+((y-297)/220)**2)*2)
            return (x+6.5*hand*a, y-3*hand*a-3.5*nod*b)
        mesh=[]
        step=24
        for y in range(0,h,step):
            for x in range(0,w,step):
                x1=min(x+step,w);y1=min(y+step,h)
                quad=point(x,y)+point(x,y1)+point(x1,y1)+point(x1,y)
                mesh.append(((x,y,x1,y1),quad))
        moving=src.transform((w,h),Image.Transform.MESH,mesh,Image.Resampling.BILINEAR)
        frame=Image.new('RGB',(720,1280),'#17201c')
        frame.paste(moving.crop((0,30,720,990)),(0,212))
        d=ImageDraw.Draw(frame)
        centered(d,55,'엄마가 단톡방에',44,'#fff5df')
        centered(d,118,'달력 사진을 보낸 이유',43,'#e9bb75')
        d.rounded_rectangle((65,1032,655,1135),radius=14,fill='#17201c')
        centered(d,1048,'휴대폰을 넘기던',36,'#ffffff')
        centered(d,1092,'엄마의 손이 멈췄습니다',36,'#ffffff')
        centered(d,1222,'모션 시험 · 무음 · 완성본 아님',21,'#a8b5a8',False)
        p.stdin.write(frame.tobytes())
        if n in [0,40,100,143]:
            frame.save(ROOT/'clips'/f'sample-frame-{n:03}.png')
    p.stdin.close()
    if p.wait()!=0: raise RuntimeError('FFmpeg failed')
    print(out)

if __name__=='__main__':
    calendar(False);calendar(True);motion_sample()
