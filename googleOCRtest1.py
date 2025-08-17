def process_all_with_line_reconstruction():
    """改行を修正して全画像処理"""
    
    results = []
    
    for img_file in image_files:ｎi
        # Google Vision API実行
        text = google_vision_ocr(img_file)
        
        # 改行を修正してデータ抽出
        lines = text.split('\n')
        
        # V.d./V.s.の行を再構築
        for i, line in enumerate(lines):
            if 'V.d.' in line:
                full_vd = reconstruct_vision_line(lines, i)
                # ここから裸眼・矯正を抽出
                
            if 'V.s.' in line:
                full_vs = reconstruct_vision_line(lines, i)
                # ここから裸眼・矯正を抽出
        
        results.append(extracted_data)ｄｄｄｄｄｄｄｄｄｄｄｄｄｄｄｄｄｄｄｄｄｄｄｄｄｄｄｄｄｄｄｄｄｄｄｄｄｄｄｄｄｄｄｄ
    
    return results