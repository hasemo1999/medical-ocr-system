import urllib.parse
import os
import sys

# patient_vision_iop_export.pyから関数をインポート
import patient_vision_iop_export as pvie

def check_image_iop(file_url):
    """単一画像の眼圧抽出をチェック"""
    
    # file:// URLをローカルパスに変換
    if file_url.startswith('file:///'):
        local_path = urllib.parse.unquote(file_url[8:])  # file:/// を除去
    else:
        local_path = file_url
    
    print(f"🔍 画像ファイル: {local_path}")
    print("=" * 60)
    
    if not os.path.exists(local_path):
        print(f"❌ ファイルが見つかりません: {local_path}")
        return
    
    try:
        # OCR実行
        print("📖 OCR実行中...")
        # 画像を読み込んでOCR実行（日本語パス対応）
        import cv2
        import numpy as np
        
        # 日本語パスに対応した画像読み込み
        with open(local_path, 'rb') as f:
            img_data = np.frombuffer(f.read(), np.uint8)
        img = cv2.imdecode(img_data, cv2.IMREAD_COLOR)
        
        if img is None:
            print("❌ 画像の読み込みに失敗しました")
            return
        text = pvie.ocr_image_tesseract(img)
        
        if not text.strip():
            print("❌ OCRテキストが空です")
            return
        
        print(f"📄 OCRテキスト（最初の500文字）:")
        print("-" * 40)
        print(text[:500])
        if len(text) > 500:
            print("... (省略)")
        print("-" * 40)
        
        # 眼圧関連の行を抽出
        lines = text.splitlines()
        iop_lines = []
        for i, line in enumerate(lines):
            line_upper = line.upper()
            if any(key in line_upper for key in ['IOP', 'AVG', 'MMHG', 'AT', 'ＮＣＴ', 'NCT', '眼圧']):
                iop_lines.append(f"行{i:3d}: {line.strip()}")
        
        if iop_lines:
            print(f"\n🎯 眼圧関連の行:")
            for line in iop_lines:
                print(f"  {line}")
        else:
            print("\n⚠️ 眼圧関連のキーワードが見つかりません")
        
        # 眼圧抽出実行
        print(f"\n🔢 眼圧抽出結果:")
        iop_result = pvie.extract_iop(text)
        print(f"  IOP_R: {iop_result['IOP_R']}")
        print(f"  IOP_L: {iop_result['IOP_L']}")
        print(f"  方法: {iop_result['IOP_src']}")
        
        # Avg.パターンの詳細チェック
        print(f"\n🔍 Avg.パターンの詳細チェック:")
        normalized = pvie.normalize_text(text)
        for i, line in enumerate(normalized.splitlines()):
            if 'AVG' in line.upper():
                print(f"  行{i}: {line}")
                # 正規表現マッチをテスト
                import re
                m = re.search(r'AVG\.?\s*[:=]?\s*(\d{1,2}\.\d)\s+(\d{1,2}\.\d)', line.upper(), re.IGNORECASE)
                if m:
                    print(f"    ✅ マッチ: {m.group(1)} と {m.group(2)}")
                else:
                    print(f"    ❌ マッチしません")
                    # より詳細なパターンチェック
                    numbers = re.findall(r'\d{1,2}\.\d', line)
                    if numbers:
                        print(f"    💡 見つかった小数: {numbers}")
        
    except Exception as e:
        print(f"❌ エラー: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # URLから画像をチェック
    file_url = "file:///D:/%E7%94%BB%E5%83%8F/26147/&pidnum=26147&pkana=&pname=%E6%9D%89%E7%94%B0%20%E5%AE%88&psex=&pbirth=&cdate=20190204&tmstamp=20190204%20095703&drNo=&drName=&kaNo=&kaName=&kbn=krt2&no=1.jpg"
    check_image_iop(file_url)
