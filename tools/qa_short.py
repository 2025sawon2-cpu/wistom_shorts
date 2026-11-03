"""최종 MP4 자동 검수: 규격, 전체 디코딩 오류, 음량, 최종 음성 전사 대조, 전 구간 접촉 시트.
사용: .venv/bin/python tools/qa_short.py episode-005
결과: episode-XXX/edit/final-qa.json, edit/final-review.jpg
"""
import difflib
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from platform_paths import whisper_dir  # noqa: E402

ep = Path(sys.argv[1]).resolve()
video = ep / 'final.mp4'
edit = ep / 'edit'
info = json.loads(subprocess.check_output(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(video)]))
v = next(s for s in info['streams'] if s['codec_type'] == 'video')
a = next(s for s in info['streams'] if s['codec_type'] == 'audio')
decode = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(video), '-f', 'null', os.devnull], capture_output=True, text=True).stderr.strip()
loud = subprocess.run(['ffmpeg', '-hide_banner', '-i', str(video), '-af', 'ebur128=peak=true', '-f', 'null', '-'],
                      capture_output=True, text=True).stderr
lufs = re.findall(r'I:\s+(-?[\d.]+) LUFS', loud)[-1]
peak = re.findall(r'Peak:\s+(-?[\d.]+) dBFS', loud)[-1]

from faster_whisper import WhisperModel  # noqa: E402
model = WhisperModel('small', device='cpu', compute_type='int8', download_root=whisper_dir(), local_files_only=True)
segs, _ = model.transcribe(str(video), language='ko', beam_size=5, vad_filter=True, condition_on_previous_text=False)
heard = ''.join(s.text for s in segs)
norm = lambda t: re.sub('[^가-힣A-Za-z0-9]', '', t)  # noqa: E731
script = (ep / 'audio/narration.txt').read_text(encoding='utf-8')
ratio = difflib.SequenceMatcher(None, norm(script), norm(heard), autojunk=False).ratio()

dur = float(info['format']['duration'])
n = 24
step = dur / n
subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', str(video), '-vf', f'fps=1/{step:.3f},scale=270:480,tile=8x3',
                '-frames:v', '1', str(edit / 'final-review.jpg')], check=True)
result = {
    'file': str(video.relative_to(ep.parent)), 'bytes': video.stat().st_size,
    'sha256': hashlib.sha256(video.read_bytes()).hexdigest(),
    'size': f"{v['width']}x{v['height']}", 'fps': v['r_frame_rate'], 'frames': int(v.get('nb_frames', 0)),
    'seconds': round(dur, 3), 'video_codec': v['codec_name'], 'audio_codec': a['codec_name'],
    'decode_errors': decode or None, 'loudness_lufs': float(lufs), 'true_peak_dbfs': float(peak),
    'asr_ratio_vs_script': round(ratio, 4), 'asr_text': heard,
    'note': '자동 검사 결과다. 직접 청감·사용자 취향 확인은 별도다.',
}
(edit / 'final-qa.json').write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding='utf-8')
print(json.dumps({k: result[k] for k in ('size', 'fps', 'seconds', 'decode_errors', 'loudness_lufs', 'true_peak_dbfs', 'asr_ratio_vs_script')}, ensure_ascii=False))
