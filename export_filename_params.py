#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
ファイル名からパラメータを抽出し、CSVに階層化して保存

対象: 指定ディレクトリ（例: D:\画像\20000）
出力先: C:\Users\bnr39\OneDrive\serena_mcp_project\memories\Cursor\カルテOCR化\<pidnum>
 - filename_params_<pidnum>.csv（全件）
 - by_kbn\<kbn>.csv（種別ごと）
"""

import os
import re
import csv
import argparse
import urllib.parse
from typing import Dict, List

import json

def load_paths():
    cfg_path = os.path.join(os.getcwd(), 'path_config.json')
    try:
        with open(cfg_path, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
            return cfg.get('image_root', r'D:\画像'), cfg.get('output_root', r'C:\Users\bnr39\OneDrive\カルテOCR')
    except Exception:
        return r'D:\画像', r'C:\Users\bnr39\OneDrive\カルテOCR'

IMAGE_ROOT, OUTPUT_ROOT = load_paths()

PARAM_KEYS_ORDER = [
    'pidnum', 'pkana', 'pname', 'psex', 'pbirth', 'cdate', 'tmstamp',
    'drNo', 'drName', 'kaNo', 'kaName', 'kbn', 'no', 'full_path', 'relative_path', 'cdate_valid'
]

def _read_text_file(path: str) -> str:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception:
        pass
    # フォールバック（Windows日本語環境想定）
    for enc in ('cp932', 'shift_jis', 'euc_jp'):
        try:
            with open(path, 'r', encoding=enc, errors='replace') as f:
                return f.read()
        except Exception:
            continue
    return ''

def load_patient_txt_metadata(target_dir: str, pid_hint: str) -> Dict[str, str]:
    """
    患者フォルダ直下の `&pidnum=<PID>.txt`（または*.txt）からキー値を抽出。
    対象キー: pkana, pname, psex, pbirth
    """
    candidates = []
    try:
        for name in os.listdir(target_dir):
            if name.lower().endswith('.txt'):
                candidates.append(os.path.join(target_dir, name))
    except Exception:
        return {}

    # 優先: 厳密に一致するファイル名
    preferred = [p for p in candidates if os.path.basename(p) == f'&pidnum={pid_hint}.txt']
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
            if k in ('pkana', 'pname', 'psex', 'pbirth'):
                meta[k] = v
    return meta

def merge_patient_metadata(records: List[Dict[str, str]], meta: Dict[str, str]) -> None:
    if not meta:
        return
    for r in records:
        for k in ('pkana', 'pname', 'psex', 'pbirth'):
            if not r.get(k):
                val = meta.get(k)
                if val:
                    r[k] = val

def parse_params_from_filename(path: str) -> Dict[str, str]:
    base = os.path.basename(path)
    decoded = urllib.parse.unquote(base)
    # 先頭の'&'から始まる想定のため、最初の'&'の後ろを抽出
    amp_idx = decoded.find('&')
    query_part = decoded[amp_idx+1:] if amp_idx >= 0 else decoded
    # 拡張子を除外
    lower = query_part.lower()
    for ext in ['.jpg', '.jpeg', '.png', '.tiff', '.bmp']:
        if lower.endswith(ext):
            query_part = query_part[:-(len(ext))]
            break
    params: Dict[str, str] = {}
    for part in query_part.split('&'):
        if '=' in part:
            k, v = part.split('=', 1)
            params[k] = urllib.parse.unquote(v)
    params['full_path'] = path
    return params

def collect_records(target_dir: str) -> List[Dict[str, str]]:
    records: List[Dict[str, str]] = []
    for name in os.listdir(target_dir):
        if not name.lower().endswith(('.jpg', '.jpeg', '.png', '.tiff', '.bmp')):
            continue
        path = os.path.join(target_dir, name)
        try:
            rec = parse_params_from_filename(path)
            # 足りないキーは空文字で補完
            for k in PARAM_KEYS_ORDER:
                rec.setdefault(k, '')
            # relative_path は IMAGE_ROOT に対する相対
            try:
                rec['relative_path'] = os.path.relpath(path, IMAGE_ROOT)
            except Exception:
                rec['relative_path'] = os.path.join(os.path.basename(target_dir), os.path.basename(path))
            # cdate_valid: kbn != 'old' のとき有効
            kbn = (rec.get('kbn') or '').lower()
            rec['cdate_valid'] = '1' if kbn and kbn != 'old' else ('0' if kbn == 'old' else '')
            records.append(rec)
        except Exception:
            continue
    # ソート: cdate, kbn, no
    def sort_key(r: Dict[str, str]):
        return (r.get('cdate', ''), r.get('kbn', ''), r.get('no', ''))
    records.sort(key=sort_key)
    return records

def write_master_csv(records: List[Dict[str, str]], pidnum_hint: str) -> str:
    out_dir = os.path.join(OUTPUT_ROOT, pidnum_hint)
    os.makedirs(out_dir, exist_ok=True)
    out_csv = os.path.join(out_dir, f'filename_params_{pidnum_hint}.csv')
    with open(out_csv, 'w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=PARAM_KEYS_ORDER)
        w.writeheader()
        for r in records:
            w.writerow({k: r.get(k, '') for k in PARAM_KEYS_ORDER})
    # Excel向けにUTF-16タブ区切りも出力
    out_tsv = os.path.join(out_dir, f'filename_params_{pidnum_hint}.tsv')
    with open(out_tsv, 'w', newline='', encoding='utf-16') as f:
        # encoding='utf-16' はBOM付きでExcelが自動判別
        f.write('\t'.join(PARAM_KEYS_ORDER) + '\r\n')
        for r in records:
            row = [str(r.get(k, '')) for k in PARAM_KEYS_ORDER]
            f.write('\t'.join(row) + '\r\n')
    return out_csv

def write_kbn_splits(records: List[Dict[str, str]], pidnum_hint: str) -> List[str]:
    out_paths: List[str] = []
    out_dir = os.path.join(OUTPUT_ROOT, pidnum_hint, 'by_kbn')
    os.makedirs(out_dir, exist_ok=True)
    # kbnごとに分割
    kbn_to_records: Dict[str, List[Dict[str, str]]] = {}
    for r in records:
        kbn = r.get('kbn', 'unknown') or 'unknown'
        kbn_to_records.setdefault(kbn, []).append(r)
    for kbn, recs in kbn_to_records.items():
        p = os.path.join(out_dir, f'{kbn}.csv')
        with open(p, 'w', newline='', encoding='utf-8-sig') as f:
            w = csv.DictWriter(f, fieldnames=PARAM_KEYS_ORDER)
            w.writeheader()
            for r in recs:
                w.writerow({k: r.get(k, '') for k in PARAM_KEYS_ORDER})
        out_paths.append(p)
        # Excel向けにUTF-16タブ区切りも出力
        pt = os.path.join(out_dir, f'{kbn}.tsv')
        with open(pt, 'w', newline='', encoding='utf-16') as f:
            f.write('\t'.join(PARAM_KEYS_ORDER) + '\r\n')
            for r in recs:
                row = [str(r.get(k, '')) for k in PARAM_KEYS_ORDER]
                f.write('\t'.join(row) + '\r\n')
        out_paths.append(pt)
    return out_paths

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dir', required=True, help='対象ディレクトリ (例: D:\\画像\\20000)')
    args = ap.parse_args()
    target_dir = args.dir
    if not os.path.isdir(target_dir):
        print(f'❌ ディレクトリがありません: {target_dir}')
        return
    records = collect_records(target_dir)
    if not records:
        print('❌ 画像ファイルが見つかりませんでした')
        return
    # pidnumはレコードから推測（第一件）
    pid_hint = records[0].get('pidnum', '') or os.path.basename(target_dir)
    # テキストメタデータで補完
    meta = load_patient_txt_metadata(target_dir, pid_hint)
    merge_patient_metadata(records, meta)
    master = write_master_csv(records, pid_hint)
    splits = write_kbn_splits(records, pid_hint)
    print(f'✅ 保存: {master}')
    if splits:
        print(f'✅ kbn分割:')
        for p in splits:
            print(f'  - {p}')

if __name__ == '__main__':
    main()


