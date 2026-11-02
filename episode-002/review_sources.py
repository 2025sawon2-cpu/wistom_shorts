from pathlib import Path
import subprocess
from PIL import Image,ImageDraw
root=Path(__file__).resolve().parent
files=sorted((root/'clips/raw-downloads').glob('*.mp4'))
sheet=Image.new('RGB',(960,len(files)*340),'#ddd')
d=ImageDraw.Draw(sheet)
for row,p in enumerate(files):
    d.text((8,row*340+4),p.name,fill='black')
    for col,t in enumerate([0.15,2.8,5.7]):
        out=root/'edit'/f'{p.stem}-{col}.jpg'
        subprocess.run(['ffmpeg','-y','-v','error','-ss',str(t),'-i',str(p),'-frames:v','1',str(out)],check=True)
        im=Image.open(out); im.thumbnail((310,310))
        sheet.paste(im,(col*320+(320-im.width)//2,row*340+25))
sheet.save(root/'edit/raw-motion-review.jpg')
