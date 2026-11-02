"""Exact Korean overlays for this episode; never rasterize text with a generator."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'graphics'
OUT.mkdir(exist_ok=True)
FONT = 'C:/Windows/Fonts/malgun.ttf'
BOLD = 'C:/Windows/Fonts/malgunbd.ttf'

def font(size, bold=False):
    return ImageFont.truetype(BOLD if bold else FONT, size)

def centered(d, y, text, size, fill, bold=True):
    f = font(size, bold)
    width = d.textlength(text, font=f)
    d.text(((1080-width)/2, y), text, font=f, fill=fill)

def base():
    return Image.new('RGBA', (1080,1920), (0,0,0,0))

def message(name, lines, filename, sent=False):
    im = base(); d = ImageDraw.Draw(im)
    left,right = (175,1000) if sent else (80,905)
    top = 1110
    bottom = top+116+len(lines)*65
    color = '#e8d8a8' if sent else '#fff8e9'
    d.rounded_rectangle((left,top,right,bottom), radius=30, fill=color,
                        outline='#d9cdb5', width=2)
    d.text((left+36,top+24), name, font=font(32,True),fill='#526454')
    for i,line in enumerate(lines):
        d.text((left+36,top+80+i*65),line,font=font(44,True),fill='#29332d')
    im.save(OUT/filename)
    return im

def main():
    im=base();d=ImageDraw.Draw(im)
    d.rectangle((0,0,1080,300),fill='#17201c')
    centered(d,65,'엄마가 단톡방에',66,'#fff5df')
    centered(d,155,'달력 사진을 보낸 이유',64,'#e9bb75')
    d.rectangle((0,1770,1080,1920),fill='#17201c')
    im.save(OUT/'title.png')
    message('엄마',['나도 이번에는','여행 가는 사람이 되고 싶어.'],'mother-message.png')
    message('지은',['숙소는 내가 맡을게.','오늘 여덟 시까지 예약할게.'],'daughter-reply.png',True)
    im=base();d=ImageDraw.Draw(im)
    d.rounded_rectangle((120,1120,960,1405),radius=30,fill='#fff8e9',outline='#d9cdb5',width=2)
    d.ellipse((170,1170,232,1232),fill='#497372')
    d.line([(185,1201),(198,1213),(218,1188)],fill='white',width=6)
    d.text((260,1165),'숙소 예약 완료',font=font(49,True),fill='#29332d')
    d.text((172,1260),'지은 · 오후 7:40',font=font(37),fill='#526454')
    im.save(OUT/'booking-confirmed.png')
    # Contact preview is a composition check, not a finished video.
    previews=[]
    for source,overlay in [('05-daughter-phone.png','mother-message.png'),
                           ('06-daughter-laptop.png','daughter-reply.png'),
                           ('06-daughter-laptop.png','booking-confirmed.png')]:
        frame=Image.new('RGBA',(1080,1920),'#17201c')
        art=Image.open(ROOT/'images'/source).convert('RGBA').resize((1080,1620),Image.Resampling.LANCZOS)
        frame.alpha_composite(art,(0,300))
        frame.alpha_composite(Image.open(OUT/'title.png'))
        frame.alpha_composite(Image.open(OUT/overlay))
        d=ImageDraw.Draw(frame)
        centered(d,1660,'자막 위치 · 편집 준비 화면',42,'#ffffff')
        previews.append(frame.convert('RGB').resize((360,640),Image.Resampling.LANCZOS))
    sheet=Image.new('RGB',(1080,640))
    for i,p in enumerate(previews): sheet.paste(p,(i*360,0))
    sheet.save(OUT/'text-layout-preview.jpg',quality=94)
    print(OUT)

if __name__=='__main__': main()
