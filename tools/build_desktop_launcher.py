"""Build a small native Windows launcher for this existing Python project.

This is a local-environment launcher, not a bundled Python installer.
"""
from pathlib import Path
import subprocess
import sys

root=Path(__file__).resolve().parents[1]
compiler=Path('C:/Windows/Microsoft.NET/Framework64/v4.0.30319/csc.exe')
if not compiler.is_file():raise SystemExit('Windows .NET Framework C# compiler is unavailable')
from PIL import Image,ImageDraw
image=Image.new('RGBA',(256,256),'#183c43');draw=ImageDraw.Draw(image)
points=[(65,185),(69,70),(180,61),(189,181),(125,128)]
for a,b in [(0,1),(1,2),(2,3),(3,0),(0,4),(2,4)]:draw.line([points[a],points[b]],fill='#a7e3cc',width=11)
for x,y in points:draw.ellipse((x-15,y-15,x+15,y+15),fill='#e8fff5')
out=root/'outputs/desktop-build';out.mkdir(parents=True,exist_ok=True)
icon=out/'desktop.ico';image.save(icon,format='ICO',sizes=[(16,16),(32,32),(48,48),(64,64),(128,128),(256,256)])
destination=root/'图论科研助手.exe'
subprocess.run([str(compiler),'/nologo','/target:winexe','/reference:System.Windows.Forms.dll','/win32icon:'+str(icon),
                '/out:'+str(destination),str(root/'tools/DesktopLauncher.cs')],check=True)
print(destination)
