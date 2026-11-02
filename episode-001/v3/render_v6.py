"""Motion-compensated 60 fps art, composited before the crisp text overlays."""
import argparse, json, math
from pathlib import Path
from PIL import Image
import render_v3 as base
import render_v5 as v5

ROOT=base.ROOT
EDIT=ROOT/'edit-v6'
EDIT.mkdir(exist_ok=True)
FPS=60

def smooth(art):
    output=EDIT/f'{art}-60fps.mp4'
    vf='crop=iw:iw:0:(ih-iw)/2,tpad=stop_mode=clone:stop_duration=0.15,'
    vf+='minterpolate=fps=60:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:me=epzs:vsbmc=1:search_param=16'
    # The static rest picture remains static; interpolation cannot add gestures.
    if art=='06-rest':vf='crop=iw:iw:0:(ih-iw)/2,fps=60'
    base.run(['-i',str(ROOT/'edit'/f'{art}-cycle.mp4'),'-vf',vf,'-frames:v','720',
              '-an','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p',str(output)])
    print(f'Smoothed {art}',flush=True)

def render():
    cues=json.loads((ROOT/'edit-v5/timed-cues.json').read_text(encoding='utf-8'))
    old_duration=json.loads((ROOT/'edit-v4/duration.json').read_text(encoding='utf-8'))['seconds']
    duration=math.ceil(old_duration*FPS)/FPS
    paths=[];previous_art=None;art_start=0
    for i,c in enumerate(cues):
        a=round(c['display_start']*FPS)/FPS
        b=duration if i==len(cues)-1 else round(c['display_end']*FPS)/FPS
        c['display_start'],c['display_end']=a,b
        if c['art']!=previous_art:art_start=a;previous_art=c['art']
        cycle=EDIT/f'{c["art"]}-60fps.mp4';assert cycle.is_file(),cycle
        overlay=Image.open(ROOT/'graphics/title.png').convert('RGBA')
        if c['dialogue']:
            caption=v5.plate(c['rows'])
        else:
            caption=Image.new('RGBA',(1080,1920),(0,0,0,0))
            for j,row in enumerate(c['rows']):
                base.centered(caption,row,1470+(j-(len(c['rows'])-1)/2)*84,68,'#FFFFFF',7)
        overlay.alpha_composite(caption)
        png=EDIT/f'overlay-{i:02}.png';overlay.save(png)
        output=EDIT/f'cue-{i:02}.mp4'
        vf=f'scale=1080:1080:flags=lanczos,setsar=1,pad=1080:1920:0:{base.ART_Y}:color=black[art];[art][1:v]overlay=0:0[v]'
        base.run(['-stream_loop','-1','-ss',str(a-art_start),'-i',str(cycle),'-i',str(png),
                  '-filter_complex',vf,'-map','[v]','-frames:v',str(round((b-a)*FPS)),
                  '-an','-c:v','libx264','-preset','fast','-crf','18','-pix_fmt','yuv420p',str(output)])
        paths.append(output);print(f'{i+1}/{len(cues)} {a:.3f}-{b:.3f}',flush=True)
    listing=EDIT/'concat.txt'
    listing.write_text('\n'.join("file '"+p.as_posix()+"'" for p in paths),encoding='utf-8')
    base.run(['-f','concat','-safe','0','-i',str(listing),'-i',str(ROOT/'final-v5.mp4'),
              '-map','0:v','-map','1:a','-c','copy','-t',str(duration),'-movflags','+faststart',str(ROOT/'final-v6.mp4')])
    (EDIT/'timed-cues.json').write_text(json.dumps(cues,ensure_ascii=False,indent=2),encoding='utf-8')
    (EDIT/'duration.json').write_text(json.dumps({'seconds':duration,'fps':FPS}),encoding='utf-8')
    def stamp(t):
        ms=round(t*1000);return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'
    (ROOT/'captions-v6.srt').write_text('\n\n'.join(
        f'{i+1}\n{stamp(c["display_start"])} --> {stamp(c["display_end"])}\n'+'\n'.join(c['rows'])
        for i,c in enumerate(cues)),encoding='utf-8-sig')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--art');args=parser.parse_args()
    if args.art:smooth(args.art)
    else:render()
