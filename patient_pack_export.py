#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
患者ごとにCSVとサムネイル群をエクスポート

- 入力: 画像フォルダ (例: D:\画像\<PID>)
- 出力: OneDrive\カルテOCR\<PID>\
   - filename_params_<PID>.csv（ファイル名からの全パラメータ）
   - thumbnails\<元ファイル名>.jpg（最大幅512pxのサムネイル）

保存先変更に強い設計: path_config.json の output_root を変更すれば一括で反映
"""

import os
import cv2
import csv
import json
import argparse
import urllib.parse
from typing import Dict, List

CFG_PATH = os.path.join(os.getcwd(), 'path_config.json')

def load_paths():
    try:
        with open(CFG_PATH, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
            return cfg.get('image_root', r'D:\画像'), cfg.get('output_root', r'C:\Users\bnr39\OneDrive\カルテOCR')
    except Exception:
        return r'D:\画像', r'C:\Users\bnr39\OneDrive\カルテOCR'

IMAGE_ROOT, OUTPUT_ROOT = load_paths()

PARAM_KEYS = [
    'pidnum','pkana','pname','psex','pbirth','cdate','tmstamp','drNo','drName','kaNo','kaName','kbn','no','full_path','relative_path','cdate_valid'
]

def _read_text_file(path: str) -> str:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception:
        pass
    for enc in ('cp932', 'shift_jis', 'euc_jp'):
        try:
            with open(path, 'r', encoding=enc, errors='replace') as f:
                return f.read()
        except Exception:
            continue
    return ''

def load_patient_txt_metadata(patient_dir: str, pid: str) -> Dict[str, str]:
    candidates: List[str] = []
    try:
        for name in os.listdir(patient_dir):
            if name.lower().endswith('.txt'):
                candidates.append(os.path.join(patient_dir, name))
    except Exception:
        return {}
    preferred = [p for p in candidates if os.path.basename(p) == f'&pidnum={pid}.txt']
    path = preferred[0] if preferred else (candidates[0] if candidates else None)
    if not path:
        return {}
    text = _read_text_file(path)
    if not text:
        return {}
    meta: Dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip('\ufeff').strip()
        if not line or line.startswith('['):
            continue
        if '=' in line:
            k, v = line.split('=', 1)
            k = k.strip()
            v = v.strip()
            if k in ('pkana','pname','psex','pbirth'):
                meta[k] = v
    return meta

def merge_patient_metadata(records: List[Dict[str,str]], meta: Dict[str,str]) -> None:
    if not meta:
        return
    for r in records:
        for k in ('pkana','pname','psex','pbirth'):
            if not r.get(k):
                val = meta.get(k)
                if val:
                    r[k] = val

def parse_params_from_filename(path: str) -> Dict[str, str]:
    base = os.path.basename(path)
    decoded = urllib.parse.unquote(base)
    amp = decoded.find('&')
    query = decoded[amp+1:] if amp >= 0 else decoded
    lower = query.lower()
    for ext in ('.jpg','.jpeg','.png','.tif','.tiff','.bmp'):
        if lower.endswith(ext):
            query = query[:-(len(ext))]
            break
    params: Dict[str,str] = {}
    for part in query.split('&'):
        if '=' in part:
            k, v = part.split('=', 1)
            params[k] = urllib.parse.unquote(v)
    params['full_path'] = path
    return params

def collect_images(patient_dir: str) -> List[str]:
    files: List[str] = []
    for name in os.listdir(patient_dir):
        if name.lower().endswith(('.jpg','.jpeg','.png','.tif','.tiff','.bmp')):
            files.append(os.path.join(patient_dir, name))
    files.sort()
    return files

def write_csv(records: List[Dict[str,str]], out_csv: str) -> None:
    os.makedirs(os.path.dirname(out_csv), exist_ok=True)
    with open(out_csv, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=PARAM_KEYS)
        w.writeheader()
        for r in records:
            row = {k: r.get(k,'') for k in PARAM_KEYS}
            w.writerow(row)
    # Excel向けにUTF-16のTSVも出力
    out_tsv = os.path.splitext(out_csv)[0] + '.tsv'
    with open(out_tsv, 'w', newline='', encoding='utf-16') as f:
        f.write('\t'.join(PARAM_KEYS) + '\r\n')
        for r in records:
            row = [str(r.get(k, '')) for k in PARAM_KEYS]
            f.write('\t'.join(row) + '\r\n')

def save_thumbnail(src_path: str, out_path: str, max_width: int = 512) -> bool:
    try:
        data = None
        # 日本語パス対応
        import numpy as np
        data = np.fromfile(src_path, dtype=np.uint8)
        img = cv2.imdecode(data, cv2.IMREAD_COLOR)
        if img is None:
            return False
        h, w = img.shape[:2]
        if w > max_width:
            scale = max_width / w
            img = cv2.resize(img, (int(w*scale), int(h*scale)), interpolation=cv2.INTER_AREA)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        # 安全保存
        ok, buf = cv2.imencode('.jpg', img, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        if ok:
            with open(out_path, 'wb') as f:
                f.write(buf.tobytes())
            return True
        return False
    except Exception:
        return False

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pid', required=True, help='患者ID（例: 20000）')
    args = ap.parse_args()
    pid = args.pid

    patient_dir = os.path.join(IMAGE_ROOT, pid)
    if not os.path.isdir(patient_dir):
        print(f'❌ 患者フォルダがありません: {patient_dir}')
        return

    images = collect_images(patient_dir)
    if not images:
        print('❌ 画像が見つかりません')
        return

    # CSV
    records: List[Dict[str,str]] = []
    for p in images:
        rec = parse_params_from_filename(p)
        for k in PARAM_KEYS:
            rec.setdefault(k, '')
        # relative_path は IMAGE_ROOT に対する相対
        try:
            rec['relative_path'] = os.path.relpath(p, IMAGE_ROOT)
        except Exception:
            rec['relative_path'] = os.path.join(os.path.basename(patient_dir), os.path.basename(p))
        # cdate_valid: kbn != 'old' のとき有効
        kbn = (rec.get('kbn') or '').lower()
        rec['cdate_valid'] = '1' if kbn and kbn != 'old' else ('0' if kbn == 'old' else '')
        records.append(rec)

    # テキストメタデータ（&pidnum=<PID>.txt）があれば補完
    meta = load_patient_txt_metadata(patient_dir, pid)
    merge_patient_metadata(records, meta)

    out_dir = os.path.join(OUTPUT_ROOT, pid)
    write_csv(records, os.path.join(out_dir, f'filename_params_{pid}.csv'))

    # by_kbn 分割（CSV/TSV）
    by_kbn_dir = os.path.join(out_dir, 'by_kbn')
    os.makedirs(by_kbn_dir, exist_ok=True)
    kbn_groups: Dict[str, List[Dict[str,str]]] = {}
    for r in records:
        key = (r.get('kbn') or 'unknown') or 'unknown'
        kbn_groups.setdefault(key, []).append(r)
    for key, recs in kbn_groups.items():
        p_csv = os.path.join(by_kbn_dir, f'{key}.csv')
        with open(p_csv, 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.DictWriter(f, fieldnames=PARAM_KEYS)
            w.writeheader()
            for r in recs:
                w.writerow({k: r.get(k,'') for k in PARAM_KEYS})
        p_tsv = os.path.join(by_kbn_dir, f'{key}.tsv')
        with open(p_tsv, 'w', newline='', encoding='utf-16') as f:
            f.write('\t'.join(PARAM_KEYS) + '\r\n')
            for r in recs:
                row = [str(r.get(k, '')) for k in PARAM_KEYS]
                f.write('\t'.join(row) + '\r\n')

    # サムネイル
    thumb_dir = os.path.join(out_dir, 'thumbnails')
    for p in images:
        base = os.path.splitext(os.path.basename(p))[0] + '.jpg'
        save_thumbnail(p, os.path.join(thumb_dir, base))

    print(f'✅ 出力: {out_dir}')

if __name__ == '__main__':
    main()


