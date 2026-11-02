"""One-film pacing and semantic-caption revision. Preserve the delivered v3."""
from pathlib import Path
import json, math, re, subprocess, sys, wave
import numpy as np
from PIL import Image, ImageDraw
import render_v3 as base

ROOT = base.ROOT
OLD_EDIT = ROOT / 'edit'
EDIT = ROOT / 'edit-v4'
EDIT.mkdir(exist_ok=True)
SPEED = 1.20

# Each tuple is one screen. Newlines are editorial meaning boundaries,
# independent of punctuation and automatic width balancing.
SCREENS = [
    ('야근하고 돌아온 아버지에게\n딸이 공책을 내밀었습니다.',),
    ('“아빠,\n내가 그린 만화야.”',),
    ('“아빠 피곤한 거\n안 보여?”',),
    ('회사에서 하루 종일\n시달린 아버지는', '목소리가 날카로워진 줄도\n몰랐습니다.'),
    ('딸은 공책을 덮었습니다.',),
    ('며칠째 저녁이면\n비슷한 일이 이어졌습니다.',),
    ('어느 날, 아버지는', '딸이 엄마에게\n묻는 말을 들었습니다.'),
    ('“엄마, 오늘 아빠한테\n말 걸어도 돼?”',),
    ('딸은 보여줄 것이 생겨도', '아버지의 기분부터\n확인하고 있었습니다.'),
    ('아버지는\n딸 앞에 앉았습니다.',),
    ('“아빠가 요즘\n말 심하게 했지.', '네가 잘못한 건 없어.\n미안해.”'),
    ('그러고는\n자기 상태도 말했습니다.',),
    ('“오늘 좀 지쳤어.\n십 분만 쉬고 같이 보자.”',),
    ('십 분 뒤, 아버지가 먼저\n딸의 공책을 펼쳤습니다.',),
    ('“이 다음엔\n어떻게 돼?”',),
    ('아버지의 피로가\n사라진 건 아니었습니다.',),
    ('다만 쉴 시간이 필요하다는 말을,', '딸을 밀어내는 말 대신\n전한 겁니다.'),
    ('우리는 가까운 사람이라면', '내 사정을\n알아줄 거라 기대합니다.'),
    ('하지만 설명하지 않은 피로는', '상대에게 거절로\n전해지기도 합니다.'),
    ('감정을 책임진다는 건\n늘 웃으며 참는 일이 아닙니다.',),
    ('지금 상태를 말하고,\n쉼을 구하고,', '상처 준 말은\n사과하는 일입니다.'),
    ('오늘의 기분은 지나가도,',),
    ('편하게 말을 걸어도 된다는\n믿음은 관계에 남습니다.',),
]
ROW_MAP = {}
PARTS = {}
for original, screens in zip(base.LINES, SCREENS):
    assert base.norm(' '.join(screens)) == base.norm(original), original
    PARTS[original] = []
    for screen in screens:
        text = screen.replace('\n', ' ')
        PARTS[original].append(text)
        ROW_MAP[text] = screen.splitlines()

def wrap(text, maxwidth=940, size=68):
    rows = ROW_MAP[text]
    d = ImageDraw.Draw(Image.new('RGB', (1, 1)))
    widths = [d.textlength(s, font=base.font(size)) for s in rows]
    if len(rows) > 2 or max(widths) > maxwidth:
        raise ValueError(f'Caption layout needs editorial repair: {rows} {widths}')
    return rows

base.EDIT = EDIT
base.wrap = wrap
base.chunks = lambda text: PARTS[text]

def audio_edit():
    log = (OLD_EDIT / 'silence-v3.log').read_text(encoding='utf-8')
    detected = [(float(a), float(b)) for a, b in re.findall(
        r'silence_start: ([\d.]+).*?silence_end: ([\d.]+)', log, re.S)]
    # Only remove the middle of measured <-40 dB silence, never voiced audio.
    # Keep 120 ms on either side. The resulting gap is 200 ms at 1.2x.
    cuts = [(a + .12, b - .12) for a, b in detected if b-a > .4 and a > 0]
    cuts.insert(0, (0, detected[0][1] - .08))
    with wave.open(str(ROOT/'audio/narration-charon.wav'), 'rb') as f:
        params = f.getparams(); sr = f.getframerate()
        assert f.getnchannels() == 1 and f.getsampwidth() == 2
        samples = np.frombuffer(f.readframes(f.getnframes()), dtype='<i2').copy()
    cuts = [(round(a*sr), round(b*sr)) for a,b in cuts]
    kept = []; cursor = 0
    for a,b in cuts:
        assert a >= cursor and b > a
        block = samples[cursor:a].copy()
        # 3 ms fades lie wholly inside the detected silence, avoiding join clicks.
        n = min(round(.003*sr), len(block))
        if n:
            if cursor: block[:n] = (block[:n]*np.linspace(0,1,n)).astype('<i2')
            block[-n:] = (block[-n:]*np.linspace(1,0,n)).astype('<i2')
        kept.append(block); cursor = b
    kept.append(samples[cursor:])
    pcm = np.concatenate(kept)
    with wave.open(str(EDIT/'silence-tightened.wav'), 'wb') as f:
        f.setparams(params); f.writeframes(pcm.tobytes())
    base.run(['-i',str(EDIT/'silence-tightened.wav'),'-af',f'atempo={SPEED}',
              '-c:a','pcm_s16le',str(ROOT/'audio/narration-charon-v4.wav')])
    seconds = [(a/sr,b/sr) for a,b in cuts]
    def retime(t):
        return (t-sum(max(0,min(t,b)-a) for a,b in seconds if t>a))/SPEED
    metadata = {'speed':SPEED,'silence_threshold_db':-40,'retained_gap_before_speed':.24,
                'cuts_seconds':seconds,'source_seconds':len(samples)/sr,
                'removed_seconds':sum(b-a for a,b in seconds)}
    (EDIT/'audio-edit-map.json').write_text(json.dumps(metadata,indent=2),encoding='utf-8')
    return retime

def prepare():
    for text in ROW_MAP: wrap(text)
    retime = audio_edit()
    cues = base.timing()
    for c in cues:
        c['source_start'],c['source_end'] = c['start'],c['end']
        c['start'],c['end'] = retime(c['start']),retime(c['end'])
        c['rows'] = wrap(c['text'])
    audio = ROOT/'audio/narration-charon-v4.wav'
    info = json.loads(subprocess.check_output(['ffprobe','-v','error','-show_format','-of','json',str(audio)]))
    duration = math.ceil((float(info['format']['duration'])+.3)*base.FPS)/base.FPS
    for i,c in enumerate(cues):
        c['display_start'] = 0 if i==0 else round((cues[i-1]['end']+c['start'])/2*base.FPS)/base.FPS
        c['display_end'] = duration if i==len(cues)-1 else round((c['end']+cues[i+1]['start'])/2*base.FPS)/base.FPS
        assert c['display_end'] > c['display_start']
    (EDIT/'timed-cues.json').write_text(json.dumps(cues,ensure_ascii=False,indent=2),encoding='utf-8')
    (EDIT/'duration.json').write_text(json.dumps({'seconds':duration,'fps':base.FPS}),encoding='utf-8')
    return cues, audio, duration

def render(cues,audio,duration):
    paths=[]; art_start=0; previous_art=None
    for i,c in enumerate(cues):
        a,b=c['display_start'],c['display_end']
        if c['art']!=previous_art: art_start=a;previous_art=c['art']
        cycle=OLD_EDIT/f"{c['art']}-cycle.mp4"
        assert cycle.is_file()
        overlay=Image.open(ROOT/'graphics/title.png').convert('RGBA')
        overlay.alpha_composite(base.plate(c['text'],c['dialogue']))
        png=EDIT/f'overlay-{i:02}.png'; overlay.save(png)
        out=EDIT/f'cue-{i:02}.mp4'
        vf=f'crop=iw:iw:0:(ih-iw)/2,scale=1080:1080:flags=lanczos,setsar=1,pad=1080:1920:0:{base.ART_Y}:color=black[art];[art][1:v]overlay=0:0[v]'
        base.run(['-stream_loop','-1','-ss',str(a-art_start),'-i',str(cycle),'-i',str(png),
                  '-filter_complex',vf,'-map','[v]','-frames:v',str(round((b-a)*base.FPS)),
                  '-an','-c:v','libx264','-crf','18','-preset','fast','-pix_fmt','yuv420p',str(out)])
        paths.append(out); print(f'{i+1}/{len(cues)} {a:.2f}-{b:.2f} {c["text"]}',flush=True)
    listing=EDIT/'concat.txt'
    listing.write_text('\n'.join("file '"+p.as_posix()+"'" for p in paths),encoding='utf-8')
    base.run(['-f','concat','-safe','0','-i',str(listing),'-i',str(audio),'-map','0:v','-map','1:a',
              '-c:v','copy','-af','loudnorm=I=-16:TP=-1.5:LRA=7,apad','-t',str(duration),
              '-c:a','aac','-b:a','192k','-movflags','+faststart',str(ROOT/'final-v4.mp4')])
    def stamp(t):
        ms=round(t*1000)
        return f'{ms//3600000:02}:{ms//60000%60:02}:{ms//1000%60:02},{ms%1000:03}'
    (ROOT/'captions-v4.srt').write_text('\n\n'.join(
        f'{i+1}\n{stamp(c["display_start"])} --> {stamp(c["display_end"])}\n'+'\n'.join(c['rows'])
        for i,c in enumerate(cues)),encoding='utf-8-sig')

if __name__=='__main__':
    prepared=prepare()
    print(f'{len(prepared[0])} screens; {prepared[2]:.3f} seconds',flush=True)
    if '--prepare' not in sys.argv: render(*prepared)
