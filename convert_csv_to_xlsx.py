#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
UTF-8(BOM) の CSV または UTF-16 の TSV を Excel 用の XLSX に変換

使い方:
  python convert_csv_to_xlsx.py "C:\\Users\\bnr39\\OneDrive\\カルテOCR\\26147\\vision_iop_26147.csv"
  python convert_csv_to_xlsx.py "C:\\Users\\bnr39\\OneDrive\\カルテOCR\\26147\\vision_iop_26147.tsv"
"""

import os
import sys
import csv
from pathlib import Path

try:
	from openpyxl import Workbook
	OPENPYXL_OK = True
except Exception:
	OPENPYXL_OK = False


def convert(input_path: str) -> str:
	if not OPENPYXL_OK:
		raise RuntimeError("openpyxl が見つかりません。pip install openpyxl")
	p = Path(input_path)
	if not p.exists():
		raise FileNotFoundError(str(p))
	ext = p.suffix.lower()
	# 出力パス
	out_xlsx = p.with_suffix('.xlsx')
	wb = Workbook()
	ws = wb.active
	ws.title = p.stem[:31]
	# 読み込み
	if ext == '.tsv':
		with p.open('r', encoding='utf-16', newline='') as f:
			r = csv.reader(f, delimiter='\t')
			for row in r:
				ws.append(row)
	else:
		with p.open('r', encoding='utf-8-sig', newline='') as f:
			r = csv.reader(f)
			for row in r:
				ws.append(row)
	# 列幅をざっくり自動調整
	for col in ws.columns:
		max_len = 0
		col_letter = col[0].column_letter
		for cell in col:
			v = '' if cell.value is None else str(cell.value)
			max_len = max(max_len, len(v))
		ws.column_dimensions[col_letter].width = min(60, max(10, max_len + 2))
	wb.save(out_xlsx)
	return str(out_xlsx)


def main():
	if len(sys.argv) < 2:
		print('Usage: python convert_csv_to_xlsx.py <csv_or_tsv_path>')
		sys.exit(1)
	inp = sys.argv[1]
	out = convert(inp)
	print(f'✅ XLSX: {out}')


if __name__ == '__main__':
	main()



