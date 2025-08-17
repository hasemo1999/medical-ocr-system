import os
import pandas as pd
from patient_vision_iop_export import load_image_jp, ocr_image_tesseract, extract_iop, parse_filename_params

def debug_iop_accuracy():
    """眼圧抽出の精度をデバッグ"""
    
    # CSVから眼圧データがある紙カルテを取得
    csv_path = r"C:\Users\bnr39\OneDrive\カルテOCR\26147\vision_iop_26147.csv"
    df = pd.read_csv(csv_path, encoding='utf-8-sig')
    
    paper_charts = df[df['file'].str.contains('krt2|old', case=False, na=False)]
    iop_found = paper_charts[(paper_charts['IOP_R'].notna() & (paper_charts['IOP_R'] != '')) | 
                            (paper_charts['IOP_L'].notna() & (paper_charts['IOP_L'] != ''))]
    
    print(f"🔍 眼圧データがある紙カルテ: {len(iop_found)}件")
    print("=" * 60)
    
    for i, (idx, row) in enumerate(iop_found.head(5).iterrows()):
        print(f"\n📁 ファイル {i+1}: {os.path.basename(row['full_path'])}")
        print(f"🔢 抽出結果: IOP_R={row['IOP_R']}, IOP_L={row['IOP_L']}")
        
        try:
            # 元画像からOCR実行
            img = load_image_jp(row['full_path'])
            text = ocr_image_tesseract(img)
            
            # 眼圧関連の行を表示
            lines = text.splitlines()
            print(f"📄 OCRテキスト（眼圧関連行のみ）:")
            
            iop_lines = []
            for j, line in enumerate(lines):
                line_upper = line.upper()
                if any(keyword in line_upper for keyword in ['IOP', 'AVG', 'MMHG', 'AT', 'ＮＣＴ', 'NCT', '眼圧', '右', '左', 'R', 'L']):
                    if line.strip():  # 空行でない場合のみ
                        iop_lines.append(f"  {j:2d}: {line.strip()}")
            
            if iop_lines:
                for line in iop_lines[:10]:  # 最初の10行
                    print(line)
            else:
                print("  ⚠️ 眼圧関連キーワードなし")
            
            # 抽出パターンのテスト
            iop_result = extract_iop(text)
            print(f"📝 抽出方法: {iop_result['IOP_src']}")
            
            # 数値パターンを表示
            import re
            numbers = re.findall(r'\d{1,2}(?:\.\d)?', text)
            if numbers:
                print(f"🔢 見つかった数値: {numbers[:20]}...")  # 最初の20個
            
        except Exception as e:
            print(f"❌ エラー: {e}")
        
        print("-" * 40)

if __name__ == "__main__":
    debug_iop_accuracy()
