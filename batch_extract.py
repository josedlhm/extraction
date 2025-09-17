from pathlib import Path
from extract import extract_svo2
IN_DIR = Path('/home/user/Desktop/imperial/')
OUT_DIR = Path ('/home/user/Desktop/imperial_out/')

MAX_FRAMES = 100000
OUT_DIR.mkdir(exist_ok=True)

for svo in sorted(IN_DIR.glob("ZEDXMini_SN50918724*.svo*")):
    extract_svo2(str(svo),str(OUT_DIR/svo.stem), MAX_FRAMES)
