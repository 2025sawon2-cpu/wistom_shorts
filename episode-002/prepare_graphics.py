"""Prepare this episode's editorial typography; never substitute for motion QA."""
from pathlib import Path
import json,re
from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parent
OUT=ROOT/'edit'
OUT.mkdir(exist_ok=True)
def font(size,dialogue=False):
    f=ImageFont.truetype('C:/Windows/Fonts/NotoSerifKR-VF.ttf' if dialogue else 'C:/Windows/Fonts/NotoSansKR-VF.ttf',size)
    f.set_variation_by_name('Bold');return f
def centered(im,text,cy,size,color,stroke=0,dialogue=False):
    d=ImageDraw.Draw(im);f=font(size,dialogue);b=d.textbbox((0,0),text,font=f,stroke_width=stroke)
    assert b[2]-b[0]<=1000,text
    d.text(((1080-b[2]-b[0])/2,cy-(b[3]+b[1])/2),text,font=f,fill=color,stroke_width=stroke,stroke_fill='black')
def title():
    im=Image.new('RGBA',(1080,1920),(0,0,0,0))
    centered(im,'목표를 떼었더니',210,88,'white')
    centered(im,'의자가 완성됐다',325,100,'#FF982F')
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
    p=json.loads((ROOT/'caption-plan.json').read_text(encoding='utf-8'))
    lines=(ROOT/'audio/narration.txt').read_text(encoding='utf-8').splitlines()
    normal=lambda t:re.sub('[^가-힣A-Za-z0-9]','',t)
    count=0
    for entry,line in zip(p,lines):
        assert normal(''.join(''.join(s) for s in entry['screens']))==normal(line)
        for rows in entry['screens']:
            im=title();im.alpha_composite(plate(rows,line.startswith('“')));im.save(OUT/f'overlay-{count:02}.png');count+=1
    title().save(OUT/'title.png')
    samples=[('01-plans',0),('03-conversation',8),('06-planing',14),('08-first-chair',18)]
    sheet=Image.new('RGB',(1080,960),'#181818')
    for i,(name,caption) in enumerate(samples):
        im=Image.new('RGBA',(1080,1920),'black');art=Image.open(ROOT/'images'/(name+'.png')).convert('RGBA').resize((1080,1080),Image.Resampling.LANCZOS)
        im.alpha_composite(art,(0,490));im.alpha_composite(Image.open(OUT/f'overlay-{caption:02}.png').convert('RGBA'))
        sheet.paste(im.convert('RGB').resize((270,480)),(i*270,0))
    # Lower row previews original assets only, not timed or completed video.
    for i,name in enumerate(['02-tools','04-timber','07-adjust','09-removal']):
        art=Image.open(ROOT/'images'/(name+'.png')).convert('RGB').resize((270,270),Image.Resampling.LANCZOS);sheet.paste(art,(i*270,560))
    sheet.save(OUT/'layout-preview.jpg',quality=95)
    print(f'{count} subtitle overlays prepared and validated.')
if __name__=='__main__':prepare()
