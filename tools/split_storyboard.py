"""3x3 스토리보드 이미지를 검은 구분선 기준으로 9개 정사각 패널로 자른다.
사용: python tools/split_storyboard.py episode-005
결과: episode-XXX/images/panel-1.png ~ panel-9.png (각 1440x1440, 구분선 제외 후 약간 안쪽으로 자름)
      episode-XXX/images/flow-inputs/01.png ~ 09.png (Flow 첫 프레임용 720x1280 검정 캔버스, 그림 720 정사각이 y=280)
패널 하나만 손으로 다시 자른 뒤에는 --inputs-only 로 flow-inputs만 다시 만든다.
"""
import sys
from pathlib import Path
import numpy as np
from PIL import Image

def bands(profile, n):
    """어두운 구분선 위치를 찾아 n등분 경계를 돌려준다."""
    size = len(profile)
    cuts = [0]
    for k in range(1, n):
        guess = size * k // n
        lo, hi = guess - size // 20, guess + size // 20
        seg = profile[lo:hi]
        dark = np.where(seg < seg.min() + 12)[0]
        cuts.append(lo + int(dark.mean()) if len(dark) else guess)
    cuts.append(size)
    return cuts

ep = Path(sys.argv[1])


def flow_inputs():
    out = ep / 'images/flow-inputs'
    out.mkdir(exist_ok=True)
    for n in range(1, 10):
        canvas = Image.new('RGB', (720, 1280), 'black')
        canvas.paste(Image.open(ep / f'images/panel-{n}.png').convert('RGB').resize((720, 720), Image.LANCZOS), (0, 280))
        canvas.save(out / f'{n:02}.png')


if '--inputs-only' in sys.argv:
    flow_inputs()
    sys.exit()
im = Image.open(ep / 'images/storyboard-4k.jpg').convert('RGB')
a = np.asarray(im.convert('L'), dtype=np.float32)
xs, ys = bands(a.mean(0), 3), bands(a.mean(1), 3)
n = 0
for r in range(3):
    for c in range(3):
        n += 1
        x0, x1, y0, y1 = xs[c], xs[c + 1], ys[r], ys[r + 1]
        # 구분선 두께만큼 안쪽으로 들어가고, 정사각형으로 맞춘다.
        m = 28
        box = [x0 + m, y0 + m, x1 - m, y1 - m]
        w, h = box[2] - box[0], box[3] - box[1]
        s = min(w, h)
        box = [box[0] + (w - s) // 2, box[1] + (h - s) // 2]
        box += [box[0] + s, box[1] + s]
        im.crop(box).resize((1440, 1440), Image.LANCZOS).save(ep / f'images/panel-{n}.png')
flow_inputs()
print(ep, 'cols', xs, 'rows', ys)
