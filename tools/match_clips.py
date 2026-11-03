"""다운로드 폴더의 Flow 클립을 첫 프레임으로 각 편의 패널과 대조해 episode-XXX/clips/NN.mp4로 옮긴다.
사용: .venv/bin/python tools/match_clips.py --eps 5-9 ~/Downloads/*.mp4
  --eps: 대조할 편 번호 범위(예: 10-14) 또는 쉼표 목록(10,12). 각 편에 images/flow-inputs/01~09.png가 있어야 한다.
기준: 첫 프레임 그림 영역 48x48 흑백 MSE < 300 이고 2순위가 2배 이상 멀 때만 옮긴다. 이미 있는 NN.mp4는 덮지 않는다.
"""
import subprocess, sys, shutil, io, json
from pathlib import Path
import numpy as np
from PIL import Image
ROOT = Path(__file__).resolve().parents[1]
def vec(im):
    return np.asarray(im.convert('L').resize((48, 48), Image.BILINEAR), dtype=np.float32).ravel()
args = sys.argv[1:]
EPS = list(range(5, 10))
if args and args[0] == '--eps':
    spec, args = args[1], args[2:]
    EPS = [int(x) for x in spec.split(',')] if ',' in spec or '-' not in spec else list(range(int(spec.split('-')[0]), int(spec.split('-')[1]) + 1))
name = lambda e: f'episode-{e:03}'  # noqa: E731
refs = {}
for e in EPS:
    for i in range(1, 10):
        refs[(e, i)] = vec(Image.open(ROOT / name(e) / f'images/flow-inputs/{i:02}.png').crop((0, 280, 720, 1000)))
srcs = [Path(p) for p in args]
report = []
for p in srcs:
    raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(p), '-frames:v', '1', '-f', 'image2pipe', '-vcodec', 'png', '-'])
    im = Image.open(io.BytesIO(raw)).convert('RGB')
    if im.size != (720, 1280):
        report.append({'file': p.name, 'skip': f'size {im.size}'}); continue
    v = vec(im.crop((0, 280, 720, 1000)))
    scores = sorted((float(np.mean((v - r) ** 2)), k) for k, r in refs.items())
    (best, (e, i)), second = scores[0], scores[1][0]
    dest = ROOT / name(e) / f'clips/{i:02}.mp4'
    dest.parent.mkdir(exist_ok=True)
    ok = best < 300 and second > best * 2
    report.append({'file': p.name, 'episode': e, 'shot': i, 'mse': round(best, 1), 'second': round(second, 1), 'moved': ok and not dest.exists()})
    if ok and not dest.exists():
        shutil.move(str(p), dest)
print(json.dumps(report, ensure_ascii=False, indent=0))
have = {(e, i) for e in EPS for i in range(1, 10) if (ROOT / name(e) / f'clips/{i:02}.mp4').exists()}
print('missing:', [f'e{e:03}-{i:02}' for e in EPS for i in range(1, 10) if (e, i) not in have])
