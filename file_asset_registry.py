import os, sys, csv, hashlib, shutil
from pathlib import Path
from typing import Tuple

try:
	from PIL import Image, ImageOps
	PIL_OK = True
except Exception:
	PIL_OK = False

IMG_EXTS = {".jpg",".jpeg",".png",".tif",".tiff",".bmp",".webp",".JPG",".JPEG",".PNG",".TIF",".TIFF",".BMP",".WEBP"}

def sha256_file(path: Path, bufsize: int = 1024*1024) -> str:
	h = hashlib.sha256()
	with path.open("rb") as f:
		while True:
			b = f.read(bufsize)
			if not b: break
			h.update(b)
	return h.hexdigest()

def ensure_dir(p: Path):
	p.mkdir(parents=True, exist_ok=True)

def copy_or_link(src: Path, dst: Path, mode: str):
	ensure_dir(dst.parent)
	if dst.exists():
		return
	mode = (mode or "copy").lower()
	if mode == "hardlink":
		try:
			os.link(src, dst); return
		except Exception: pass
	if mode == "symlink":
		try:
			os.symlink(src, dst); return
		except Exception: pass
	shutil.copy2(src, dst)

def make_thumb(src: Path, dst: Path, max_side: int = 512) -> Tuple[int,int]:
	if not PIL_OK:
		raise RuntimeError("Pillow not installed. pip install pillow")
	ensure_dir(dst.parent)
	with Image.open(src) as im:
		im = ImageOps.exif_transpose(im)
		w, h = im.size
		scale = max_side / float(max(w, h)) if max(w, h) > max_side else 1.0
		nw, nh = int(w*scale), int(h*scale)
		im = im.resize((nw, nh))
		im.save(dst, format="JPEG", quality=85, optimize=True)
		return nw, nh

def normalize_ext(e: str) -> str:
	e = (e or "").lower()
	return e if e.startswith(".") else ("." + e if e else "")

def to_rel(p: Path, root: Path) -> str:
	return str(p.relative_to(root).as_posix())

def load_registry(path: Path):
	if not path.exists(): return {}
	out = {}
	with path.open("r", encoding="utf-8-sig", newline="") as f:
		r = csv.DictReader(f)
		for row in r:
			out[row.get("doc_id","")] = row
	return out

def write_registry(path: Path, rows: list):
	if not rows: return
	cols = ["doc_id","file","base","ext","size_bytes","width","height","orig_relpath","thumb_relpath"]
	with path.open("w", encoding="utf-8-sig", newline="") as f:
		w = csv.DictWriter(f, fieldnames=cols)
		w.writeheader()
		for r in rows:
			w.writerow(r)

def scan_and_store(src_folder: str, store_root: str, recursive: bool = True, mode: str = "copy", max_side: int = 512):
	src = Path(src_folder)
	store = Path(store_root)
	ensure_dir(store / "orig"); ensure_dir(store / "thumb")
	reg_path = store / "asset_registry.csv"
	reg = load_registry(reg_path)

	files = []
	if recursive:
		files = [p for p in src.rglob("*") if p.is_file() and p.suffix in IMG_EXTS]
	else:
		files = [p for p in src.iterdir() if p.is_file() and p.suffix in IMG_EXTS]

	for p in files:
		try:
			h = sha256_file(p)
			sub = h[:2]
			ext = normalize_ext(p.suffix)
			orig = store / "orig" / sub / f"{h}{ext}"
			thumb = store / "thumb" / sub / f"{h}.jpg"
			copy_or_link(p, orig, mode)
			try:
				w, hgt = make_thumb(orig, thumb, max_side=max_side)
			except Exception:
				w = hgt = ""
			st = p.stat()
			reg[h] = {
				"doc_id": h,
				"file": p.name,
				"base": p.stem,
				"ext": ext,
				"size_bytes": str(st.st_size),
				"width": str(w),
				"height": str(hgt),
				"orig_relpath": to_rel(orig, store),
				"thumb_relpath": to_rel(thumb, store),
			}
		except Exception:
			continue

	write_registry(reg_path, list(reg.values()))
	with (store / "store_root.txt").open("w", encoding="utf-8") as f:
		f.write(str(store.resolve()))
	print(f"Indexed {len(files)} files into {store}/ (registry: {reg_path})")

if __name__ == "__main__":
	import argparse
	ap = argparse.ArgumentParser(description="Build a content-addressable image store with thumbnails and a registry.")
	ap.add_argument("src_folder", help="Folder that contains original images to index")
	ap.add_argument("store_root", help="Root folder of the asset store (will create orig/ and thumb/)")
	ap.add_argument("--no-recursive", action="store_true", help="Do not recurse subfolders")
	ap.add_argument("--mode", choices=["copy","hardlink","symlink"], default="copy", help="How to place originals in the store")
	ap.add_argument("--max-side", type=int, default=512, help="Max side length for thumbnails")
	args = ap.parse_args()
	scan_and_store(args.src_folder, args.store_root, recursive=not args.no_recursive, mode=args.mode, max_side=args.max_side)

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, sys, csv, hashlib, shutil
from pathlib import Path
from typing import Tuple, Dict, List, Optional

try:
    from PIL import Image, ImageOps
    PIL_OK = True
except Exception:
    PIL_OK = False

IMG_EXTS = {".jpg", ".jpeg", ".png", ".tif", ".tiff", ".bmp", ".webp", ".JPG", ".JPEG", ".PNG", ".TIF", ".TIFF", ".BMP", ".WEBP"}


def sha256_file(path: Path, bufsize: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(bufsize)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def ensure_dir(p: Path):
    p.mkdir(parents=True, exist_ok=True)


def copy_or_link(src: Path, dst: Path, mode: str):
    ensure_dir(dst.parent)
    if dst.exists():
        return
    mode = (mode or "copy").lower()
    if mode == "hardlink":
        try:
            os.link(src, dst)
            return
        except Exception:
            pass
    if mode == "symlink":
        try:
            os.symlink(src, dst)
            return
        except Exception:
            pass
    shutil.copy2(src, dst)


def make_thumb(src: Path, dst: Path, max_side: int = 512) -> Tuple[int, int]:
    if not PIL_OK:
        raise RuntimeError("Pillow not installed. pip install pillow")
    ensure_dir(dst.parent)
    with Image.open(src) as im:
        im = ImageOps.exif_transpose(im)
        w, h = im.size
        scale = max_side / float(max(w, h)) if max(w, h) > max_side else 1.0
        nw, nh = int(w * scale), int(h * scale)
        im = im.resize((nw, nh))
        im.save(dst, format="JPEG", quality=85, optimize=True)
        return nw, nh


def normalize_ext(e: str) -> str:
    e = (e or "").lower()
    return e if e.startswith(".") else ("." + e if e else "")


def to_rel(p: Path, root: Path) -> str:
    return str(p.relative_to(root).as_posix())


COLUMNS = [
    "sha256",
    "src_path",
    "src_rel",
    "dst_path",
    "dst_rel",
    "size_bytes",
    "width",
    "height",
    "ext",
    "thumb_rel",
    "mode",
]


def load_registry(path: Path) -> Dict[str, Dict[str, str]]:
    if not path.exists():
        return {}
    out: Dict[str, Dict[str, str]] = {}
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            key = row.get("sha256") or ""
            if not key:
                # スキップ
                continue
            out[key] = row
    return out


def save_registry(path: Path, rows: List[Dict[str, str]]):
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        for row in rows:
            w.writerow({c: row.get(c, "") for c in COLUMNS})


def scan_images(root: Path) -> List[Path]:
    results: List[Path] = []
    for p in root.rglob("*"):
        if p.is_file() and p.suffix in IMG_EXTS:
            results.append(p)
    return results


def main(argv: Optional[List[str]] = None):
    import argparse, json

    # path_config.json から既定値
    image_root_default = None
    output_root_default = None
    cfg_path = Path.cwd() / "path_config.json"
    if cfg_path.exists():
        try:
            cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
            image_root_default = cfg.get("image_root")
            output_root_default = cfg.get("output_root")
        except Exception:
            pass

    ap = argparse.ArgumentParser(description="Mirror images with registry and thumbnails")
    ap.add_argument("--src", required=False, default=image_root_default, help="Source root (scan recursively)")
    ap.add_argument("--dst", required=False, default=output_root_default, help="Destination root to mirror into")
    ap.add_argument("--subdir", required=False, default="assets", help="Subdirectory under dst for mirrored files")
    ap.add_argument("--mode", required=False, default="copy", choices=["copy", "hardlink", "symlink"], help="Copy mode")
    ap.add_argument("--thumbs", action="store_true", help="Generate thumbnails")
    ap.add_argument("--thumb-subdir", required=False, default="thumbnails", help="Thumbnails subdir under dst/subdir")
    ap.add_argument("--registry", required=False, default="image_registry.csv", help="Registry CSV name (under dst/subdir)")
    args = ap.parse_args(argv)

    if not args.src or not args.dst:
        print("❌ --src と --dst を指定してください (path_config.json から既定値取得も可)")
        sys.exit(1)

    src_root = Path(args.src)
    dst_root = Path(args.dst) / args.subdir
    thumbs_root = dst_root / args.thumb_subdir
    registry_path = dst_root / args.registry

    if not src_root.exists():
        print(f"❌ src が存在しません: {src_root}")
        sys.exit(1)

    # 既存レジストリ読み込み
    registry = load_registry(registry_path)

    files = scan_images(src_root)
    processed: List[Dict[str, str]] = []
    updated = 0
    skipped = 0

    for src in files:
        try:
            h = sha256_file(src)
            src_rel = to_rel(src, src_root)
            dst_path = dst_root / src_rel
            dst_rel = to_rel(dst_path, dst_root)

            # 基本メタ
            size_bytes = src.stat().st_size
            width = height = ""
            if PIL_OK:
                try:
                    with Image.open(src) as im:
                        width, height = str(im.size[0]), str(im.size[1])
                except Exception:
                    width = height = ""

            # 既存か判定
            prev = registry.get(h)
            if prev:
                skipped += 1
                processed.append(prev)
                continue

            # コピー/リンク
            copy_or_link(src, dst_path, args.mode)

            # サムネ
            thumb_rel = ""
            if args.thumbs and PIL_OK:
                thumb_path = thumbs_root / src_rel
                thumb_path = thumb_path.with_suffix(".jpg")
                make_thumb(dst_path, thumb_path, max_side=512)
                thumb_rel = to_rel(thumb_path, dst_root)

            row = {
                "sha256": h,
                "src_path": str(src),
                "src_rel": src_rel,
                "dst_path": str(dst_path),
                "dst_rel": dst_rel,
                "size_bytes": str(size_bytes),
                "width": width,
                "height": height,
                "ext": normalize_ext(src.suffix),
                "thumb_rel": thumb_rel,
                "mode": args.mode,
            }
            registry[h] = row
            processed.append(row)
            updated += 1
        except Exception as e:
            print(f"⚠️ 失敗: {src} -> {e}")
            continue

    # 保存
    save_registry(registry_path, list(registry.values()))

    print(f"✅ 完了 files={len(files)} updated={updated} skipped(existed)={skipped}")
    print(f"📄 レジストリ: {registry_path}")
    print(f"📁 出力: {dst_root}")


if __name__ == "__main__":
    main()


