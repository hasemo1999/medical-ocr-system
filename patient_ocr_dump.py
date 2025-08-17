#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
患者フォルダ配下の画像をOCRし、Markdownに集約保存。IOL(眼内レンズ)らしき情報も簡易抽出してCSV保存。

出力先: path_config.json の output_root 配下
 - ocr_text_<PID>.md
 - iol_data_<PID>.csv (抽出できた行のみ)
"""

import os
import csv
import json
import argparse
from typing import Dict, List, Tuple, Optional

import cv2
import numpy as np
from PIL import Image
import pytesseract
import shutil


def load_paths() -> Tuple[str, str]:
    cfg_path = os.path.join(os.getcwd(), 'path_config.json')
    try:
        with open(cfg_path, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
            return cfg.get('image_root', r'D:\画像'), cfg.get('output_root', r'C:\Users\bnr39\OneDrive\カルテOCR')
    except Exception:
        return r'D:\画像', r'C:\Users\bnr39\OneDrive\カルテOCR'


IMAGE_ROOT, OUTPUT_ROOT = load_paths()


def setup_tesseract_cmd() -> None:
    # 優先順位: 環境変数 / PATH / 既定のインストール先
    candidates = []
    env_cmd = os.environ.get('TESSERACT_CMD')
    if env_cmd:
        candidates.append(env_cmd)
    which = shutil.which('tesseract')
    if which:
        candidates.append(which)
    candidates.extend([
        r"C:\\Program Files\\Tesseract-OCR\\tesseract.exe",
        r"C:\\Program Files (x86)\\Tesseract-OCR\\tesseract.exe",
    ])
    for c in candidates:
        if c and os.path.isfile(c):
            pytesseract.pytesseract.tesseract_cmd = c
            break

setup_tesseract_cmd()


def find_tessdata_and_langs() -> Tuple[Optional[str], str]:
    """tessdata の場所を推定し、利用可能な言語セットを返す。"""
    candidates = [
        os.environ.get('TESSDATA_PREFIX') or '',
        os.path.join(os.getcwd(), 'tessdata'),
        r"C:\\Program Files\\Tesseract-OCR\\tessdata",
        r"C:\\Program Files (x86)\\Tesseract-OCR\\tessdata",
    ]
    for d in candidates:
        if d and os.path.isdir(d):
            files = {fn.lower() for fn in os.listdir(d)}
            has_jpn = 'jpn.traineddata' in files
            has_jpn_vert = 'jpn_vert.traineddata' in files
            has_eng = 'eng.traineddata' in files
            if has_jpn and has_jpn_vert and has_eng:
                return d, 'jpn+jpn_vert+eng'
            if has_jpn and has_eng:
                return d, 'jpn+eng'
            if has_eng:
                return d, 'eng'
    # どれも見つからない場合
    return None, 'eng'


def collect_images(patient_dir: str) -> List[str]:
    images: List[str] = []
    for name in os.listdir(patient_dir):
        if name.lower().endswith(('.jpg', '.jpeg', '.png', '.tif', '.tiff', '.bmp')):
            images.append(os.path.join(patient_dir, name))
    images.sort()
    return images


def load_image_jp(path: str):
    data = np.fromfile(path, dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    return img


def ocr_image_tesseract(img) -> str:
    if img is None:
        return ''
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # 軽い二値化
    try:
        th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    except Exception:
        th = gray
    rgb = cv2.cvtColor(th, cv2.COLOR_GRAY2RGB)
    pil = Image.fromarray(rgb)
    # tessdata パス（存在すれば利用）
    tessdata_dir, lang = find_tessdata_and_langs()
    config = '--psm 6'
    try:
        if tessdata_dir and os.path.isdir(tessdata_dir):
            os.environ['TESSDATA_PREFIX'] = tessdata_dir
            return pytesseract.image_to_string(pil, lang=lang, config=config + f" --tessdata-dir \"{tessdata_dir}\"")
        return pytesseract.image_to_string(pil, lang=lang, config=config)
    except Exception:
        # 最低限のフォールバック
        try:
            return pytesseract.image_to_string(pil, config=config)
        except Exception:
            return ''


def extract_iol_info(text: str) -> Dict[str, str]:
    """非常に簡易なIOL情報抽出。見つからなければ空。"""
    import re
    t = text
    # 正規化: カンマ→ピリオド
    t = t.replace('，', ',').replace(',', '.')
    # 基本パターン
    s = re.search(r'\bS\s*[:=]?\s*([+\-]?\d{1,2}(?:\.\d{1,2})?)', t, re.IGNORECASE)
    c = re.search(r'\bC\s*[:=]?\s*([+\-]?\d{1,2}(?:\.\d{1,2})?)', t, re.IGNORECASE)
    ax = re.search(r'\bA(?:X|XIS)?\s*[:=]?\s*(\d{1,3})', t, re.IGNORECASE)
    # メーカー/製品のキーワード例
    makers = ['Alcon', 'HOYA', 'Bausch', 'ZEISS', 'AMO', 'J&J', 'Santen', 'NIDEK']
    products = ['AcrySof', 'TECNIS', 'Clareon', 'CT', 'SN60', 'SA60', 'ZCB00', 'ZCT']
    maker = next((m for m in makers if m.lower() in t.lower()), '')
    product = next((p for p in products if p.lower() in t.lower()), '')
    # laterality (任意)
    lat = ''
    if re.search(r'\bOD\b|RIGHT|\bR\b|ミギ', t, re.IGNORECASE):
        lat = 'R'
    if re.search(r'\bOS\b|LEFT|\bL\b|ヒダリ', t, re.IGNORECASE):
        # 左優先で上書き
        lat = 'L'
    res: Dict[str, str] = {
        'S': s.group(1) if s else '',
        'C': c.group(1) if c else '',
        'AX': ax.group(1) if ax else '',
        'maker': maker,
        'product': product,
        'eye': lat,
    }
    # いずれかが埋まっていれば採用
    if any(res.values()):
        return res
    return {}


def process_patient(pid: str) -> Tuple[str, int]:
    patient_dir = os.path.join(IMAGE_ROOT, pid)
    if not os.path.isdir(patient_dir):
        return '', 0

    out_dir = os.path.join(OUTPUT_ROOT, pid)
    os.makedirs(out_dir, exist_ok=True)
    md_path = os.path.join(out_dir, f'ocr_text_{pid}.md')
    iol_csv = os.path.join(out_dir, f'iol_data_{pid}.csv')

    images = collect_images(patient_dir)
    if not images:
        return '', 0

    iol_rows: List[Dict[str, str]] = []

    with open(md_path, 'w', encoding='utf-8-sig', newline='') as md:
        md.write(f'## OCR結果 (PID={pid})\n\n')
        for p in images:
            img = load_image_jp(p)
            text = ocr_image_tesseract(img)
            base = os.path.basename(p)
            md.write(f'### {base}\n\n')
            md.write('````\n')
            md.write((text or '').strip() + '\n')
            md.write('````\n\n')

            iol = extract_iol_info(text or '')
            if iol:
                iol_row = {
                    'pidnum': pid,
                    'file': base,
                    **iol,
                }
                iol_rows.append(iol_row)

    if iol_rows:
        with open(iol_csv, 'w', encoding='utf-8-sig', newline='') as f:
            cols = ['pidnum', 'file', 'eye', 'S', 'C', 'AX', 'maker', 'product']
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            for r in iol_rows:
                w.writerow({c: r.get(c, '') for c in cols})

    return md_path, len(iol_rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pid', required=True, help='患者ID (例: 26147) または all')
    args = ap.parse_args()
    pid = args.pid.strip()
    created: List[Tuple[str, int, str]] = []  # (md_path, iol_count, pid)

    if pid.lower() == 'all':
        # 直下のサブフォルダを患者IDとして処理
        for name in sorted(os.listdir(IMAGE_ROOT)):
            pdir = os.path.join(IMAGE_ROOT, name)
            if os.path.isdir(pdir):
                md_path, cnt = process_patient(name)
                if md_path:
                    created.append((md_path, cnt, name))
        # インデックスを作成
        index_md = os.path.join(OUTPUT_ROOT, 'OCR_INDEX.md')
        with open(index_md, 'w', encoding='utf-8-sig', newline='') as f:
            f.write('# OCRテキスト インデックス\n\n')
            for md_path, cnt, pid_val in created:
                rel = os.path.relpath(md_path, OUTPUT_ROOT)
                f.write(f'- {pid_val}: {rel} (IOL {cnt}件)\n')
        print(f'✅ 保存: {index_md} ({len(created)}件)')
    else:
        md_path, cnt = process_patient(pid)
        if not md_path:
            print(f'❌ 患者フォルダがありません: {os.path.join(IMAGE_ROOT, pid)}')
            return
        print(f'✅ 保存: {md_path}')
        if cnt:
            print(f'✅ IOL抽出: {os.path.join(OUTPUT_ROOT, pid, f"iol_data_{pid}.csv")} ({cnt}行)')


if __name__ == '__main__':
    main()


