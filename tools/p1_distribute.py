# -*- coding: utf-8 -*-
"""
master.csv の full_text を再スキャンで埋め直すツール
- Patients/{...}/raw の画像をQR再読取（検出強化 + 文字化け修復）
- CSVの full_text が空の行だけ更新
- --also-fix-id-date を付けると、patient_id / visit_date が空欄の行も埋める
使い方:
  ドライラン: python p1_distribute.py --patients-root ".\Patients" --master-csv ".\Patients\master.csv"
  本適用 　: python p1_distribute.py --patients-root ".\Patients" --master-csv ".\Patients\master.csv" --apply
"""

import argparse, csv, os, re, sys
from pathlib import Path
from datetime import datetime
from dateutil import parser as dtparser
from urllib.parse import parse_qsl, unquote_plus
import unicodedata

import numpy as np
import cv2
from PIL import Image, ExifTags

IMG_EXTS = {".jpg", ".jpeg", ".png", ".heic", ".tif", ".tiff", ".webp"}
PID_KEYS  = ["pidnum","pid","patient_id","patient","patid","mrn","id","no"]
DATE_KEYS = ["cdate","date","visit","visit_date","day","surg","surgery_date","dt","tm","tmstamp"]

def normalize_date(s: str):
    if not s: return None
    s = s.strip()
    if re.fullmatch(r"20\d{6}", s):  # 20250809
        return f"{s[0:4]}-{s[4:6]}-{s[6:8]}"
    try:
        return dtparser.parse(s).date().isoformat()
    except Exception:
        return None

def repair_mojibake(s: str) -> str:
    if not s: return s
    t = unquote_plus(s)
    if any('\u3040' <= ch <= '\u30ff' or '\u4e00' <= ch <= '\u9fff' for ch in t):
        return unicodedata.normalize("NFC", t)
    raw = s.encode("latin-1", errors="ignore")
    for enc in ("cp932", "shift_jis", "euc_jp"):
        try:
            fixed = raw.decode(enc)
            if any('\u3040' <= ch <= '\u30ff' or '\u4e00' <= ch <= '\u9fff' for ch in fixed):
                return unicodedata.normalize("NFC", fixed)
        except Exception:
            pass
    return unicodedata.normalize("NFC", t)

def parse_qr_payload(text: str):
    qs = text.lstrip('?&')
    kv = {k.lower(): v for k, v in parse_qsl(qs, keep_blank_values=True)}
    pid = None
    for k in PID_KEYS:
        if k in kv and kv[k] and kv[k].lower() not in PID_KEYS:
            pid = kv[k]; break
    date = None
    for k in DATE_KEYS:
        if k in kv and kv[k]:
            raw = kv[k].split()[0]
            date = normalize_date(raw)
            if date: break
    if not (pid and date):
        for pat in [
            re.compile(r"(?P<pid>[0-9]{3,})[_\-\.](?P<date>20[0-9]{2}[01][0-9][0-3][0-9])"),
            re.compile(r"(?:PID|ID)[:=]?\s*(?P<pid>[0-9A-Za-z_-]+).*?(?:DATE|Date|cdate)[:=]?\s*(?P<date>[0-9]{4}[-/\.][0-9]{1,2}[-/\.][0-9]{1,2})", re.I|re.S),
        ]:
            m = pat.search(text)
            if m:
                pid = pid or m.group("pid")
                date = date or normalize_date(m.group("date"))
                break
    return pid, date

def load_gray_for_qr(path: Path):
    try:
        data = np.fromfile(str(path), dtype=np.uint8)
        img = cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)
        if img is not None: return img
    except Exception:
        pass
    try:
        pil = Image.open(path).convert("L")
        arr = np.array(pil)
        if arr.ndim == 2: return arr
        return cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY)
    except Exception:
        return None

def detect_qr(path: Path):
    img = load_gray_for_qr(path)
    if img is None: return None
    det = cv2.QRCodeDetector()
    variants=[]
    for scale in (1.0,1.5,2.0):
        base = img if scale==1.0 else cv2.resize(img,(int(img.shape[1]*scale),int(img.shape[0]*scale)),interpolation=cv2.INTER_CUBIC)
        variants.append(base)
        variants.append(cv2.adaptiveThreshold(base,255,cv2.ADAPTIVE_THRESH_GAUSSIAN_C,cv2.THRESH_BINARY,31,5))
        variants.append(cv2.bitwise_not(base))
        k = cv2.getStructuringElement(cv2.MORPH_RECT,(3,3))
        variants.append(cv2.morphologyEx(base, cv2.MORPH_CLOSE, k, iterations=1))
    for work in variants:
        data, pts, _ = det.detectAndDecode(work)
        if data: return data
        try:
            retval, decoded_info, _, _ = det.detectAndDecodeMulti(work)
            if retval and decoded_info:
                for d in decoded_info:
                    if d: return d
        except Exception:
            pass
    return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--patients-root", required=True)
    ap.add_argument("--master-csv", required=True)
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--also-fix-id-date", action="store_true", help="patient_id / visit_date が空ならQRから補完")
    ap.add_argument("--fill-from-path", action="store_true", help="source_relpath から patient_id / visit_date を補完")
    ap.add_argument("--pid-from-filename", action="store_true", help="ファイル名の数値から patient_id を補完")
    ap.add_argument("--override-csv", type=str, default="", help="上書き用CSV (source_relpath,patient_id,visit_date)")
    ap.add_argument("--mark-note", action="store_true", help="補完根拠を note 列に記録")
    args = ap.parse_args()

    root = Path(args.patients_root)
    csv_path = Path(args.master_csv)
    if not csv_path.exists():
        print(f"[ERR] master.csv not found: {csv_path}"); sys.exit(1)

    # CSV読み込み
    rows=[]
    with csv_path.open("r",encoding="utf-8") as f:
        r = csv.DictReader(f)
        header = r.fieldnames or []
        for row in r: rows.append(row)
    # ヘッダに不足列があれば追加
    required_columns = ["full_text", "patient_id", "visit_date"]
    for col in required_columns:
        if col not in header:
            header.append(col)
    if args.mark_note and "note" not in header:
        header.append("note")

    def normalize_relpath(rel: str) -> str:
        if not rel:
            return ""
        p = rel.replace("/", "\\")
        while "\\\\" in p:
            p = p.replace("\\\\", "\\")
        if p.startswith(".\\"):
            p = p[2:]
        return p

    def append_note(row: dict, tag: str):
        if not args.mark_note:
            return
        note_val = (row.get("note") or "").strip()
        if note_val:
            if tag not in note_val:
                row["note"] = note_val + "," + tag
        else:
            row["note"] = tag

    def parse_from_path(rel: str):
        # 例: 12345\\20250809\\raw\\IMG_0001.JPG から pid=12345, date=2025-08-09
        try:
            import re as _re
            pid = None
            date = None
            m = _re.search(r"(?P<pid>\\d{3,})[\\/](?P<date>20\\d{6})[\\/]", rel)
            if m:
                pid = m.group("pid")
                raw = m.group("date")
                date = f"{raw[0:4]}-{raw[4:6]}-{raw[6:8]}"
            return pid, date
        except Exception:
            return None, None

    def pid_from_filename(rel: str):
        try:
            import re as _re
            base = Path(rel).name
            m = _re.search(r"(\\d{3,})", base)
            return m.group(1) if m else None
        except Exception:
            return None

    # full_text 空の行を対象
    targets = [row for row in rows if not (row.get("full_text") or "").strip()]
    print(f"[INFO] full_text 空の行: {len(targets)} / 総行数: {len(rows)}")

    updated = 0
    for row in targets:
        rel = row.get("source_relpath","")
        if not rel: continue
        fpath = root / rel
        if not fpath.exists():
            print(f"[MISS] {rel} : ファイルが見つからない"); continue
        if fpath.suffix.lower() not in IMG_EXTS:
            continue

        qr = detect_qr(fpath)
        if not qr:
            # 見つからないときはスキップ
            continue
        qr_fixed = repair_mojibake(qr)
        row["full_text"] = qr_fixed
        if args.also_fix_id_date:
            pid, date = parse_qr_payload(qr_fixed)
            if not (row.get("patient_id") or "").strip() and pid:
                row["patient_id"] = pid
            if not (row.get("visit_date") or "").strip() and date:
                row["visit_date"] = date
        updated += 1
        print(f"[SET] {rel} full_text を更新")

    # 既存 full_text からの補完（全行対象）
    if args.also_fix_id_date:
        for row in rows:
            full_text_value = (row.get("full_text") or "").strip()
            if not full_text_value:
                continue
            pid, date = parse_qr_payload(full_text_value)
            changed = False
            if not (row.get("patient_id") or "").strip() and pid:
                row["patient_id"] = pid
                changed = True
            if not (row.get("visit_date") or "").strip() and date:
                row["visit_date"] = date
                changed = True
            if changed:
                updated += 1
                print(f"[SET-TEXT] {row.get('source_relpath','(no path)')} 欠損ID/日付を補完")
                append_note(row, "full_text")

    # override CSV による補完
    if args.override_csv:
        ov_path = Path(args.override_csv)
        if ov_path.exists():
            with ov_path.open("r", encoding="utf-8") as f:
                rdr = csv.DictReader(f)
                override_rows = list(rdr)
            key_to_row = {}
            for orow in override_rows:
                key = normalize_relpath(orow.get("source_relpath", ""))
                if key:
                    key_to_row[key] = orow
            for row in rows:
                key = normalize_relpath(row.get("source_relpath", ""))
                if not key:
                    continue
                orow = key_to_row.get(key)
                if not orow:
                    continue
                changed = False
                if not (row.get("patient_id") or "").strip() and (orow.get("patient_id") or "").strip():
                    row["patient_id"] = orow["patient_id"].strip()
                    changed = True
                if not (row.get("visit_date") or "").strip() and (orow.get("visit_date") or "").strip():
                    row["visit_date"] = normalize_date(orow["visit_date"].strip()) or orow["visit_date"].strip()
                    changed = True
                if changed:
                    updated += 1
                    print(f"[SET-OVR] {row.get('source_relpath','(no path)')} override で補完")
                    append_note(row, "override")

    # パスからの補完
    if args.fill_from_path:
        for row in rows:
            rel = normalize_relpath(row.get("source_relpath", ""))
            if not rel:
                continue
            pid_guess, date_guess = parse_from_path(rel)
            changed = False
            if not (row.get("patient_id") or "").strip() and pid_guess:
                row["patient_id"] = pid_guess
                changed = True
            if not (row.get("visit_date") or "").strip() and date_guess:
                row["visit_date"] = date_guess
                changed = True
            if changed:
                updated += 1
                print(f"[SET-PATH] {row.get('source_relpath','(no path)')} パスから補完")
                append_note(row, "path")

    # ファイル名からの patient_id 補完
    if args.pid_from_filename:
        for row in rows:
            if (row.get("patient_id") or "").strip():
                continue
            rel = normalize_relpath(row.get("source_relpath", ""))
            if not rel:
                continue
            pid_guess = pid_from_filename(rel)
            if pid_guess:
                row["patient_id"] = pid_guess
                updated += 1
                print(f"[SET-FNAME] {row.get('source_relpath','(no path)')} ファイル名から補完")
                append_note(row, "filename")

    # 書き戻し
    if args.apply and updated:
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=header)
            w.writeheader(); w.writerows(rows)
        print(f"[WRITE] master.csv を更新: {updated} 行")
    else:
        print(f"[DRYRUN] 更新候補: {updated} 行（--apply で反映）")

    print("Done.")

if __name__ == "__main__":
    main()