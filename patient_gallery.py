#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
患者ごとの視力・眼圧・レフ値CSVを読み、見やすいHTMLギャラリー(index.html)を生成。
 - サムネイル表示
 - 原画像へのリンク
 - 主な項目（kbn / cdate / 視力 / 眼圧 / レフ値）を表で表示

前提: patient_vision_iop_export.py を実行済みで CSV と thumbnails があること。
"""

import os
import csv
import json
import argparse
import html
from typing import Tuple, List, Dict


def load_paths() -> Tuple[str, str]:
    cfg_path = os.path.join(os.getcwd(), 'path_config.json')
    try:
        with open(cfg_path, 'r', encoding='utf-8') as f:
            cfg = json.load(f)
            return cfg.get('image_root', r'D:\画像'), cfg.get('output_root', r'C:\Users\bnr39\OneDrive\カルテOCR')
    except Exception:
        return r'D:\画像', r'C:\Users\bnr39\OneDrive\カルテOCR'


IMAGE_ROOT, OUTPUT_ROOT = load_paths()


def build_html(pid: str, rows: List[Dict[str, str]]) -> str:
    # 軽いCSSで見やすく
    head = """
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8" />
<title>OCRギャラリー PID={pid}</title>
<style>
  body { font-family: -apple-system, Segoe UI, Roboto, "Hiragino Kaku Gothic ProN", Meiryo, sans-serif; margin: 16px; }
  table { border-collapse: collapse; width: 100%; }
  th, td { border: 1px solid #ddd; padding: 6px 8px; vertical-align: top; }
  th { position: sticky; top: 0; background: #fafafa; z-index: 1; }
  tr:nth-child(even) { background: #fbfbfb; }
  img.thumb { max-width: 220px; height: auto; display: block; }
  .nowrap { white-space: nowrap; }
  .mono { font-family: Consolas, Menlo, monospace; font-size: 12px; }
  .pill { display: inline-block; padding: 2px 6px; border-radius: 10px; background: #eef; }
</style>
</head>
<body>
<h2>OCRギャラリー (PID={pid})</h2>
<table>
  <thead>
    <tr>
      <th>#</th>
      <th>拡大</th>
      <th>サムネイル</th>
      <th>kbn</th>
      <th class="nowrap">cdate</th>
      <th>file</th>
      <th>視力 (Vd/Vs)</th>
      <th>眼圧 (R/L)</th>
      <th>レフ値 (R/L)</th>
    </tr>
  </thead>
  <tbody>
""".replace("{pid}", html.escape(pid))

    body_rows = []
    for idx, r in enumerate(rows, start=1):
        full_path = r.get('full_path', '')
        thumb_rel = r.get('thumb_rel', '')
        thumb_abs = os.path.join(OUTPUT_ROOT, pid, thumb_rel) if thumb_rel else ''
        # HTMLエスケープとfile://リンク
        full_href = ('file:///' + full_path.replace('\\', '/')) if full_path else ''
        full_a = f'<a href="{html.escape(full_href)}" class="mono">open</a>' if full_href else ''
        thumb_href = ('file:///' + thumb_abs.replace('\\', '/')) if thumb_abs else ''
        img_tag = (f'<img class="thumb" src="{html.escape(thumb_href)}" />' if os.path.isfile(thumb_abs) else '')
        vd = [r.get('Vd_naked',''), r.get('Vd_corrected',''), r.get('Vd_TOL','')]
        vs = [r.get('Vs_naked',''), r.get('Vs_corrected',''), r.get('Vs_TOL','')]
        iop = [r.get('IOP_R',''), r.get('IOP_L',''), r.get('IOP_src','')]
        ref_r = [r.get('Ref_R_S',''), r.get('Ref_R_C',''), r.get('Ref_R_Ax','')]
        ref_l = [r.get('Ref_L_S',''), r.get('Ref_L_C',''), r.get('Ref_L_Ax','')]

        def compact(vals: List[str]) -> str:
            vals = [v for v in vals if v]
            return ' / '.join(vals) if vals else ''

        row_html = """
    <tr>
      <td class="mono">{idx}</td>
      <td>{full_a}</td>
      <td>{img_tag}</td>
      <td><span class="pill">{kbn}</span></td>
      <td class="nowrap mono">{cdate}</td>
      <td class="mono">{file}</td>
      <td>{vdv} / {vsv}</td>
      <td>{iopr}/{iopl} <span class=mono>{iops}</span></td>
      <td>R: {refr} / L: {refl}</td>
    </tr>
""".format(
            idx=idx,
            full_a=full_a,
            img_tag=img_tag,
            kbn=html.escape(r.get('kbn','')),
            cdate=html.escape(r.get('cdate','')),
            file=html.escape(r.get('file','')),
            vdv=html.escape(compact(vd)),
            vsv=html.escape(compact(vs)),
            iopr=html.escape(iop[0]),
            iopl=html.escape(iop[1]),
            iops=html.escape(iop[2]),
            refr=html.escape(compact(ref_r)),
            refl=html.escape(compact(ref_l)),
        )
        body_rows.append(row_html)

    tail = """
  </tbody>
</table>
</body>
</html>
"""
    return head + "\n".join(body_rows) + tail


def load_patient_csv(pid: str) -> List[Dict[str, str]]:
    out_dir = os.path.join(OUTPUT_ROOT, pid)
    csv_path = os.path.join(out_dir, f'vision_iop_{pid}.csv')
    rows: List[Dict[str, str]] = []
    if not os.path.isfile(csv_path):
        return rows
    with open(csv_path, 'r', encoding='utf-8-sig', newline='') as f:
        r = csv.DictReader(f)
        for row in r:
            rows.append(row)
    # 並べ替え: cdate, kbn, no
    def sort_key(x: Dict[str,str]):
        return (x.get('cdate',''), x.get('kbn',''), x.get('no',''))
    rows.sort(key=sort_key)
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pid', required=True, help='患者ID (例: 26147)')
    args = ap.parse_args()
    pid = args.pid.strip()

    rows = load_patient_csv(pid)
    if not rows:
        print('❌ CSVが見つからないか空です。先に patient_vision_iop_export.py を実行してください。')
        return
    html_text = build_html(pid, rows)
    out_dir = os.path.join(OUTPUT_ROOT, pid)
    os.makedirs(out_dir, exist_ok=True)
    out_html = os.path.join(out_dir, 'index.html')
    with open(out_html, 'w', encoding='utf-8') as f:
        f.write(html_text)
    print(f'✅ ギャラリー出力: {out_html}')


if __name__ == '__main__':
    main()


