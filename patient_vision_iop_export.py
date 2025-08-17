#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
患者フォルダ配下の画像をOCRし、視力(裸眼/矯正/TOL)と眼圧(IOP)を抽出してCSV/TSVに出力。

出力先: path_config.json の output_root 配下
 - vision_iop_<PID>.csv / .tsv

注意: OCR品質に依存。手書き・印刷混在に対し、代表的なパターンを網羅。
"""

import os
import re
import csv
import json
import argparse
from typing import Dict, List, Tuple

import cv2
import numpy as np
from PIL import Image
import pytesseract
import shutil
import urllib.parse


def load_paths() -> Tuple[str, str]:
    cfg_path = os.path.join(os.getcwd(), 'path_config.json')
    try:
        with open(cfg_path, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
            return cfg.get('image_root', r'D:\画像'), cfg.get('output_root', r'C:\Users\bnr39\OneDrive\カルテOCR')
    except Exception:
        return r'D:\画像', r'C:\Users\bnr39\OneDrive\カルテOCR'


IMAGE_ROOT, OUTPUT_ROOT = load_paths()


# kbn を実検査名にマッピング
KBN_TO_LABEL = {
    'keikou': 'FAF',
    'angio': 'OCTA',
    'oct2': 'OCT',
    'kensa': 'ハンフリー',
    'gantei2': '眼底カメラ',
    'kowagantei': '眼底カメラ',
    'kowaspe': 'AIMO',
    'kowatopo': 'Topo',
    'kowaslit': 'Slit',
    'kowaetc': 'OCT(旧)',
    'krt2-2': '紙カルテ(新)',
    'old': '紙カルテ(旧)',
    'hoken': '保険証',
}


def setup_tesseract_cmd() -> None:
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
            print(f"✅ Tesseract設定: {c}")
            return
    
    # 見つからない場合は直接指定
    direct_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.path.isfile(direct_path):
        pytesseract.pytesseract.tesseract_cmd = direct_path
        print(f"✅ Tesseract直接設定: {direct_path}")
    else:
        print(f"❌ Tesseractが見つかりません")


def find_tessdata_and_langs() -> Tuple[str, str]:
    # ローカル優先で探索
    candidates = [
        os.path.join(os.getcwd(), 'tessdata'),
        os.environ.get('TESSDATA_PREFIX') or '',
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
            if has_jpn and has_jpn_vert:
                return d, 'jpn+jpn_vert'
            if has_jpn and has_eng:
                return d, 'jpn+eng'
            if has_jpn:
                return d, 'jpn'
            if has_eng:
                return d, 'eng'
    return '', 'eng'


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


def save_thumbnail(img, out_path: str, max_width: int = 320) -> bool:
    try:
        if img is None:
            return False
        h, w = img.shape[:2]
        if w > max_width:
            scale = max_width / w
            img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        ok, buf = cv2.imencode('.jpg', img, [int(cv2.IMWRITE_JPEG_QUALITY), 85])
        if ok:
            with open(out_path, 'wb') as f:
                f.write(buf.tobytes())
            return True
    except Exception:
        return False
    return False


def ocr_image_google_vision(img_path: str) -> str:
    """Google Vision APIでOCR実行"""
    try:
        from google.cloud import vision
        import os
        
        # 認証ファイルの確認
        if not os.path.exists("google_credentials.json"):
            return ""
        
        os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = 'google_credentials.json'
        client = vision.ImageAnnotatorClient()
        
        with open(img_path, 'rb') as image_file:
            content = image_file.read()
        
        image = vision.Image(content=content)
        response = client.text_detection(image=image)
        texts = response.text_annotations
        
        if texts:
            return texts[0].description
        return ""
    except Exception as e:
        print(f"Google Vision APIエラー: {e}")
        return ""

def ocr_image_tesseract(img) -> str:
    if img is None:
        return ''
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    try:
        th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
    except Exception:
        th = gray
    rgb = cv2.cvtColor(th, cv2.COLOR_GRAY2RGB)
    pil = Image.fromarray(rgb)
    tessdata_dir, lang = find_tessdata_and_langs()
    config = '--psm 6'
    if tessdata_dir:
        os.environ['TESSDATA_PREFIX'] = tessdata_dir
    else:
        # 参照が壊れていると失敗するためクリア
        if 'TESSDATA_PREFIX' in os.environ:
            del os.environ['TESSDATA_PREFIX']
    return pytesseract.image_to_string(pil, lang=lang, config=config)


def parse_filename_params(path: str) -> Dict[str, str]:
    base = os.path.basename(path)
    decoded = urllib.parse.unquote(base)
    amp = decoded.find('&')
    query = decoded[amp+1:] if amp >= 0 else decoded
    lower = query.lower()
    for ext in ('.jpg', '.jpeg', '.png', '.tif', '.tiff', '.bmp'):
        if lower.endswith(ext):
            query = query[:-(len(ext))]
            break
    params: Dict[str, str] = {}
    for part in query.split('&'):
        if '=' in part:
            k, v = part.split('=', 1)
            params[k] = urllib.parse.unquote(v)
    return params


def load_patient_txt(pid: str) -> Dict[str, str]:
    txt_path = os.path.join(IMAGE_ROOT, pid, f'&pidnum={pid}.txt')
    if not os.path.isfile(txt_path):
        return {}
    text = ''
    for enc in ('cp932', 'shift_jis', 'utf-8'):  # cp932を最初に試す
        try:
            with open(txt_path, 'r', encoding=enc, errors='replace') as f:
                text = f.read()
                break
        except Exception:
            continue
    meta: Dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip('\ufeff').strip()
        if not line or line.startswith('['):
            continue
        if '=' in line:
            k, v = line.split('=', 1)
            k = k.strip(); v = v.strip()
            if k in ('pname', 'pkana', 'pbirth', 'psex'):  # psexも追加
                meta[k] = v
    return meta

def find_patient_info_from_dir(patient_dir: str) -> Dict[str, str]:
    """同一患者フォルダ内のファイル名から pname/pkana/pbirth/psex を発見。優先: krt2-2 > krt2 > hoken > その他"""
    def rank(kbn: str) -> int:
        k = (kbn or '').lower()
        if k == 'krt2-2':
            return 0
        if k == 'krt2':
            return 1
        if k == 'hoken':
            return 2
        return 3
    
    def normalize_birth_date(date_str: str) -> str:
        """生年月日を正規化（YYYYMMDD → YYYY/MM/DD）"""
        if not date_str:
            return ''
        # 既に / が含まれている場合はそのまま
        if '/' in date_str:
            return date_str
        # YYYYMMDD形式の場合は変換
        if len(date_str) == 8 and date_str.isdigit():
            return f"{date_str[:4]}/{date_str[4:6]}/{date_str[6:8]}"
        return date_str
    
    best: Dict[str, str] = {}
    best_rank = 99
    try:
        for name in os.listdir(patient_dir):
            if not name.lower().endswith(('.jpg', '.jpeg', '.png', '.tif', '.tiff', '.bmp')):
                continue
            p = os.path.join(patient_dir, name)
            prm = parse_filename_params(p)
            if not prm:
                continue
            r = rank(prm.get('kbn', ''))
            # 欲しいキーが含まれるもののみ考慮
            if any(prm.get(k) for k in ('pname', 'pkana', 'pbirth', 'psex')):
                if r < best_rank:
                    best = {k: prm.get(k, '') for k in ('pname', 'pkana', 'pbirth', 'psex')}
                    # 生年月日を正規化
                    if best.get('pbirth'):
                        best['pbirth'] = normalize_birth_date(best['pbirth'])
                    best_rank = r
    except Exception:
        pass
    return best


def normalize_text(t: str) -> str:
    if not t:
        return ''
    t = t.replace('，', ',').replace(',', '.')
    # 全角→半角
    try:
        import unicodedata as ud
        t = ud.normalize('NFKC', t)
    except Exception:
        pass
    return t
def extract_refraction(text: str) -> Dict[str, str]:
    """レフ値 S/C/Ax 抽出（ノイズ抑制のためラベル必須: SPH/CYL/AXIS または S/C/AX）。"""
    t = normalize_text(text)
    # 準備
    r_s = r_c = r_ax = ''
    l_s = l_c = l_ax = ''

    lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
    # 2行ウィンドウで文脈解析（R/L 指示 + ラベル併記を重視）
    for i in range(len(lines)):
        ctx = ' '.join(lines[i:i+2])
        if not ctx:
            continue
        ctx_low = ctx.lower()

        # 右/左の文脈
        is_right = bool(re.search(r'\b(od|right|r)\b', ctx_low)) or ('右' in ctx)
        is_left  = bool(re.search(r'\b(os|left|l)\b', ctx_low)) or ('左' in ctx)

        # 1) SPH/CYL/AXIS のラベルパターン
        m = re.search(r'(?:sph|s)\s*[:=]?\s*([+\-]?\d{1,2}(?:\.\d{1,2})?)\D+(?:cyl|c)\s*[:=]?\s*([+\-]?\d{1,2}(?:\.\d{1,2})?)\D+(?:ax(?:is)?)\s*[:=]?\s*(\d{1,3})', ctx_low, re.IGNORECASE)
        if m:
            s_val, c_val, ax_val = m.group(1), m.group(2), m.group(3)
            # 軸は通常 0-180 を採用
            try:
                ax_i = int(ax_val)
                if not (0 <= ax_i <= 180):
                    ax_val = ''
            except Exception:
                ax_val = ''
            if is_right and not (r_s and r_c and r_ax):
                r_s, r_c, r_ax = s_val, c_val, ax_val
                continue
            if is_left and not (l_s and l_c and l_ax):
                l_s, l_c, l_ax = s_val, c_val, ax_val
                continue

        # 2) ラベル分割型: S:.. C:.. Ax:.. が同一行にない場合、同一コンテキスト内で拾う
        s = re.search(r'\b(?:sph|s)\s*[:=]?\s*([+\-]?\d{1,2}(?:\.\d{1,2})?)', ctx_low)
        c = re.search(r'\b(?:cyl|c)\s*[:=]?\s*([+\-]?\d{1,2}(?:\.\d{1,2})?)', ctx_low)
        ax = re.search(r'\b(?:ax(?:is)?|ax)\s*[:=]?\s*(\d{1,3})', ctx_low)
        if s and c and ax:
            s_val, c_val, ax_val = s.group(1), c.group(1), ax.group(1)
            try:
                ax_i = int(ax_val)
                if not (0 <= ax_i <= 180):
                    ax_val = ''
            except Exception:
                ax_val = ''
            if is_right and not (r_s and r_c and r_ax):
                r_s, r_c, r_ax = s_val, c_val, ax_val
                continue
            if is_left and not (l_s and l_c and l_ax):
                l_s, l_c, l_ax = s_val, c_val, ax_val
                continue

    src = 'printed' if any([r_s, r_c, r_ax, l_s, l_c, l_ax]) else ''
    return {
        'Ref_R_S': r_s, 'Ref_R_C': r_c, 'Ref_R_Ax': r_ax,
        'Ref_L_S': l_s, 'Ref_L_C': l_c, 'Ref_L_Ax': l_ax,
        'Ref_src': src,
    }


def extract_vision(text: str) -> Dict[str, str]:
    t = normalize_text(text)
    # 数値正規化: 01 -> 0.1 の誤認識補正（限定的）
    def fix_num(s: str) -> str:
        if s == '01':
            return '0.1'
        return s
    # ラインごとに探索
    vd_naked = vd_corr = vd_tol = ''
    vs_naked = vs_corr = vs_tol = ''
    for line in t.splitlines():
        if 'V.d.' in line or 'V.s.' in line:
            nums = re.findall(r'([+\-]?\d(?:\.\d)?)', line)
            has_iol = bool(re.search(r'\b[I1l]OL\b|[×xX]\s*IOL', line))
            is_naked = ('裸眼' in line) or ('n.c' in line.lower())
            is_corr = ('矯正' in line) or ('矯' in line)
            # 値の選択: 行内の最初の 0.x/1.x を採用
            val = ''
            for n in nums:
                try:
                    v = float(n)
                    if 0 <= v <= 2.5:
                        val = fix_num(n)
                        break
                except Exception:
                    continue
            if 'V.d.' in line:
                if has_iol:
                    vd_tol = 'IOL'
                if is_naked and val:
                    vd_naked = val
                if is_corr and val:
                    vd_corr = val
                # 種別が取れないが数字はある場合、裸眼へ仮置き
                if not (is_naked or is_corr) and val and not vd_naked:
                    vd_naked = val
            if 'V.s.' in line:
                if has_iol:
                    vs_tol = 'IOL'
                if is_naked and val:
                    vs_naked = val
                if is_corr and val:
                    vs_corr = val
                if not (is_naked or is_corr) and val and not vs_naked:
                    vs_naked = val
    return {
        'Vd_naked': vd_naked,
        'Vd_corrected': vd_corr,
        'Vd_TOL': vd_tol,
        'Vs_naked': vs_naked,
        'Vs_corrected': vs_corr,
        'Vs_TOL': vs_tol,
    }


def extract_iop_avg_from_image(img) -> Dict[str, str]:
    """画像から精密なAvg抽出（TSV座標ベース）"""
    try:
        # TSVデータでOCR実行
        g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        H, W = g.shape
        if max(H, W) < 1800:
            s = 1800 / max(H, W)
            g = cv2.resize(g, (int(W*s), int(H*s)), cv2.INTER_CUBIC)
        th = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU)[1]
        
        df = pytesseract.image_to_data(
            th, lang="jpn+eng", config="--oem 3 --psm 6",
            output_type=pytesseract.Output.DATAFRAME
        )
        df = df.dropna(subset=["text"])
        df["text"] = df["text"].astype(str).str.strip()
        df = df[df["text"] != ""]
        
        if len(df) == 0:
            return {'IOP_R': '', 'IOP_L': '', 'IOP_src': 'no-text'}
        
        # Avg行を探す（Aug誤認識も含む）
        avg_pat = re.compile(r"\bA[vu]g\b\.?:?", re.I)
        avg_lines = []
        for (blk, par, ln), g_group in df.groupby(["block_num","par_num","line_num"]):
            line = " ".join(g_group["text"].tolist())
            if avg_pat.search(line):
                x1 = int(min(g_group["left"])); y1 = int(min(g_group["top"]))
                x2 = int(max(g_group["left"]+g_group["width"])); y2 = int(max(g_group["top"]+g_group["height"]))
                avg_lines.append(((x1,y1,x2,y2), line))
        
        if not avg_lines:
            return {'IOP_R': '', 'IOP_L': '', 'IOP_src': 'no-avg'}
        
        # IOP/mmHgに最も近いAvg行を選択
        iop_candidates = []
        for (blk, par, ln), g_group in df.groupby(["block_num","par_num","line_num"]):
            line = " ".join(g_group["text"].tolist())
            if re.search(r"\bIOP\b|\bmmHg\b", line, re.I):
                x1 = int(min(g_group["left"])); y1 = int(min(g_group["top"]))
                x2 = int(max(g_group["left"]+g_group["width"])); y2 = int(max(g_group["top"]+g_group["height"]))
                iop_candidates.append(((x1,y1,x2,y2), line))
        
        def dist(a, b):
            ax,ay = (a[0]+a[2])//2, (a[1]+a[3])//2
            bx,by = (b[0]+b[2])//2, (b[1]+b[3])//2
            return (ax-bx)**2 + (ay-by)**2
        
        if iop_candidates:
            best = None; bestd = 10**12
            for abox,_ in avg_lines:
                d = min(dist(abox, ibox) for ibox,_ in iop_candidates)
                if d < bestd: bestd, best = d, abox
            avg_box = best
        else:
            avg_box = avg_lines[0][0]
        
        # Avg行周辺のROIから数値抽出
        x1,y1,x2,y2 = avg_box
        lpad, rpad, upad, dpad = 300, 500, 8, 24
        X1 = max(0, x1 - lpad); Y1 = max(0, y1 - upad)
        X2 = min(W, x2 + rpad); Y2 = min(H, y2 + dpad)
        roi = th[Y1:Y2, X1:X2]
        
        # ROIから数値のみ抽出
        roi_text = pytesseract.image_to_string(
            roi, lang="eng", 
            config="--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789."
        )
        
        # 小数1桁パターンで抽出
        nums = re.findall(r"\b(\d{1,2}\.\d)\b", roi_text)
        if len(nums) >= 2:
            r, l = float(nums[0]), float(nums[1])
            if 0 <= r <= 80 and 0 <= l <= 80:
                return {'IOP_R': f'{r:.1f}', 'IOP_L': f'{l:.1f}', 'IOP_src': 'TSV-Avg'}
        
        return {'IOP_R': '', 'IOP_L': '', 'IOP_src': 'no-nums'}
        
    except Exception as e:
        return {'IOP_R': '', 'IOP_L': '', 'IOP_src': f'error-{str(e)[:10]}'}

def extract_iop(text: str) -> Dict[str, str]:
    """従来のテキストベース抽出（フォールバック用）"""
    t = normalize_text(text)
    lines = t.splitlines()
    for i, line in enumerate(lines):
        if any(key in line.upper() for key in ['IOP', 'AVG', 'MMHG', 'AT', 'ＮＣＴ', 'NCT', '眼圧']):
            ctx = ' '.join(lines[max(0, i-2): min(len(lines), i+3)])
            ctx_u = ctx.upper()
            # 縦線パターン（15|12形式、OCR誤認識も含む）
            m = re.search(r'(\d{1,2}(?:\.\d)?)\s*[|Il1]\s*(\d{1,2}(?:\.\d)?)', ctx_u)
            if m:
                r = float(m.group(1)); l = float(m.group(2))
                if 0 <= r <= 80 and 0 <= l <= 80:
                    return {'IOP_R': f'{r:.1f}', 'IOP_L': f'{l:.1f}', 'IOP_src': 'hand-pipe'}
    return {'IOP_R': '', 'IOP_L': '', 'IOP_src': ''}


def write_outputs(pid: str, rows: List[Dict[str, str]]):
    out_dir = os.path.join(OUTPUT_ROOT, pid)
    os.makedirs(out_dir, exist_ok=True)
    out_csv = os.path.join(out_dir, f'vision_iop_{pid}.csv')
    out_tsv = os.path.join(out_dir, f'vision_iop_{pid}.tsv')
    cols = [
        'ID', '患者名', 'フリガナ', '性別', '生年月日', 'file', '検査名', '検査日', 'full_path', 'thumb_rel',
        'IOP_R', 'IOP_L'
    ]
    from datetime import datetime
    # CSV出力（ファイルロック時は別名で保存）
    try:
        with open(out_csv, 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            for r in rows:
                w.writerow({c: r.get(c, '') for c in cols})
    except PermissionError:
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        out_csv = os.path.join(out_dir, f'vision_iop_{pid}_{ts}.csv')
        with open(out_csv, 'w', encoding='utf-8-sig', newline='') as f:
            w = csv.DictWriter(f, fieldnames=cols)
            w.writeheader()
            for r in rows:
                w.writerow({c: r.get(c, '') for c in cols})
    
    # TSV出力（ファイルロック時は別名で保存）
    try:
        with open(out_tsv, 'w', encoding='utf-16', newline='') as f:
            f.write('\t'.join(cols) + '\r\n')
            for r in rows:
                f.write('\t'.join([str(r.get(c, '')) for c in cols]) + '\r\n')
    except PermissionError:
        ts = datetime.now().strftime('%Y%m%d_%H%M%S')
        out_tsv = os.path.join(out_dir, f'vision_iop_{pid}_{ts}.tsv')
        with open(out_tsv, 'w', encoding='utf-16', newline='') as f:
            f.write('\t'.join(cols) + '\r\n')
            for r in rows:
                f.write('\t'.join([str(r.get(c, '')) for c in cols]) + '\r\n')
    return out_csv, out_tsv


def process_patient(pid: str) -> Tuple[str, str, int]:
    patient_dir = os.path.join(IMAGE_ROOT, pid)
    if not os.path.isdir(patient_dir):
        return '', '', 0
    rows: List[Dict[str, str]] = []
    thumb_dir = os.path.join(OUTPUT_ROOT, pid, 'thumbnails')
    # テキスト/ファイル名から患者情報（患者フォルダ優先取得 + 行ごと上書き可）
    folder_guess = find_patient_info_from_dir(patient_dir)
    txt_meta = load_patient_txt(pid)
    for p in collect_images(patient_dir):
        img = load_image_jp(p)
        text = ocr_image_tesseract(img)
        params = parse_filename_params(p)
        vision = extract_vision(text)
        
        # 眼圧抽出は一時停止（精度が低いため）
        # TODO: 将来的にAvg抽出の精度を改善してから再有効化
        iop = {'IOP_R': '', 'IOP_L': '', 'IOP_src': 'disabled'}
        base = os.path.basename(p)
        thumb_name = os.path.splitext(base)[0] + '.jpg'
        thumb_rel = os.path.join('thumbnails', thumb_name)
        # サムネ生成
        save_thumbnail(img, os.path.join(thumb_dir, thumb_name))
        # 表示用ID
        row_id = f"{params.get('kbn','')}_{params.get('cdate','')}_{params.get('no','')}"
        # 検査名ラベル
        kbn_val = (params.get('kbn', '') or '').lower()
        exam_label = KBN_TO_LABEL.get(kbn_val, kbn_val)
        # 患者情報（ファイル名優先）
        pname = params.get('pname') or folder_guess.get('pname', '') or txt_meta.get('pname', '')
        pkana = params.get('pkana') or folder_guess.get('pkana', '') or txt_meta.get('pkana', '')
        psex = params.get('psex') or folder_guess.get('psex', '') or txt_meta.get('psex', '')
        
        # 生年月日の取得（このファイル → フォルダ推定 → テキスト）
        pbirth_raw = params.get('pbirth', '')
        if pbirth_raw and len(pbirth_raw) == 8 and pbirth_raw.isdigit():
            # ファイル名にYYYYMMDD形式がある場合
            pbirth = f"{pbirth_raw[:4]}/{pbirth_raw[4:6]}/{pbirth_raw[6:8]}"
        elif pbirth_raw:
            # ファイル名に他の形式がある場合
            pbirth = pbirth_raw
        else:
            # ファイル名にない場合は、フォルダ推定またはテキストファイルから
            pbirth = folder_guess.get('pbirth', '') or txt_meta.get('pbirth', '')
        rows.append({
            'ID': params.get('pidnum', pid),
            '患者名': pname,
            'フリガナ': pkana,
            '性別': psex,
            '生年月日': pbirth,
            'file': base,
            '検査名': exam_label,
            '検査日': params.get('cdate', ''),
            'full_path': p,
            'thumb_rel': thumb_rel,
            'IOP_R': iop.get('IOP_R', ''),
            'IOP_L': iop.get('IOP_L', ''),
        })
    out_csv, out_tsv = write_outputs(pid, rows)
    return out_csv, out_tsv, len(rows)


def main():
    setup_tesseract_cmd()
    ap = argparse.ArgumentParser()
    ap.add_argument('--pid', required=True, help='患者ID (例: 26147)')
    args = ap.parse_args()
    pid = args.pid.strip()
    out_csv, out_tsv, n = process_patient(pid)
    if not n:
        print(f'❌ 画像が見つかりません: {os.path.join(IMAGE_ROOT, pid)}')
        return
    print(f'✅ 出力: {out_csv}')
    print(f'✅ 出力: {out_tsv}')


if __name__ == '__main__':
    main()


