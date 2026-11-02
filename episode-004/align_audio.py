"""Read the already installed/cached local ASR; never download a model."""
from pathlib import Path
import json,sys
from faster_whisper import WhisperModel

root=Path(__file__).resolve().parent
source=root/'audio'/(sys.argv[1] if len(sys.argv)>1 else 'narration-raw.wav')
model=WhisperModel('small',device='cpu',compute_type='int8',
    download_root='C:/Codex/인스타자동화_사원2/insta_auto/data/models/faster-whisper',local_files_only=True)
segments,_=model.transcribe(str(source),language='ko',word_timestamps=True,beam_size=5,vad_filter=True)
rows=[]
for s in segments:
    rows.append({'start':s.start,'end':s.end,'text':s.text,
                 'words':[{'start':w.start,'end':w.end,'word':w.word} for w in s.words]})
    print(f'{s.start:.2f}-{s.end:.2f} {s.text}',flush=True)
(root/'audio'/(source.stem+'-alignment.json')).write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
