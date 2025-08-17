import os
import glob
from patient_vision_iop_export import parse_filename_params, extract_iop, ocr_image_tesseract, load_image_jp

def test_iop_extraction():
    """患者26147の紙カルテから眼圧抽出をテスト"""
    
    patient_dir = r"D:\画像\26147"
    if not os.path.exists(patient_dir):
        print(f"❌ 患者フォルダが見つかりません: {patient_dir}")
        return
    
    # 画像ファイルを探す
    image_files = []
    for ext in ['*.jpg', '*.jpeg', '*.png', '*.tif', '*.tiff']:
        image_files.extend(glob.glob(os.path.join(patient_dir, ext)))
    
    print(f"🔍 患者26147の画像ファイル数: {len(image_files)}")
    
    paper_charts = []
    exam_images = []
    
    for img_path in image_files:
        params = parse_filename_params(img_path)
        kbn = (params.get('kbn', '') or '').lower()
        
        if kbn in ['krt2', 'krt2-2', 'old']:
            paper_charts.append(img_path)
        else:
            exam_images.append(img_path)
    
    print(f"📄 紙カルテ数: {len(paper_charts)}")
    print(f"🔬 検査画像数: {len(exam_images)}")
    
    if not paper_charts:
        print("❌ 紙カルテが見つかりません")
        return
    
    print("\n🔍 紙カルテから眼圧抽出テスト:")
    print("=" * 50)
    
    for i, chart_path in enumerate(paper_charts[:5]):  # 最初の5枚をテスト
        print(f"\n📁 ファイル {i+1}: {os.path.basename(chart_path)}")
        
        try:
            # OCR実行
            img = load_image_jp(chart_path)
            text = ocr_image_tesseract(img)
            
            if not text.strip():
                print("  ❌ OCRテキストが空")
                continue
            
            # 眼圧抽出
            iop_result = extract_iop(text)
            
            print(f"  🔢 IOP_R: {iop_result['IOP_R']}")
            print(f"  🔢 IOP_L: {iop_result['IOP_L']}")
            print(f"  📝 方法: {iop_result['IOP_src']}")
            
            # OCRテキストの一部を表示
            lines = text.splitlines()[:10]  # 最初の10行
            print("  📄 OCRテキスト（抜粋）:")
            for j, line in enumerate(lines):
                if line.strip():
                    print(f"    {j:2d}: {line.strip()}")
            
            # 眼圧関連キーワードをチェック
            iop_keywords = ['IOP', 'AVG', 'MMHG', 'AT', 'ＮＣＴ', 'NCT', '眼圧', '右', '左', 'R', 'L']
            found_keywords = []
            for line in lines:
                for keyword in iop_keywords:
                    if keyword in line.upper():
                        found_keywords.append(f"{keyword}({line.strip()})")
            
            if found_keywords:
                print("  🎯 眼圧関連キーワード:")
                for kw in found_keywords[:3]:  # 最初の3つ
                    print(f"    {kw}")
            else:
                print("  ⚠️ 眼圧関連キーワードなし")
                
        except Exception as e:
            print(f"  ❌ エラー: {e}")
        
        print("-" * 30)

if __name__ == "__main__":
    test_iop_extraction()
