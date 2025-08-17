import os
import sys
from patient_vision_iop_export import extract_iop, normalize_text, safe_ocr

def debug_iop_for_patient(pid: str):
    """患者の眼圧抽出をデバッグ"""
    from pathlib import Path
    from patient_vision_iop_export import IMAGE_ROOT
    
    patient_dir = Path(IMAGE_ROOT) / pid
    if not patient_dir.exists():
        print(f"❌ 患者フォルダが見つかりません: {patient_dir}")
        return
    
    print(f"🔍 患者 {pid} の眼圧抽出デバッグ")
    print("=" * 50)
    
    # 画像ファイルを探す
    image_files = []
    for ext in ['*.jpg', '*.jpeg', '*.png', '*.tif', '*.tiff']:
        image_files.extend(patient_dir.glob(ext))
    
    iop_found = []
    
    for img_path in image_files[:10]:  # 最初の10枚をチェック
        try:
            # OCR実行
            text = safe_ocr(str(img_path))
            if not text.strip():
                continue
            
            # 眼圧抽出
            iop_result = extract_iop(text)
            
            if iop_result['IOP_R'] or iop_result['IOP_L']:
                print(f"\n📁 ファイル: {img_path.name}")
                print(f"🔢 IOP_R: {iop_result['IOP_R']}, IOP_L: {iop_result['IOP_L']}")
                print(f"📝 方法: {iop_result['IOP_src']}")
                
                # OCRテキストの関連部分を表示
                lines = text.splitlines()
                for i, line in enumerate(lines):
                    if any(key in line.upper() for key in ['IOP', 'AVG', 'MMHG', 'AT', 'ＮＣＴ', 'NCT', '眼圧']):
                        print(f"📄 関連行 {i}: {line.strip()}")
                        # 前後の行も表示
                        for j in range(max(0, i-2), min(len(lines), i+3)):
                            if j != i:
                                print(f"   {j}: {lines[j].strip()}")
                        break
                
                iop_found.append({
                    'file': img_path.name,
                    'iop_r': iop_result['IOP_R'],
                    'iop_l': iop_result['IOP_L'],
                    'src': iop_result['IOP_src']
                })
                print("-" * 30)
        
        except Exception as e:
            print(f"❌ エラー {img_path.name}: {e}")
    
    print(f"\n📊 眼圧データが見つかった画像: {len(iop_found)}枚")
    
    if iop_found:
        print("\n🔍 見つかった眼圧データ一覧:")
        for item in iop_found:
            print(f"  {item['file']}: R={item['iop_r']}, L={item['iop_l']} ({item['src']})")
    
    return iop_found

if __name__ == "__main__":
    if len(sys.argv) > 1:
        pid = sys.argv[1]
    else:
        pid = "26147"  # デフォルト
    
    debug_iop_for_patient(pid)
