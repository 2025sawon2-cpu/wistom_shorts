"""한 편의 쇼츠를 최종 MP4로 만든다 (005편부터 공용).

입력 (episode-XXX/):
  audio/narration-raw.wav   웹 TTS 원본
  audio/narration.txt       대본 (한 줄 = 한 문장 단위)
  caption-plan.json         {"title":[1행,2행], "lines":[{"screens":[[행,행],...], "shots":["01",...]}]}
  clips/NN.mp4              Flow 모션 (720x1280, 가운데 720 정사각 그림이 y=280)
출력:
  final.mp4 (1080x1920, 60fps, H.264/AAC), captions.srt, poster.jpg, edit/* 중간 산출물

사용: .venv/bin/python tools/make_short.py episode-005 [--align-only]
"""
import difflib
import json
import math
import re
import subprocess
import sys
import wave
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from platform_paths import font_path, whisper_dir  # noqa: E402

FPS = 60
ART_Y = 490          # 그림 영역 위치 (1080 정사각)
CLIP_CROP = '720:720:0:280'


def run(args):
    subprocess.run(['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error', *map(str, args)], check=True)


def norm(t):
    return re.sub('[^가-힣A-Za-z0-9]', '', t)


def dump(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8')


# ---------- 글꼴·그래픽 ----------
def font(size, dialogue=False):
    f = ImageFont.truetype(font_path('NotoSerifKR' if dialogue else 'NotoSansKR'), size)
    f.set_variation_by_name('Bold')
    return f


def draw_centered(im, text, cy, size, color, stroke, dialogue=False, max_w=1000):
    d = ImageDraw.Draw(im)
    while True:
        f = font(size, dialogue)
        b = d.textbbox((0, 0), text, font=f, stroke_width=stroke)
        if b[2] - b[0] <= max_w or size <= 40:
            break
        size -= 2
    d.text(((1080 - b[2] - b[0]) / 2, cy - (b[3] + b[1]) / 2), text, font=f, fill=color,
           stroke_width=stroke, stroke_fill='black')
    return size


def title_png(lines, out):
    im = Image.new('RGBA', (1080, 1920), (0, 0, 0, 0))
    size = min(draw_centered(Image.new('RGBA', (1080, 1920)), l, 0, 96, 'white', 0) for l in lines)
    draw_centered(im, lines[0], 230, size, 'white', 0)
    draw_centered(im, lines[1], 345, size, '#FF982F', 0)
    im.save(out)


def caption_png(rows, out):
    dialogue = rows[0].startswith('“')
    if dialogue:
        assert rows[-1].endswith('”'), rows
    im = Image.new('RGBA', (1080, 1920), (0, 0, 0, 0))
    size = 70 if dialogue else 67
    d = ImageDraw.Draw(im)
    while max(d.textlength(r, font=font(size, dialogue)) for r in rows) > 960:
        size -= 2
    for i, row in enumerate(rows):
        cy = 1450 + (i - (len(rows) - 1) / 2) * (size + 16)
        draw_centered(im, row, cy, size, '#FFE35C' if dialogue else 'white', 5 if dialogue else 7, dialogue, 980)
    im.save(out)
    return size


# ---------- 음성 ----------
def align(ep):
    out = ep / 'audio/narration-raw-alignment.json'
    if out.exists():
        return json.loads(out.read_text(encoding='utf-8'))
    from faster_whisper import WhisperModel
    model = WhisperModel('small', device='cpu', compute_type='int8', download_root=whisper_dir(), local_files_only=True)
    src = ep / 'audio/narration-raw.wav'
    with wave.open(str(src), 'rb') as f:
        sr = f.getframerate()
        pcm = np.frombuffer(f.readframes(f.getnframes()), dtype='<i2').astype(np.float32) / 32768
    # 긴 파일 한 번에 전사하면 문장을 통째로 빠뜨리는 일이 있어, 쉼 위치에서 12초 안팎으로 나눠 전사한다.
    log = subprocess.run(['ffmpeg', '-hide_banner', '-i', str(src), '-af', 'silencedetect=n=-40dB:d=0.25', '-f', 'null', '-'],
                         capture_output=True, text=True).stderr
    mids = [(float(a) + float(b)) / 2 for a, b in re.findall(r'silence_start: ([\d.]+).*?silence_end: ([\d.]+)', log, re.S)]
    total = len(pcm) / sr
    bounds, start = [0.0], 0.0
    for m in mids:
        if m - start >= 8:
            bounds.append(m)
            start = m
    bounds.append(total)
    rows = []
    for a, b in zip(bounds, bounds[1:]):
        chunk = pcm[int(a * sr):int(b * sr)]
        if sr != 16000:
            idx = np.linspace(0, len(chunk) - 1, int(len(chunk) * 16000 / sr))
            chunk = np.interp(idx, np.arange(len(chunk)), chunk).astype(np.float32)
        segs, _ = model.transcribe(chunk, language='ko', word_timestamps=True, beam_size=5,
                                   condition_on_previous_text=False)
        for s in segs:
            rows.append({'start': s.start + a, 'end': s.end + a, 'text': s.text,
                         'words': [{'start': w.start + a, 'end': w.end + a, 'word': w.word} for w in s.words]})
    dump(out, rows)
    return rows


def tighten(ep, edit):
    """0.4초 넘는 무음만 0.24초로 줄인다. 말속도는 바꾸지 않는다."""
    src = ep / 'audio/narration-raw.wav'
    log = subprocess.run(['ffmpeg', '-hide_banner', '-i', str(src), '-af', 'silencedetect=n=-40dB:d=0.4', '-f', 'null', '-'],
                         capture_output=True, text=True).stderr
    spans = [(float(a), float(b)) for a, b in re.findall(r'silence_start: ([\d.]+).*?silence_end: ([\d.]+)', log, re.S)]
    with wave.open(str(src), 'rb') as f:
        params, sr = f.getparams(), f.getframerate()
        pcm = np.frombuffer(f.readframes(f.getnframes()), dtype='<i2').copy()
    cuts = [(a + .12, b - .12) for a, b in spans if b - a > .4 and a > 0]
    blocks, cursor = [], 0
    for a, b in cuts:
        a, b = round(a * sr), round(b * sr)
        blk = pcm[cursor:a].copy()
        n = min(round(.003 * sr), len(blk))
        if n:
            blk[-n:] = (blk[-n:] * np.linspace(1, 0, n)).astype('<i2')
        blocks.append(blk)
        cursor = b
    blocks.append(pcm[cursor:])
    out = ep / 'audio/narration-edited.wav'
    with wave.open(str(out), 'wb') as f:
        f.setparams(params)
        f.writeframes(np.concatenate(blocks).tobytes())
    dump(edit / 'audio-edit-map.json', {'source_seconds': len(pcm) / sr, 'removed': sum(b - a for a, b in cuts), 'cuts': cuts})

    def retime(t):
        return t - sum(max(0, min(t, b) - a) for a, b in cuts if t > a)
    with wave.open(str(out), 'rb') as f:
        dur = f.getnframes() / f.getframerate()
    return out, retime, dur


def cue_times(ep, edit, plan, rows, retime, audio_dur):
    heard, clocks = '', []
    for seg in rows:
        for w in seg['words']:
            word = norm(w['word'])
            for i, _ in enumerate(word):
                clocks.append((w['start'] + (w['end'] - w['start']) * i / len(word),
                               w['start'] + (w['end'] - w['start']) * (i + 1) / len(word)))
            heard += word
    lines = (ep / 'audio/narration.txt').read_text(encoding='utf-8').strip().splitlines()
    exact = ''.join(norm(x) for x in lines)
    m = difflib.SequenceMatcher(None, exact, heard, autojunk=False)
    mapping = {a + i: b + i for a, b, n in m.get_matching_blocks() for i in range(n)}
    for tag, a, b, c, d in m.get_opcodes():
        if tag == 'replace':
            for i in range(b - a):
                mapping.setdefault(a + i, c + min(i * (d - c) // max(b - a, 1), d - c - 1))
    dump(edit / 'transcript-check.json', {'ratio': m.ratio(),
         'differences': [{'script': exact[a:b], 'asr': heard[c:d]} for t, a, b, c, d in m.get_opcodes() if t != 'equal']})
    cues, offset = [], 0
    for line in plan['lines']:
        for rows_, shot in zip(line['screens'], line['shots']):
            n = len(norm(''.join(rows_)))
            hits = [mapping[x] for x in range(offset, offset + n) if x in mapping]
            cue = {'rows': rows_, 'shot': shot, 'line': line['line'], 'chars': n}
            if len(hits) >= n * .5:
                cue['start'], cue['end'] = float(retime(clocks[min(hits)][0])), float(retime(clocks[max(hits)][1]))
            cues.append(cue)
            offset += n
    assert offset == len(exact)
    # 앞 화면보다 앞서는 시각은 인식 오류로 보고 버린다.
    last = 0.0
    for c in cues:
        if 'start' in c:
            if c['start'] < last - .05 or c['end'] - c['start'] < .15:
                del c['start'], c['end']
            else:
                last = c['end']
    # 인식이 빠진 화면은 앞뒤 확정 시각 사이를 글자 수 비율로 나눈다.
    i = 0
    while i < len(cues):
        if 'start' in cues[i]:
            i += 1
            continue
        j = i
        while j < len(cues) and 'start' not in cues[j]:
            j += 1
        a = cues[i - 1]['end'] if i else 0.0
        b = cues[j]['start'] if j < len(cues) else audio_dur
        total = sum(c['chars'] for c in cues[i:j])
        t = a
        for c in cues[i:j]:
            span = (b - a) * c['chars'] / total
            c['start'], c['end'], c['estimated'] = t, t + span, True
            t += span
        i = j
    duration = math.ceil((audio_dur + .35) * FPS) / FPS
    for i, c in enumerate(cues):
        c['display_start'] = 0 if i == 0 else round((cues[i - 1]['end'] + c['start']) / 2 * FPS) / FPS
        c['display_end'] = duration if i == len(cues) - 1 else round((c['end'] + cues[i + 1]['start']) / 2 * FPS) / FPS
        assert c['display_end'] > c['display_start'], c
    dump(edit / 'timed-cues.json', cues)
    return cues, duration, m.ratio()


# ---------- 그림 트랙 ----------
def segments(cues):
    segs = []
    for c in cues:
        if segs and segs[-1]['shot'] == c['shot']:
            segs[-1]['end'] = c['display_end']
        else:
            segs.append({'shot': c['shot'], 'start': c['display_start'], 'end': c['display_end']})
    return segs


def art_segment(ep, edit, i, seg, used):
    out = edit / f'art-{i:02}.mp4'
    dur = seg['end'] - seg['start']
    frames = round(dur * FPS)
    clip = ep / 'clips' / f"{seg['shot']}.mp4"
    clip_len = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(clip)]))
    # clip-edits.json: {"07": {"start": 1.9, "end": 6, "crop": [x, y, size]}} 검수에서 걸러낸 구간·영역만 쓴다.
    edits_file = ep / 'clip-edits.json'
    fix = json.loads(edits_file.read_text(encoding='utf-8')).get(seg['shot'], {}) if edits_file.exists() else {}
    t0, t1 = fix.get('start', 0.0), min(fix.get('end', clip_len), clip_len)
    usable = t1 - t0 - .15
    pre = f'trim=start={t0}:end={t1},setpts=PTS-STARTPTS,' if fix.get('start') or fix.get('end') else ''
    crop = f'crop={CLIP_CROP}'
    if 'crop' in fix:
        x, y, s = fix['crop']
        crop += f',crop={round(720 * s)}:{round(720 * s)}:{round(720 * x)}:{round(720 * y)},scale=720:720:flags=lanczos'
    speed = min(max(dur / usable, 1.0), 2.0)       # 길면 최대 2배까지 느리게, 그 뒤는 마지막 프레임 유지
    reuse = used.count(seg['shot'])
    used.append(seg['shot'])
    # 처음 쓰는 컷은 천천히 살짝 줌인, 다시 쓰는 컷은 얼굴 쪽 클로즈업으로 시작해 변화를 준다.
    if reuse == 0:
        z0, z1, cy = 1.0, 1.06, .5
    elif reuse == 1:
        z0, z1, cy = 1.30, 1.38, .38
    else:
        z0, z1, cy = 1.15, 1.0, .45
    zexpr = f"{z0}+({z1}-{z0})*min(on/{max(frames - 1, 1)},1)"
    vf = (f"{pre}{crop},setpts={speed:.4f}*(PTS-STARTPTS),tpad=stop_mode=clone:stop_duration=30,"
          f"minterpolate=fps={FPS}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1,"
          f"scale=2160:2160:flags=lanczos,"
          f"zoompan=z='{zexpr}':x='iw/2-iw/zoom/2':y='max(0,min(ih-ih/zoom,ih*{cy}-ih/zoom/2))':d=1:s=1080x1080:fps={FPS},setsar=1")
    if not out.exists():
        run(['-i', clip, '-vf', vf, '-frames:v', frames, '-an', '-c:v', 'libx264', '-crf', '17', '-preset', 'fast',
             '-pix_fmt', 'yuv420p', out])
    return out, {'shot': seg['shot'], 'seconds': [seg['start'], seg['end']], 'speed': speed, 'zoom': [z0, z1], 'reuse': reuse}


def main():
    ep = Path(sys.argv[1]).resolve()
    edit = ep / 'edit'
    edit.mkdir(exist_ok=True)
    plan = json.loads((ep / 'caption-plan.json').read_text(encoding='utf-8'))
    rows = align(ep)
    audio, retime, audio_dur = tighten(ep, edit)
    cues, duration, ratio = cue_times(ep, edit, plan, rows, retime, audio_dur)
    print(f'{ep.name}: {len(cues)} screens, {duration:.2f}s, transcript ratio {ratio:.3f}', flush=True)
    if '--align-only' in sys.argv:
        return

    # 그림 트랙
    used, parts, shotplan = [], [], []
    for i, seg in enumerate(segments(cues)):
        p, info = art_segment(ep, edit, i, seg, used)
        parts.append(p)
        shotplan.append(info)
    dump(edit / 'shot-plan.json', shotplan)
    (edit / 'concat.txt').write_text('\n'.join(f"file '{p.as_posix()}'" for p in parts), encoding='utf-8')
    art = edit / 'art-track.mp4'
    run(['-f', 'concat', '-safe', '0', '-i', edit / 'concat.txt', '-c', 'copy', art])

    # 제목·자막
    title_png(plan['title'], edit / 'title.png')
    inputs, chain, last = ['-i', art, '-i', edit / 'title.png'], [f'[0:v]pad=1080:1920:0:{ART_Y}:color=black,setsar=1[bg]',
                                                                    '[bg][1:v]overlay=0:0[t]'], 't'
    for i, c in enumerate(cues):
        png = edit / f'cap-{i:02}.png'
        c['font_size'] = caption_png(c['rows'], png)
        inputs += ['-i', png]
        chain.append(f"[{last}][{i + 2}:v]overlay=0:0:enable='between(t,{c['display_start']:.4f},{c['display_end'] - 1 / FPS:.4f})'[c{i}]")
        last = f'c{i}'
    final = ep / 'final.mp4'
    run([*inputs, '-i', audio, '-filter_complex', ';'.join(chain), '-map', f'[{last}]', '-map', f'{len(cues) + 2}:a',
         '-af', 'loudnorm=I=-16:TP=-1.5:LRA=7,apad', '-t', f'{duration:.4f}', '-r', FPS,
         '-c:v', 'libx264', '-crf', '18', '-preset', 'medium', '-pix_fmt', 'yuv420p',
         '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-movflags', '+faststart', final])

    def stamp(t):
        ms = round(t * 1000)
        return f'{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}'
    (ep / 'captions.srt').write_text('\n\n'.join(f"{i + 1}\n{stamp(c['display_start'])} --> {stamp(c['display_end'])}\n" + '\n'.join(c['rows'])
                                                 for i, c in enumerate(cues)) + '\n', encoding='utf-8')
    run(['-ss', f"{cues[0]['display_end'] * .6:.2f}", '-i', final, '-frames:v', 1, '-q:v', 2, ep / 'poster.jpg'])
    dump(edit / 'timed-cues.json', cues)
    print('done', final, flush=True)


if __name__ == '__main__':
    main()
