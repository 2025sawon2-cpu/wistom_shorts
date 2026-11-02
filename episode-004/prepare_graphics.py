"""Prepare this episode's checked typography and letterboxed Flow inputs.

No voice, motion or final render is synthesized by this preparation command.
"""
from pathlib import Path
import json
import re
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'edit'
SOURCES = {
    '01': '01-payment-shop.png', '02': '02-catalog.png',
    '03': '03-choice-v2.png', '04': '04-delay-call.png',
    '05': '05-transfer.png', '06': '06-sora-payday.png',
    '07': '07-closing.png',
}

def font(size, dialogue=False):
    path = 'C:/Windows/Fonts/' + ('NotoSerifKR-VF.ttf' if dialogue else 'NotoSansKR-VF.ttf')
    f = ImageFont.truetype(path, size)
    f.set_variation_by_name('Bold')
    return f

def centered(im, text, cy, size, color, stroke=0, dialogue=False):
    d = ImageDraw.Draw(im)
    f = font(size, dialogue)
    b = d.textbbox((0, 0), text, font=f, stroke_width=stroke)
    assert b[2] - b[0] <= 1000, text
    d.text(((1080 - b[2] - b[0]) / 2, cy - (b[3] + b[1]) / 2), text,
           font=f, fill=color, stroke_width=stroke, stroke_fill='black')

def title():
    im = Image.new('RGBA', (1080, 1920), (0, 0, 0, 0))
    centered(im, '낡은 간판을', 210, 96, 'white')
    centered(im, '바꾸지 않은 이유', 325, 96, '#FF982F')
    return im

def plate(rows, dialogue):
    im = Image.new('RGBA', (1080, 1920), (0, 0, 0, 0))
    size = 70 if dialogue else 67
    assert 1 <= len(rows) <= 2
    if dialogue:
        assert rows[0].startswith('“') and rows[-1].endswith('”'), rows
    widths = [ImageDraw.Draw(im).textlength(row, font=font(size, dialogue)) for row in rows]
    assert max(widths) <= 940, (rows, widths)
    for i, row in enumerate(rows):
        centered(im, row, 1470 + (i - (len(rows) - 1) / 2) * 84,
                 size, '#FFE35C' if dialogue else 'white', 5 if dialogue else 7, dialogue)
    return im, widths

def prepare_inserts():
    """Exact text overlays, prepared on the original square before shot crops.

    Apply after motion interpolation. Coordinates must be checked against the
    real generated clip; preparation is not proof of motion tracking quality.
    """
    folder = ROOT / 'graphics'
    folder.mkdir(exist_ok=True)
    def projected(rows, quad, color='#493E2D', size=70, canvas=(600, 180)):
        tile = Image.new('RGBA', canvas, (0, 0, 0, 0))
        draw = ImageDraw.Draw(tile)
        for i, row in enumerate(rows):
            draw.text((canvas[0] / 2, canvas[1] * (i + 1) / (len(rows) + 1)), row,
                      anchor='mm', font=font(size), fill=color)
        a, b = [], []
        source = [(0, 0), (canvas[0], 0), canvas, (0, canvas[1])]
        for (x, y), (u, v) in zip(quad, source):
            a.extend([[x, y, 1, 0, 0, 0, -u*x, -u*y],
                      [0, 0, 0, x, y, 1, -v*x, -v*y]])
            b.extend([u, v])
        coeffs = np.linalg.solve(np.array(a, float), np.array(b, float))
        layer = tile.transform((1254, 1254), Image.Transform.PERSPECTIVE,
                               tuple(coeffs), Image.Resampling.BICUBIC)
        return layer.resize((1080, 1080), Image.Resampling.LANCZOS)
    overlays = {
        '01-sign': ('01', projected(['지훈 인쇄'], [(875, 90), (1190, 183), (1188, 270), (875, 187)])),
        '07-sign': ('07', projected(['지훈 인쇄'], [(787, 88), (1112, 179), (1110, 309), (787, 221)])),
        '03-note': ('03', projected(['다음 달 급여일'], [(650, 1110), (816, 1110), (824, 1135), (640, 1135)], size=70, canvas=(600, 100))),
        '04-calendar': ('04', projected(['급여일'], [(1101, 334), (1241, 313), (1240, 389), (1100, 413)], color='#A8402C', size=80)),
    }
    def notice(title_text, message):
        layer = Image.new('RGBA', (1080, 1080), (0, 0, 0, 0))
        d = ImageDraw.Draw(layer)
        d.rounded_rectangle((35, 30, 760, 165), radius=18, fill=(255, 247, 227, 242), outline='#9B7851', width=2)
        d.text((63, 48), title_text, font=font(29), fill='#73583B')
        d.text((63, 94), message, font=font(40), fill='#1F382F')
        return layer
    overlays.update({
        '01-payment': ('01', notice('인쇄소', '거래 대금이 입금되었습니다')),
        '05-transfer': ('05', notice('급여 이체', '이체가 완료되었습니다')),
        '06-salary': ('06', notice('입금 알림', '급여가 입금되었습니다')),
    })
    for name, (art, layer) in overlays.items():
        layer.save(folder / f'{name}.png')
        with Image.open(ROOT / 'images' / SOURCES[art]) as src:
            preview = src.convert('RGBA').resize((1080, 1080), Image.Resampling.LANCZOS)
        preview.alpha_composite(layer)
        preview.convert('RGB').save(folder / f'{name}-preview.jpg', quality=95)
    (folder / 'insert-plan.json').write_text(json.dumps({
        'status': 'prepared overlays; inspect and align with actual generated motion before use',
        'space': '1080 square artwork, applied after interpolation and before shot crop',
        'files': {name: {'art': art, 'overlay': name + '.png'} for name, (art, _) in overlays.items()},
        'notes': 'Not bank screenshots. These are editorial labels for a fictional story. No amount, real account or specific payment date invented.'
    }, ensure_ascii=False, indent=2), encoding='utf-8')

def prepare():
    OUT.mkdir(exist_ok=True)
    flow = ROOT / 'images' / 'flow-inputs'
    flow.mkdir(exist_ok=True)
    plan = json.loads((ROOT / 'caption-plan.json').read_text(encoding='utf-8'))
    lines = (ROOT / 'audio' / 'narration.txt').read_text(encoding='utf-8').splitlines()
    normal = lambda t: re.sub('[^가-힣A-Za-z0-9]', '', t)
    assert len(plan) == len(lines)
    count = 0
    widths = []
    for n, (entry, line) in enumerate(zip(plan, lines), 1):
        assert entry['line'] == n
        assert len(entry['screens']) == len(entry['shots'])
        assert normal(''.join(''.join(s) for s in entry['screens'])) == normal(line), line
        for rows, shot in zip(entry['screens'], entry['shots']):
            assert shot[:2] in SOURCES, shot
            p, measured = plate(rows, line.startswith('“'))
            im = title()
            im.alpha_composite(p)
            im.save(OUT / f'overlay-{count:02}.png')
            count += 1
            widths.extend(measured)
    source_checks = []
    for key, name in SOURCES.items():
        path = ROOT / 'images' / name
        with Image.open(path) as src:
            src.load()
            assert src.width == src.height, (name, src.size)
            frame = Image.new('RGB', (720, 1280), 'black')
            frame.paste(src.convert('RGB').resize((720, 720), Image.Resampling.LANCZOS), (0, 280))
            frame.save(flow / f'{key}.png')
            source_checks.append({'id': key, 'file': name, 'size': list(src.size),
                                  'flow_size': [720, 1280], 'art_box': [0, 280, 720, 1000]})
    title().save(OUT / 'title.png')
    prepare_inserts()
    for cue, art, label in [(3, '02', 'dialogue'), (9, '03', 'narration'), (30, '07', 'ending')]:
        im = Image.new('RGBA', (1080, 1920), 'black')
        with Image.open(ROOT / 'images' / SOURCES[art]) as src:
            im.paste(src.convert('RGBA').resize((1080, 1080), Image.Resampling.LANCZOS), (0, 490))
        im.alpha_composite(Image.open(OUT / f'overlay-{cue:02}.png'))
        im.convert('RGB').save(OUT / f'layout-{label}.jpg', quality=95)
    result = {'screens': count, 'script_lines': len(lines), 'max_text_width': max(widths),
              'dialogue_font': 'Noto Serif KR Bold', 'narration_font': 'Noto Sans KR Bold',
              'title': ['낡은 간판을', '바꾸지 않은 이유'],
              'dialogue_quotes': 'each screen has a complete pair',
              'sources': source_checks,
              'status': 'prepared only; web voice and generated motion still required'}
    (OUT / 'typography-check.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    prepare()
