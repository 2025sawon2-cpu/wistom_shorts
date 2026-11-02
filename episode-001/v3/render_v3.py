"""Edit this one film; requires the downloaded web narration and its ASR timings."""
from pathlib import Path
import difflib, json, math, re, subprocess, sys
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
EDIT = ROOT / 'edit'
EDIT.mkdir(exist_ok=True)
FPS, W, H, ART_Y = 24, 1080, 1920, 490
FONT = 'C:/Windows/Fonts/NotoSansKR-VF.ttf'
ARTS = ['01-offer','01-offer','01-offer','06-rest','02-withdraw',
        '02-withdraw','03-question','03-question','02-withdraw',
        '04-apology','04-apology','04-apology','04-apology',
        '05-together','05-together','06-rest','04-apology',
        '03-question','02-withdraw','06-rest','04-apology',
        '05-together','05-together']
LINES = [x.strip() for x in (ROOT/'audio/narration.txt').read_text(encoding='utf-8').splitlines() if x.strip()]

def font(size):
    f = ImageFont.truetype(FONT, size)
    f.set_variation_by_name('Bold')
    return f

def centered(im, text, cy, size, color, stroke=0):
    d = ImageDraw.Draw(im); f = font(size)
    b = d.textbbox((0,0),text,font=f,stroke_width=stroke)
    if b[2]-b[0] > 1000:
        raise ValueError(f'Text exceeds safe width: {text}')
    d.text(((W-b[2]+b[0])/2-b[0],cy-(b[3]-b[1])/2-b[1]),text,
           font=f,fill=color,stroke_width=stroke,stroke_fill='black')

def title():
    im=Image.new('RGBA',(W,H),(0,0,0,0))
    centered(im,'엄마, 오늘 아빠한테',210,88,'white')
    centered(im,'말 걸어도 돼?',325,100,'#FF982F')
    im.save(ROOT/'graphics/title.png')
    return im

def wrap(text,maxwidth=940,size=68):
    d=ImageDraw.Draw(Image.new('RGB',(1,1))); f=font(size)
    if text=='“엄마, 오늘 아빠한테 말 걸어도 돼?”':
        return ['“엄마, 오늘 아빠한테','말 걸어도 돼?”']
    if d.textlength(text,font=f)<=maxwidth: return [text]
    words=text.split()
    choices=[]
    for j in range(1,len(words)):
        left,right=' '.join(words[:j]),' '.join(words[j:])
        lw,rw=d.textlength(left,font=f),d.textlength(right,font=f)
        if max(lw,rw)<=maxwidth:
            choices.append((abs(lw-rw),[left,right]))
    if choices: return min(choices,key=lambda x:x[0])[1]
    rows=[]; current=''
    for word in text.split():
        trial=(current+' '+word).strip()
        if d.textlength(trial,font=f)>maxwidth and current:
            rows.append(current); current=word
        else: current=trial
    if current: rows.append(current)
    return rows

def plate(text,dialogue=False):
    im=Image.new('RGBA',(W,H),(0,0,0,0))
    rows=wrap(text)
    if len(rows)>2: raise ValueError(f'More than two caption lines: {text}')
    for i,row in enumerate(rows):
        centered(im,row,1470+(i-(len(rows)-1)/2)*84,68,
                 '#FFE35C' if dialogue else '#FFFFFF',7)
    return im

def norm(text):
    return re.sub(r'[^가-힣A-Za-z0-9]','',text.replace('10','십'))

def chunks(text):
    # Split long sentences at word boundaries; keep every spoken word.
    sentences=re.split(r'(?<=[.!?])\s+',text)
    if len(sentences)>1:
        return [piece for sentence in sentences for piece in chunks(sentence)]
    if text.startswith('다만 쉴 시간이'):
        return ['다만 쉴 시간이 필요하다는 말을,','딸을 밀어내는 말 대신 전한 겁니다.']
    if text.startswith('지금 상태를 말하고'):
        return ['지금 상태를 말하고,','쉼을 구하고,','상처 준 말은 사과하는 일입니다.']
    if text.startswith('회사에서 하루 종일'):
        return ['회사에서 하루 종일 시달린 아버지는','목소리가 날카로워진 줄도 몰랐습니다.']
    if text.startswith('딸은 보여줄 것이'):
        return ['딸은 보여줄 것이 생겨도','아버지의 기분부터 확인하고 있었습니다.']
    if text.startswith('하지만 설명하지 않은'):
        return ['하지만 설명하지 않은 피로는','상대에게 거절로 전해지기도 합니다.']
    parts=[]; current=''
    for word in text.split():
        trial=(current+' '+word).strip()
        if len(wrap(trial))>2 and current:
            parts.append(current); current=word
        else: current=trial
    if current: parts.append(current)
    return parts

def preview():
    overlay=title(); samples=[]
    for name,txt,dia in [('01-offer','“아빠, 내가 그린 만화야.”',True),
                         ('03-question','“엄마, 오늘 아빠한테 말 걸어도 돼?”',True),
                         ('05-together','편하게 말을 걸어도 된다는 믿음은 관계에 남습니다.',False)]:
        canvas=Image.new('RGBA',(W,H),'black')
        art=Image.open(ROOT/'images'/f'{name}.png').convert('RGBA').resize((W,W),Image.Resampling.LANCZOS)
        canvas.alpha_composite(art,(0,ART_Y)); canvas.alpha_composite(overlay)
        # The third preview uses its last clause so the final sentence spans cues.
        txt=chunks(txt)[-1] if len(wrap(txt))>2 else txt
        canvas.alpha_composite(plate(txt,dia))
        canvas.convert('RGB').save(EDIT/f'layout-{name}.jpg',quality=94)
        samples.append(canvas.convert('RGB').resize((324,576)))
    sheet=Image.new('RGB',(972,576),'black')
    for i,im in enumerate(samples): sheet.paste(im,(i*324,0))
    sheet.save(EDIT/'layout-preview.jpg',quality=94)

def timing():
    src=json.loads((ROOT/'audio/narration-alignment.json').read_text(encoding='utf-8'))
    heard=''; clocks=[]
    for seg in src:
        for word in seg['words']:
            s=norm(word['word'])
            for j,c in enumerate(s):
                heard+=c
                clocks.append((word['start']+(word['end']-word['start'])*j/len(s),
                               word['start']+(word['end']-word['start'])*(j+1)/len(s)))
    exact=''.join(norm(s) for s in LINES)
    matcher=difflib.SequenceMatcher(None,exact,heard,autojunk=False)
    if matcher.ratio()<0.96:
        raise ValueError(f'ASR/script mismatch needs review: {matcher.ratio():.3f}')
    mapping={a+j:b+j for a,b,n in matcher.get_matching_blocks() for j in range(n)}
    cues=[]; offset=0
    for lineid,line in enumerate(LINES):
        for text in chunks(line):
            n=len(norm(text)); hits=[mapping[x] for x in range(offset,offset+n) if x in mapping]
            if lineid==1:
                # Raw small-ASR confuses '그린 만화야' with similar syllables.
                # A separate web audio transcription confirmed the intended words.
                cues.append({'start':4.86,'end':7.38,'text':text,
                             'dialogue':True,'art':ARTS[lineid],'line':lineid})
                offset+=n
                continue
            if text=='쉼을 구하고,':
                # '휨을' in raw small-ASR was also checked by web audio transcription.
                cues.append({'start':98.46,'end':100.0,'text':text,
                             'dialogue':False,'art':ARTS[lineid],'line':lineid})
                offset+=n
                continue
            if len(hits)<n*0.85: raise ValueError(f'Uncertain cue: {text}')
            cues.append({'start':clocks[min(hits)][0],'end':clocks[max(hits)][1],
                         'text':text,'dialogue':line.startswith('“'),'art':ARTS[lineid], 'line':lineid})
            offset+=n
    assert ''.join(norm(c['text']) for c in cues)==exact
    (EDIT/'timed-cues.json').write_text(json.dumps(cues,ensure_ascii=False,indent=2),encoding='utf-8')
    return cues

def run(args):
    subprocess.run(['ffmpeg','-y','-hide_banner','-loglevel','error',*args],check=True,cwd=ROOT)

def render():
    audio=ROOT/'audio/narration-charon.wav'
    if not audio.exists(): raise FileNotFoundError('Validated web narration not downloaded; do not render a final with silence.')
    cues=timing()
    info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-of','json',str(audio)]))
    duration=math.ceil((float(info['format']['duration'])+0.75)*FPS)/FPS
    title(); paths=[]
    # A forward/reverse cycle avoids a jump when a quiet shot lasts over 6 sec.
    for art in set(ARTS):
        clip=ROOT/'clips'/f'{art}.mp4'
        if not clip.exists(): raise FileNotFoundError(f'Missing reviewed motion: {clip}')
        cycle=EDIT/f'{art}-cycle.mp4'
        if not cycle.exists():
            run(['-i',str(clip),'-filter_complex',
                 '[0:v]split[a][b];[a]setpts=PTS-STARTPTS[f];[b]reverse,setpts=PTS-STARTPTS[r];[f][r]concat=n=2:v=1:a=0[v]',
                 '-map','[v]','-an','-c:v','libx264','-crf','18','-preset','fast',str(cycle)])
    art_start=0; previous_art=None
    for i,c in enumerate(cues):
        a=0 if i==0 else round((cues[i-1]['end']+c['start'])/2*FPS)/FPS
        b=duration if i==len(cues)-1 else round((c['end']+cues[i+1]['start'])/2*FPS)/FPS
        c['display_start'],c['display_end']=a,b
        n=round((b-a)*FPS)
        if n<=0: raise ValueError('Invalid cue timing')
        if c['art']!=previous_art: art_start=a; previous_art=c['art']
        clip=EDIT/f"{c['art']}-cycle.mp4"
        overlay=Image.open(ROOT/'graphics/title.png').convert('RGBA')
        overlay.alpha_composite(plate(c['text'],c['dialogue']))
        png=EDIT/f'overlay-{i:02}.png'; overlay.save(png)
        out=EDIT/f'cue-{i:02}.mp4'
        # The generated clips are portrait with a centered square illustration.
        # Source crop is confirmed against the downloaded clip before final use.
        vf='crop=iw:iw:0:(ih-iw)/2,scale=1080:1080:flags=lanczos,setsar=1'
        vf+=f',pad=1080:1920:0:{ART_Y}:color=black[art];[art][1:v]overlay=0:0[v]'
        run(['-stream_loop','-1','-ss',str(a-art_start),'-i',str(clip),'-i',str(png),'-filter_complex',vf,
             '-map','[v]','-frames:v',str(n),'-an','-c:v','libx264','-crf','18',
             '-preset','fast','-pix_fmt','yuv420p',str(out)])
        paths.append(out); print(f'{i+1}/{len(cues)} {a:.2f}-{b:.2f} {c["text"]}',flush=True)
    listing=EDIT/'concat.txt'
    listing.write_text('\n'.join("file '"+p.as_posix()+"'" for p in paths),encoding='utf-8')
    run(['-f','concat','-safe','0','-i',str(listing),'-i',str(audio),
         '-map','0:v','-map','1:a','-c:v','copy','-af','loudnorm=I=-16:TP=-1.5:LRA=7,apad',
         '-t',str(duration),'-c:a','aac','-b:a','192k','-movflags','+faststart','final-v3.mp4'])
    (EDIT/'duration.json').write_text(json.dumps({'seconds':duration,'fps':FPS}),encoding='utf-8')
    (EDIT/'timed-cues.json').write_text(json.dumps(cues,ensure_ascii=False,indent=2),encoding='utf-8')
    def srt_time(t):
        ms=round(t*1000)
        return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'
    (ROOT/'captions-v3.srt').write_text('\n\n'.join(
        f'{i+1}\n{srt_time(c["display_start"])} --> {srt_time(c["display_end"])}\n'+
        '\n'.join(wrap(c['text'])) for i,c in enumerate(cues)),encoding='utf-8-sig')

if __name__=='__main__':
    preview()
    if '--preview' not in sys.argv: render()
