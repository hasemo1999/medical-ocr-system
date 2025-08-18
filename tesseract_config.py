# Tesseract自動設定ファイル
# このファイルは自動生成されました

import pytesseract

# Tesseractパス設定
TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

print(f"Tesseract自動設定: {TESSERACT_PATH}")
