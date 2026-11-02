"""Change only dialogue font/quote pairs; reuse v4 narration clips and audio."""
import hashlib, json, subprocess
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import render_v3 as base

ROOT=base.ROOT
EDIT=ROOT/'edit-v5'
EDIT.mkdir(exist_ok=True)
DIALOGUE_FONT='C:/Windows/Fonts/NotoSerifKR-VF.ttf'
DIALOGUE_SIZE=70

def dialogue_font():
    f=ImageFont.truetype(DIALOGUE_FONT,DIALOGUE_SIZE)
    f.set_variation_by_name('Bold')
    return f

def plate(rows):
    im=Image.new('RGBA',(1080,1920),(0,0,0,0))
    d=ImageDraw.Draw(im);f=dialogue_font()
    assert len(rows)<=2
    for i,row in enumerate(rows):
        assert d.textlength(row,font=f)<=940, row
        b=d.textbbox((0,0),row,font=f,stroke_width=5)
        cy=1470+(i-(len(rows)-1)/2)*84
        d.text(((1080-b[2]-b[0])/2,cy-(b[3]+b[1])/2),row,
               font=f,fill='#FFE35C',stroke_width=5,stroke_fill='black')
    return im

def render():
    cues=json.loads((ROOT/'edit-v4/timed-cues.json').read_text(encoding='utf-8'))
    paths=[];art_start=0;previous_art=None;changed=[]
    for i,c in enumerate(cues):
        a,b=c['display_start'],c['display_end']
        if c['art']!=previous_art:art_start=a;previous_art=c['art']
        if not c['dialogue']:
            paths.append(ROOT/'edit-v4'/f'cue-{i:02}.mp4')
            continue
        rows=c['rows'].copy()
        rows[0]='“'+rows[0].lstrip('“"')
        rows[-1]=rows[-1].rstrip('”"')+'”'
        c['rows']=rows;c['text']=' '.join(rows)
        assert c['text'].startswith('“') and c['text'].endswith('”')
        overlay=Image.open(ROOT/'graphics/title.png').convert('RGBA')
        overlay.alpha_composite(plate(rows))
        png=EDIT/f'overlay-{i:02}.png';overlay.save(png)
        out=EDIT/f'cue-{i:02}.mp4'
        vf=f'crop=iw:iw:0:(ih-iw)/2,scale=1080:1080:flags=lanczos,setsar=1,pad=1080:1920:0:{base.ART_Y}:color=black[art];[art][1:v]overlay=0:0[v]'
        base.run(['-stream_loop','-1','-ss',str(a-art_start),'-i',str(ROOT/'edit'/f'{c["art"]}-cycle.mp4'),
                  '-i',str(png),'-filter_complex',vf,'-map','[v]','-frames:v',str(round((b-a)*base.FPS)),
                  '-an','-c:v','libx264','-crf','18','-preset','fast','-pix_fmt','yuv420p',str(out)])
        changed.append(i);paths.append(out)
        print(f'Dialogue {i+1}: {c["text"]}',flush=True)
    assert ''.join(base.norm(c['text']) for c in cues)==''.join(base.norm(t) for t in base.LINES)
    listing=EDIT/'concat.txt'
    listing.write_text('\n'.join("file '"+p.as_posix()+"'" for p in paths),encoding='utf-8')
    duration=json.loads((ROOT/'edit-v4/duration.json').read_text(encoding='utf-8'))['seconds']
    # Preserve the accepted v4 AAC packets, pacing and all non-dialogue pictures.
    base.run(['-f','concat','-safe','0','-i',str(listing),'-i',str(ROOT/'final-v4.mp4'),
              '-map','0:v','-map','1:a','-c','copy','-t',str(duration),'-movflags','+faststart',
              str(ROOT/'final-v5.mp4')])
    def stamp(t):
        ms=round(t*1000)
        return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'
    (ROOT/'captions-v5.srt').write_text('\n\n'.join(
        f'{i+1}\n{stamp(c["display_start"])} --> {stamp(c["display_end"])}\n'+'\n'.join(c['rows'])
        for i,c in enumerate(cues)),encoding='utf-8-sig')
    (EDIT/'timed-cues.json').write_text(json.dumps(cues,ensure_ascii=False,indent=2),encoding='utf-8')
    (EDIT/'font.json').write_text(json.dumps({'name':'Noto Serif KR Bold','file':DIALOGUE_FONT,
        'size':DIALOGUE_SIZE,'stroke':5,'color':'#FFE35C','changed_cues':[i+1 for i in changed]},indent=2),encoding='utf-8')

if __name__=='__main__':render()
