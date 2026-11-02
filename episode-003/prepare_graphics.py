"""Episode-specific title and manually broken meaning-unit subtitles."""
from pathlib import Path
import json,re
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parent
OUT=ROOT/'edit';OUT.mkdir(exist_ok=True)
def font(size,dialogue=False):
    f=ImageFont.truetype('C:/Windows/Fonts/NotoSerifKR-VF.ttf' if dialogue else 'C:/Windows/Fonts/NotoSansKR-VF.ttf',size)
    f.set_variation_by_name('Bold');return f
def centered(im,text,cy,size,color,stroke=0,dialogue=False):
    d=ImageDraw.Draw(im);f=font(size,dialogue);b=d.textbbox((0,0),text,font=f,stroke_width=stroke)
    assert b[2]-b[0]<=1000,text
    d.text(((1080-b[2]-b[0])/2,cy-(b[3]+b[1])/2),text,font=f,fill=color,stroke_width=stroke,stroke_fill='black')
def title():
    im=Image.new('RGBA',(1080,1920),(0,0,0,0))
    centered(im,'수선집에서',210,96,'white')
    centered(im,'처음 거절한 날',325,100,'#FF982F')
    return im
def plate(rows,dialogue):
    im=Image.new('RGBA',(1080,1920),(0,0,0,0));d=ImageDraw.Draw(im);size=70 if dialogue else 67
    assert len(rows)<=2
    if dialogue:assert rows[0].startswith('“') and rows[-1].endswith('”')
    for i,row in enumerate(rows):
        assert d.textlength(row,font=font(size,dialogue))<=940,row
        centered(im,row,1470+(i-(len(rows)-1)/2)*84,size,'#FFE35C' if dialogue else 'white',5 if dialogue else 7,dialogue)
    return im
def prepare():
    plan=json.loads((ROOT/'caption-plan.json').read_text(encoding='utf-8'))
    lines=(ROOT/'audio/narration.txt').read_text(encoding='utf-8').splitlines()
    normal=lambda t:re.sub('[^가-힣A-Za-z0-9]','',t)
    assert len(plan)==len(lines)
    count=0;widths=[]
    for e,line in zip(plan,lines):
        assert len(e['screens'])==len(e['shots'])
        assert normal(''.join(''.join(s) for s in e['screens']))==normal(line),line
        for rows in e['screens']:
            im=title();im.alpha_composite(plate(rows,line.startswith('“')));im.save(OUT/f'overlay-{count:02}.png');count+=1
            widths.extend(ImageDraw.Draw(im).textlength(row,font=font(70 if line.startswith('“') else 67,line.startswith('“'))) for row in rows)
    title().save(OUT/'title.png')
    (OUT/'typography-check.json').write_text(json.dumps({'screens':count,'script_lines':len(lines),'max_text_width':max(widths),'dialogue_font':'Noto Serif KR Bold','narration_font':'Noto Sans KR Bold','title':['수선집에서','처음 거절한 날'],'dialogue_quotes':'each screen has complete pair'},ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'{count} subtitle overlays validated; maximum width {max(widths):.1f}px.')
if __name__=='__main__':prepare()
