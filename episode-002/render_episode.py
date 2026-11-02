"""Bounded edit for episode 002 using preserved web media and manual caption breaks."""
from pathlib import Path
import difflib,json,math,re,subprocess,sys,wave
import numpy as np
from PIL import Image,ImageDraw
import prepare_graphics as gfx

ROOT=Path(__file__).resolve().parent
EDIT=ROOT/'edit';FPS=60
def run(args):
    subprocess.run(['ffmpeg','-y','-hide_banner','-loglevel','error',*map(str,args)],check=True)
def norm(t):return re.sub('[^가-힣A-Za-z0-9]','',t)
def dump(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')

def prepare_audio():
    source=ROOT/'audio/narration-raw.wav'
    assert source.is_file(),'Web narration is required; never render a silent final.'
    log=(EDIT/'silence.log').read_text(encoding='utf-16' if (EDIT/'silence.log').read_bytes()[:2]==b'\xff\xfe' else 'utf-8')
    spans=[(float(a),float(b)) for a,b in re.findall(r'silence_start: ([\d.]+).*?silence_end: ([\d.]+)',log,re.S)]
    with wave.open(str(source),'rb') as f:
        params=f.getparams();sr=f.getframerate();assert f.getnchannels()==1 and f.getsampwidth()==2
        samples=np.frombuffer(f.readframes(f.getnframes()),dtype='<i2').copy()
    cuts=[(a+.12,b-.12) for a,b in spans if b-a>.4]
    cuts=[(round(a*sr),round(b*sr)) for a,b in cuts]
    blocks=[];cursor=0
    for a,b in cuts:
        assert a>=cursor and b>a
        block=samples[cursor:a].copy();n=min(round(.003*sr),len(block))
        if n:
            if cursor:block[:n]=(block[:n]*np.linspace(0,1,n)).astype('<i2')
            block[-n:]=(block[-n:]*np.linspace(1,0,n)).astype('<i2')
        blocks.append(block);cursor=b
    blocks.append(samples[cursor:]);pcm=np.concatenate(blocks)
    with wave.open(str(EDIT/'tightened.wav'),'wb') as f:f.setparams(params);f.writeframes(pcm.tobytes())
    speed=max(1.,len(pcm)/sr/63.5)
    audio=ROOT/'audio/narration-edited.wav'
    run(['-i',EDIT/'tightened.wav','-af',f'atempo={speed:.8f}','-c:a','pcm_s16le',audio])
    cuts=[(a/sr,b/sr) for a,b in cuts]
    def retime(t):return (t-sum(max(0,min(t,b)-a) for a,b in cuts if t>a))/speed
    dump(EDIT/'audio-edit-map.json',{'source_seconds':len(samples)/sr,'removed_silence_seconds':sum(b-a for a,b in cuts),'speed':speed,'cuts':cuts,'retained_gap':.24/speed})
    return audio,retime

def timing(retime,audio):
    alignment=json.loads((ROOT/'audio/narration-raw-alignment.json').read_text(encoding='utf-8'))
    heard='';clocks=[]
    for seg in alignment:
        for w in seg['words']:
            word=norm(w['word'])
            for i,c in enumerate(word):
                heard+=c;clocks.append((w['start']+(w['end']-w['start'])*i/len(word),w['start']+(w['end']-w['start'])*(i+1)/len(word)))
    plan=json.loads((ROOT/'caption-plan.json').read_text(encoding='utf-8'))
    lines=(ROOT/'audio/narration.txt').read_text(encoding='utf-8').splitlines()
    exact=''.join(norm(x) for x in lines)
    match=difflib.SequenceMatcher(None,exact,heard,autojunk=False)
    differences=[{'script':exact[a:b],'asr':heard[c:d]} for tag,a,b,c,d in match.get_opcodes() if tag!='equal']
    dump(EDIT/'transcript-check.json',{'ratio':match.ratio(),'differences':differences,'note':'Small ASR phonetic differences are retained for review, not silently rewritten.'})
    assert match.ratio()>.96,(match.ratio(),differences)
    mapping={a+i:b+i for a,b,n in match.get_matching_blocks() for i in range(n)}
    cues=[];offset=0
    for e,line in zip(plan,lines):
        for rows,shot in zip(e['screens'],e['shots']):
            text=' '.join(rows);n=len(norm(text));hits=[mapping[x] for x in range(offset,offset+n) if x in mapping]
            assert len(hits)>=n*.85,(text,hits)
            cues.append({'rows':rows,'shot':shot,'line':e['line'],'dialogue':line.startswith('“'),'source_start':clocks[min(hits)][0],'source_end':clocks[max(hits)][1]})
            offset+=n
    assert offset==len(exact)
    with wave.open(str(audio),'rb') as f:duration=math.ceil((f.getnframes()/f.getframerate()+.25)*FPS)/FPS
    for i,c in enumerate(cues):c['start']=retime(c['source_start']);c['end']=retime(c['source_end'])
    for i,c in enumerate(cues):
        c['display_start']=0 if not i else round((cues[i-1]['end']+c['start'])/2*FPS)/FPS
        c['display_end']=duration if i==len(cues)-1 else round((c['end']+cues[i+1]['start'])/2*FPS)/FPS
        assert c['display_end']>c['display_start']
    dump(EDIT/'timed-cues.json',cues);dump(EDIT/'duration.json',{'seconds':duration,'fps':FPS})
    return cues,duration

MASTERS={
 '01':('01-plans-letterboxed.mp4','720:720:0:280'),
 '03':('03-conversation-letterboxed.mp4','720:720:0:280'),
 '04':('04-timber-portrait.mp4','640:640:40:350'),
 '05':('05-ready-letterboxed.mp4','720:720:0:280'),
 '06':('06-planing-portrait.mp4','720:720:0:240'),
 '07':('07-adjust-portrait.mp4','640:640:40:380'),
 '08':('08-first-chair-letterboxed.mp4','720:720:0:280'),
}
def masters():
    for key,(file,crop) in MASTERS.items():
        out=EDIT/f'motion-{key}.mp4'
        if out.exists():continue
        vf=f'crop={crop},setpts=1.35*(PTS-STARTPTS),tpad=stop_mode=clone:stop_duration=0.2,minterpolate=fps=60:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:me=epzs:vsbmc=1:search_param=16,scale=1080:1080:flags=lanczos,setsar=1'
        run(['-i',ROOT/'clips/raw-downloads'/file,'-vf',vf,'-an','-t','8','-c:v','libx264','-crf','18','-preset','fast','-pix_fmt','yuv420p',out])
        print('Motion',key,flush=True)

def paper_art():
    # Exact Korean world text is editorially composited, never generated lettering.
    im=Image.open(ROOT/'images/01-plans.png').convert('RGB').resize((1080,1080),Image.Resampling.LANCZOS)
    d=ImageDraw.Draw(im);f=gfx.font(17)
    for j,s in enumerate(['동네에서 가장','멋진 의자를','만들자']):
        d.text((390-d.textlength(s,font=f)/2,130+j*24),s,font=f,fill='#654b32')
    im.save(EDIT/'goal-paper.png')
    removal=Image.open(ROOT/'images/09-removal.png').convert('RGBA')
    lettering=Image.new('RGBA',(180,105));ld=ImageDraw.Draw(lettering);lf=gfx.font(18)
    for j,s in enumerate(['동네에서 가장','멋진 의자를','만들자']):
        ld.text(((180-ld.textlength(s,font=lf))/2,j*27),s,font=lf,fill='#654b32')
    lettering=lettering.rotate(-12,resample=Image.Resampling.BICUBIC,expand=True)
    removal.alpha_composite(lettering,(490-lettering.width//2,280-lettering.height//2))
    removal.convert('RGB').save(EDIT/'removal-paper.png')

# Normalized crop boxes in the square motion master (left, top, fraction).
CROPS={
 '01-face':(.54,.02,.46),'01-poster':(.18,.015,.46),
 '02-timber-detail':(.06,.1,.68),'03-mentor':(.00,.05,.62),'03-novice':(.39,.025,.59),
 '04-timber-detail':(.08,.18,.76),'05-timber-detail':(.05,.36,.63),
 '06-hand-detail':(.14,.10,.77),'07-join-detail':(.06,.10,.83),
 '08-chair-detail':(.40,.43,.50),'08-face':(.48,.03,.48),
}

def render(cues,audio,duration):
    paths=[];source_positions={};paper_art()
    shotplan=[]
    for i,c in enumerate(cues):
        shot=c['shot'];key=shot[:2];a,b=c['display_start'],c['display_end'];frames=round((b-a)*FPS)
        static=key in ['02','09'] or shot=='01-poster'
        if shot=='01-poster':source=EDIT/'goal-paper.png'
        elif static:source=ROOT/'images/02-tools.png' if key=='02' else EDIT/'removal-paper.png'
        else:source=EDIT/f'motion-{key}.mp4'
        left,top,size=CROPS.get(shot,(0,0,1))
        # Slight zoom on first character reaction; supersample art before subpixel crop.
        zoom=shot=='01-face' and c['line']==0
        if zoom:
            spatial=("scale=3240:3240:flags=lanczos,zoompan=z='1.65+0.60*min(on/"+str(frames-1)+",1)':"
                     "x='max(0,min(iw-iw/zoom,2440-iw/zoom/2))':y='max(0,min(ih-ih/zoom,840-ih/zoom/2))':d=1:s=1080x1080:fps=60")
        else:
            s=round(1080*size)//2*2;x=min(round(left*1080)//2*2,1080-s);y=min(round(top*1080)//2*2,1080-s)
            spatial=f'scale=1080:1080:flags=lanczos,crop={s}:{s}:{x}:{y},scale=1080:1080:flags=lanczos'
        overlay=EDIT/f'overlay-{i:02}.png'
        start=source_positions.get(key,0)
        if key=='05':start=max(3.,start) # Exclude the transient dark wipe in the first two seconds.
        if start+(b-a)>7.9:start=3. if key=='05' else 0
        source_positions[key]=start+(b-a)
        inp=['-loop','1','-framerate','60','-i',source] if static else ['-ss',f'{start:.6f}','-i',source]
        out=EDIT/f'cue-{i:02}.mp4'
        vf=f'[0:v]setpts=PTS-STARTPTS,{spatial},pad=1080:1920:0:490:color=black[art];[art][1:v]overlay=0:0[v]'
        if not out.exists():run([*inp,'-i',overlay,'-filter_complex',vf,'-map','[v]','-frames:v',frames,'-r','60','-an','-c:v','libx264','-crf','18','-preset','fast','-pix_fmt','yuv420p',out])
        paths.append(out);shotplan.append({'cue':i,'shot':shot,'source':str(source),'start':start,'crop':[left,top,size],'zoom':zoom,'seconds':[a,b]})
        print(f'Cue {i+1}/{len(cues)} {shot} {b-a:.2f}s',flush=True)
    dump(EDIT/'shot-plan.json',shotplan)
    listing=EDIT/'concat.txt';listing.write_text('\n'.join("file '"+p.as_posix()+"'" for p in paths),encoding='utf-8')
    run(['-f','concat','-safe','0','-i',listing,'-i',audio,'-map','0:v','-map','1:a','-c:v','copy','-af','loudnorm=I=-16:TP=-1.5:LRA=7,apad','-t',duration,'-c:a','aac','-b:a','192k','-movflags','+faststart',ROOT/'final.mp4'])
    def stamp(t):
        ms=round(t*1000);return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'
    (ROOT/'captions.srt').write_text('\n\n'.join(f'{i+1}\n{stamp(c["display_start"])} --> {stamp(c["display_end"])}\n'+ '\n'.join(c['rows']) for i,c in enumerate(cues)),encoding='utf-8-sig')

if __name__=='__main__':
    gfx.prepare();audio,retime=prepare_audio();cues,duration=timing(retime,audio)
    print(f'{len(cues)} screens; {duration:.3f} seconds',flush=True)
    if '--prepare' not in sys.argv:masters();render(cues,audio,duration)
