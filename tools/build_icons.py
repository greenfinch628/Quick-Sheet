"""Rebuild the matching platform icons; requires Pillow only at build time."""
from pathlib import Path
from PIL import Image, ImageDraw

OUT = Path(__file__).resolve().parents[1] / 'assets'
OUT.mkdir(exist_ok=True)
svg = '''<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">
<rect x="24" y="24" width="464" height="464" rx="104" fill="#125a46"/>
<path d="M124 92H322L396 166V398Q396 420 374 420H138Q116 420 116 398V114Q116 92 124 92Z" fill="#f5fbf7"/>
<path d="M322 92V146Q322 166 342 166H396Z" fill="#88d4ac"/>
<rect x="148" y="192" width="216" height="42" rx="6" fill="#21825f"/>
<rect x="148" y="248" width="64" height="56" rx="4" fill="#b8e6ce"/>
<rect x="224" y="248" width="64" height="56" rx="4" fill="#b8e6ce"/>
<rect x="300" y="248" width="64" height="56" rx="4" fill="#b8e6ce"/>
<rect x="148" y="316" width="64" height="56" rx="4" fill="#b8e6ce"/>
<rect x="224" y="316" width="64" height="56" rx="4" fill="#b8e6ce"/>
<rect x="300" y="316" width="64" height="56" rx="4" fill="#21825f"/>
</svg>'''
(OUT / 'Quick-Sheet.svg').write_text(svg, encoding='utf-8')
scale=4
image=Image.new('RGBA',(512*scale,512*scale))
draw=ImageDraw.Draw(image)
def rect(box,color,radius=0):
    draw.rounded_rectangle(tuple(v*scale for v in box),radius=radius*scale,fill=color)
def polygon(points,color):
    draw.polygon([(x*scale,y*scale) for x,y in points],fill=color)
rect((24,24,488,488),'#125a46',104)
rect((116,92,396,420),'#f5fbf7',22)
polygon([(322,92),(396,92),(396,166)],'#125a46')
polygon([(322,92),(322,166),(396,166)],'#88d4ac')
rect((148,192,364,234),'#21825f',6)
for y in (248,316):
    for x in (148,224,300):
        rect((x,y,x+64,y+56),'#21825f' if (x,y)==(300,316) else '#b8e6ce',4)
image=image.resize((512,512),Image.Resampling.LANCZOS)
image.save(OUT/'Quick-Sheet.png')
image.save(OUT/'Quick-Sheet.ico',sizes=[(16,16),(24,24),(32,32),(48,48),(64,64),(128,128),(256,256)])
print(OUT)
