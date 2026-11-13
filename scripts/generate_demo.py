"""Rebuild bundled eight-second clips from the credited JPEG inputs; no network required."""
import subprocess
from pathlib import Path

root=Path(__file__).resolve().parent.parent/'assets'/'demo'
for index,path in enumerate(sorted(root.glob('*.jpg')),1):
    subprocess.run(['ffmpeg','-v','error','-loop','1','-i',str(path),'-f','lavfi','-i',
        f'sine=frequency={180+index*40}:sample_rate=44100','-vf',
        "scale=1280:720:force_original_aspect_ratio=increase,crop=1280:720,zoompan=z='min(zoom+0.0005,1.12)':d=200:s=960x540:fps=25,format=yuv420p",
        '-af','volume=0.025,afade=t=in:d=1,afade=t=out:st=7:d=1','-t','8','-c:v','libx264',
        '-threads','1','-preset','veryfast','-crf','26','-c:a','aac','-movflags','+faststart','-y',str(path.with_suffix('.mp4'))],check=True,timeout=90)

