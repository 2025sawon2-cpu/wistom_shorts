"""Add one push-in and two close-up inserts from the reviewed 60 fps motion."""
import json
from PIL import Image
import render_v3 as base
import render_v5 as v5

ROOT=base.ROOT
EDIT=ROOT/'edit-v7'
EDIT.mkdir(exist_ok=True)
FPS=60

def render():
    cues=json.loads((ROOT/'edit-v6/timed-cues.json').read_text(encoding='utf-8'))
    specs=[
        {'name':'girl-reaction-zoom','cues':[10,11],'art':'02-withdraw','source_offset':0,
         'framing':'progressive zoom 1.08 to 1.48, center 420,340 in the 720px source'},
        {'name':'father-apology-closeup','cues':[13,14],'art':'04-apology',
         'source_offset':cues[13]['display_start']-cues[12]['display_start'],
         'framing':'crop 420x420 at 0,70, father face and upper body'},
        {'name':'notebook-hands-closeup','cues':[17],'art':'05-together','source_offset':0,
         'framing':'crop 450x450 at 135,270, notebook and pointing hand'},
    ]
    by_cue={}
    for s in specs:
        s['start']=cues[s['cues'][0]]['display_start']
        s['end']=cues[s['cues'][-1]]['display_end']
        count=round((s['end']-s['start'])*FPS)
        if s['name']=='girl-reaction-zoom':
            # Oversample the spatial crop so a slow push-in does not step by
            # whole pixels in the original 720px picture. The motion stays 60fps.
            vf="scale=2160:2160:flags=lanczos,zoompan=z='1.08+0.40*min(on/"+str(count-1)+",1)':"
            vf+="x='max(0,min(iw-iw/zoom,1260-iw/zoom/2))':y='max(0,min(ih-ih/zoom,1020-ih/zoom/2))':d=1:s=1080x1080:fps=60"
        elif s['name']=='father-apology-closeup':
            vf='crop=420:420:0:70,scale=1080:1080:flags=lanczos,setsar=1'
        else:
            vf='crop=450:450:135:270,scale=1080:1080:flags=lanczos,setsar=1'
        out=EDIT/(s['name']+'.mp4')
        base.run(['-stream_loop','-1','-ss',str(s['source_offset']),'-i',
                  str(ROOT/'edit-v6'/f'{s["art"]}-60fps.mp4'),'-vf',vf,'-frames:v',str(count),
                  '-an','-c:v','libx264','-crf','18','-preset','fast','-pix_fmt','yuv420p',str(out)])
        for i in s['cues']:by_cue[i]=s
        print(f'{s["name"]}: {s["start"]:.3f}-{s["end"]:.3f}',flush=True)
    paths=[]
    for i,c in enumerate(cues):
        if i not in by_cue:
            paths.append(ROOT/'edit-v6'/f'cue-{i:02}.mp4');continue
        s=by_cue[i]
        overlay=Image.open(ROOT/'graphics/title.png').convert('RGBA')
        if c['dialogue']:caption=v5.plate(c['rows'])
        else:
            caption=Image.new('RGBA',(1080,1920),(0,0,0,0))
            for j,row in enumerate(c['rows']):
                base.centered(caption,row,1470+(j-(len(c['rows'])-1)/2)*84,68,'#FFFFFF',7)
        overlay.alpha_composite(caption)
        png=EDIT/f'overlay-{i:02}.png';overlay.save(png)
        output=EDIT/f'cue-{i:02}.mp4'
        vf=f'pad=1080:1920:0:{base.ART_Y}:color=black[art];[art][1:v]overlay=0:0[v]'
        base.run(['-ss',str(c['display_start']-s['start']),'-i',str(EDIT/(s['name']+'.mp4')),
                  '-i',str(png),'-filter_complex',vf,'-map','[v]',
                  '-frames:v',str(round((c['display_end']-c['display_start'])*FPS)),
                  '-an','-c:v','libx264','-crf','18','-preset','fast','-pix_fmt','yuv420p',str(output)])
        paths.append(output);c['shot']=s['name']
    listing=EDIT/'concat.txt'
    listing.write_text('\n'.join("file '"+p.as_posix()+"'" for p in paths),encoding='utf-8')
    base.run(['-f','concat','-safe','0','-i',str(listing),'-i',str(ROOT/'final-v6.mp4'),
              '-map','0:v','-map','1:a','-c','copy','-movflags','+faststart',str(ROOT/'final-v7.mp4')])
    (EDIT/'shot-plan.json').write_text(json.dumps(specs,ensure_ascii=False,indent=2),encoding='utf-8')
    (EDIT/'timed-cues.json').write_text(json.dumps(cues,ensure_ascii=False,indent=2),encoding='utf-8')
    (ROOT/'captions-v7.srt').write_bytes((ROOT/'captions-v6.srt').read_bytes())

if __name__=='__main__':render()
