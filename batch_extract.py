from pathlib import Path
import shutil, json
from datetime import datetime
from extract import extract_svo2   # keep your existing extractor

IN_DIR = Path('/home/user/Desktop/imperial/')
OUT_DIR = Path('/home/user/Desktop/imperial_out/')
MAX_FRAMES = 100000
OUT_DIR.mkdir(exist_ok=True)

SVO_PREFIX = "ZEDXMini_SN50918724"

for cap_dir in sorted([d for d in IN_DIR.iterdir() if d.is_dir()]):
    # look for the target SVO inside this capture folder
    svos = sorted(cap_dir.glob(f"{SVO_PREFIX}*.svo*"))
    if not svos:
        continue

    svo = svos[0]
    out_dir = OUT_DIR / cap_dir.name
    out_dir.mkdir(parents=True, exist_ok=True)

    # run extraction
    extract_svo2(str(svo), str(out_dir), MAX_FRAMES)

    # copy metadata.json (or fallback)
    meta_src = cap_dir / "metadata.json"
    meta_dst = out_dir / "metadata.json"
    if meta_src.exists():
        shutil.copy2(meta_src, meta_dst)
    else:
        fecha = datetime.fromtimestamp(svo.stat().st_mtime).date().isoformat()
        with open(meta_dst, "w", encoding="utf-8") as f:
            json.dump({"fecha": fecha, "variedad": "", "lado": ""}, f, indent=2)

    # write intrinsics.json
    intrinsics = [1272.44, 1272.67, 920.062, 618.949]
    with open(out_dir / "intrinsics.json", "w", encoding="utf-8") as f:
        json.dump(intrinsics, f, indent=2)
