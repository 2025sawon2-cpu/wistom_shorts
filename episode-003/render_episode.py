"""Episode 003 edit, reusing the preceding episode's verified local workflow."""
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
    speed=1.0  # Keep this narrator's natural speech pace; remove only long gaps.
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
 '01':('01-delay.mp4','720:720:0:280'),
 '02':('02-promise.mp4','720:720:0:280'),
 '03':('03-interview.mp4','720:720:0:280'),
 '04':('04-hesitation.mp4','720:720:0:280'),
 '05':('05-door.mp4','720:720:0:280'),
 '06':('06-sewing.mp4','720:720:0:280'),
 '07':('07-handover.mp4','720:720:0:280'),
 '08':('08-inspect.mp4','720:720:0:280'),
 '09':('09-schedule.mp4','544:544:130:340'),
}
def masters():
    for key,(file,crop) in MASTERS.items():
        out=EDIT/f'motion-{key}.mp4'
        if out.exists():continue
        length=9.5 if key=='07' else 8
        speed=2.5 if key=='01' else 1.6 if key=='07' else 1.35
        trim='trim=end=2.8,' if key=='01' else ''
        vf=f'{trim}crop={crop},setpts={speed}*(PTS-STARTPTS),tpad=stop_mode=clone:stop_duration=1.2,minterpolate=fps=60:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:me=epzs:vsbmc=1:search_param=16,scale=1080:1080:flags=lanczos,setsar=1'
        run(['-i',ROOT/'clips/raw-downloads'/file,'-vf',vf,'-an','-t',str(length),'-c:v','libx264','-crf','18','-preset','fast','-pix_fmt','yuv420p',out])
        print('Motion',key,flush=True)

# Normalized crop boxes in the square motion master (left, top, fraction).
CROPS={
 '02-face':(.10,.02,.68),
 '01-garments':(.00,.39,.61),'01-customer':(.52,.02,.48),
 '03-customer':(.54,.01,.46),'03-seamstress':(.03,.13,.64),
 '04-ticket':(.35,.35,.65),'04-face':(.10,.02,.66),
 '05-door':(.50,.02,.50),'06-hem':(.21,.30,.70),
 '07-customer':(.54,.02,.46),'07-hands':(.23,.30,.65),'07-seamstress':(.03,.13,.62),
 '08-hem':(.20,.20,.70),'09-hands':(.00,.30,.70),'09-face':(.00,.04,.65),
}

def render(cues,audio,duration):
    paths=[];source_positions={}
    shotplan=[]
    for i,c in enumerate(cues):
        shot=c['shot'];key=shot[:2];a,b=c['display_start'],c['display_end'];frames=round((b-a)*FPS)
        static=False
        source=EDIT/f'motion-{key}.mp4'
        left,top,size=CROPS.get(shot,(0,0,1))
        # Slight zoom on first character reaction; supersample art before subpixel crop.
        zoom=shot=='04' or shot=='09-face'
        if zoom:
            initial,delta,cx,cy=(1.0,.20,1458,1458) if shot=='04' else (1.40,.28,907,1037)
            spatial=(f"scale=3240:3240:flags=lanczos,zoompan=z='{initial}+{delta}*min(on/"+str(frames-1)+",1)':"
                     f"x='max(0,min(iw-iw/zoom,{cx}-iw/zoom/2))':y='max(0,min(ih-ih/zoom,{cy}-ih/zoom/2))':d=1:s=1080x1080:fps=60")
        else:
            s=round(1080*size)//2*2;x=min(round(left*1080)//2*2,1080-s);y=min(round(top*1080)//2*2,1080-s)
            spatial=f'scale=1080:1080:flags=lanczos,crop={s}:{s}:{x}:{y},scale=1080:1080:flags=lanczos'
        overlay=EDIT/f'overlay-{i:02}.png'
        start=source_positions.get(key,0)
        limit=9.4 if key=='07' else 7.9
        if start+(b-a)>limit:start=0
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
