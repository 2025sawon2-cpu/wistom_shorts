"""Capture actual final-file evidence; keep subjective listening separate."""
from pathlib import Path
import hashlib,json,subprocess
from PIL import Image,ImageDraw
root=Path(__file__).resolve().parent;out=root/'edit';video=root/'final.mp4'
info=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',str(video)]))
v=next(s for s in info['streams'] if s['codec_type']=='video')
assert (v['width'],v['height'],v['r_frame_rate'])==(1080,1920,'60/1')
assert any(s['codec_type']=='audio' for s in info['streams'])
decode=subprocess.run(['ffmpeg','-v','error','-i',str(video),'-f','null','NUL'],capture_output=True,text=True)
assert decode.returncode==0 and not decode.stderr,decode.stderr
cues=json.loads((out/'timed-cues.json').read_text(encoding='utf-8'))
for page in range((len(cues)+8)//9):
 sheet=Image.new('RGB',(1080,1980),'#333');d=ImageDraw.Draw(sheet)
 for j,c in enumerate(cues[page*9:page*9+9]):
  idx=page*9+j;t=(c['display_start']+c['display_end'])/2;p=out/f'final-screen-{idx:02}.jpg'
  subprocess.run(['ffmpeg','-y','-v','error','-ss',str(t),'-i',str(video),'-frames:v','1',str(p)],check=True)
  im=Image.open(p).resize((360,640),Image.Resampling.LANCZOS);x=(j%3)*360;y=(j//3)*660
  sheet.paste(im,(x,y+20));d.text((x+6,y+3),f'{idx:02} {t:.2f}s {c["shot"]}',fill='white')
 sheet.save(out/f'final-review-{page+1}.jpg',quality=95)
subprocess.run(['ffmpeg','-y','-v','error','-ss','35.8','-i',str(video),'-frames:v','1',str(root/'poster.jpg')],check=True)
evidence={'file':str(video),'sha256':hashlib.sha256(video.read_bytes()).hexdigest(),'bytes':video.stat().st_size,'seconds':float(info['format']['duration']),'frames':v.get('nb_frames'),'fps':v['r_frame_rate'],'size':[v['width'],v['height']],'decode_errors':decode.stderr,'screens':len(cues),'listening':'not directly heard; ASR and playback checked separately'}
(out/'final-file-check.json').write_text(json.dumps(evidence,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(evidence,ensure_ascii=False,indent=2))
