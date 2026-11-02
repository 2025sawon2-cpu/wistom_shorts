"""Transcribe this episode with the already installed local Whisper runtime."""
from pathlib import Path
import json
from faster_whisper import WhisperModel

root=Path(__file__).resolve().parent
model=WhisperModel('small',device='cpu',compute_type='int8',
    download_root='C:/Codex/인스타자동화_사원2/insta_auto/data/models/faster-whisper',
    local_files_only=True)
segments,info=model.transcribe(str(root/'audio/narration-arlo.wav'),
    language='ko',word_timestamps=True,beam_size=5,vad_filter=True)
data=[]
for s in segments:
    row={'start':s.start,'end':s.end,'text':s.text,
         'words':[{'start':w.start,'end':w.end,'word':w.word} for w in s.words]}
    data.append(row)
    print(f'{s.start:.2f} - {s.end:.2f}: {s.text}',flush=True)
(root/'audio/narration-alignment.json').write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
