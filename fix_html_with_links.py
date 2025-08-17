import csv
import html
import os
import urllib.parse

def create_html_with_clickable_images(csv_path):
    """CSVファイルからクリック可能なサムネイル画像付きHTMLテーブルを作成"""
    
    # CSVを読み込み
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    if not rows:
        return
    
    # HTMLファイルのパス
    html_path = csv_path.replace('.csv', '_clickable.html')
    
    # HTMLを生成
    html_content = f"""<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <title>視力・眼圧データ（クリック可能画像付き）</title>
    <style>
        body {{ font-family: ui-sans-serif, system-ui, "Segoe UI", Meiryo, Arial; margin: 16px; }}
        h1 {{ font-size: 18px; margin: 0 0 8px; }}
        .controls {{ display: flex; gap: 8px; align-items: center; margin: 8px 0; }}
        input[type=text] {{ padding: 6px 8px; border: 1px solid #ccc; border-radius: 6px; min-width: 260px; }}
        .table-wrap {{ height: 80vh; overflow: auto; border: 1px solid #ddd; border-radius: 8px; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ padding: 8px 10px; border-bottom: 1px solid #eee; white-space: nowrap; }}
        thead th {{ position: sticky; top: 0; background: #fff; z-index: 2; border-bottom: 2px solid #ddd; }}
        tbody tr:nth-child(even) {{ background: #fafafa; }}
        .thumbnail {{ width: 80px; height: 60px; object-fit: cover; border: 1px solid #ddd; cursor: pointer; }}
        .thumbnail:hover {{ border-color: #0b69c7; transform: scale(1.05); }}
        .badge {{ display: inline-block; padding: 2px 6px; border: 1px solid #ddd; border-radius: 999px; font-size: 12px; }}
        .image-link {{ text-decoration: none; }}
    </style>
</head>
<body>
    <h1>視力・眼圧データ（患者ID: 26147）- クリックで元画像表示</h1>
    <div class="controls">
        <input id="q" type="text" placeholder="検索（全列対象）" oninput="filterTable()">
        <span class="badge">{len(rows)} 行</span>
        <span style="font-size:12px; color:#666;">※画像クリックで元画像を開きます</span>
    </div>
    <div class="table-wrap">
        <table id="dataTable">
            <thead>
                <tr>
                    <th>サムネイル</th>
                    <th>ID</th>
                    <th>患者名</th>
                    <th>フリガナ</th>
                    <th>性別</th>
                    <th>生年月日</th>
                    <th>検査名</th>
                    <th>検査日</th>
                    <th>IOP_R</th>
                    <th>IOP_L</th>
                    <th>ファイル名</th>
                </tr>
            </thead>
            <tbody>
"""
    
    # 各行のデータを追加
    for row in rows:
        thumb_rel = row.get('thumb_rel', '')
        full_path = row.get('full_path', '')
        
        # サムネイル画像のパス
        if thumb_rel:
            # thumb_relは既に"thumbnails/ファイル名.jpg"の形式
            thumb_full = thumb_rel.replace('\\', '/')
        else:
            thumb_full = ""
        
        # 元画像へのfile://リンク
        if full_path:
            # Windowsパスをfile://URLに変換
            path_for_url = full_path.replace('\\', '/')
            original_url = f"file:///{path_for_url}"
        else:
            original_url = "#"
        
        # 画像タグ（クリック可能）
        if thumb_full and os.path.exists(f"C:/Users/bnr39/OneDrive/カルテOCR/26147/{thumb_full}"):
            img_tag = f'''<a href="{original_url}" class="image-link" target="_blank" title="クリックで元画像を開く">
                         <img src="{thumb_full}" class="thumbnail" alt="サムネイル">
                         </a>'''
        else:
            img_tag = '<span style="color:#999;">画像なし</span>'
        
        # ファイル名を短縮
        file_name = row.get('file', '')
        short_file = os.path.basename(file_name) if file_name else ''
        
        html_content += f"""
                <tr>
                    <td>{img_tag}</td>
                    <td>{html.escape(row.get('ID', ''))}</td>
                    <td>{html.escape(row.get('患者名', ''))}</td>
                    <td>{html.escape(row.get('フリガナ', ''))}</td>
                    <td>{html.escape(row.get('性別', ''))}</td>
                    <td>{html.escape(row.get('生年月日', ''))}</td>
                    <td>{html.escape(row.get('検査名', ''))}</td>
                    <td>{html.escape(row.get('検査日', ''))}</td>
                    <td>{html.escape(row.get('IOP_R', ''))}</td>
                    <td>{html.escape(row.get('IOP_L', ''))}</td>
                    <td title="{html.escape(short_file)}">
                        <a href="{original_url}" target="_blank" style="color:#0b69c7; text-decoration:none;">
                            {html.escape(short_file[:30])}{'...' if len(short_file) > 30 else ''}
                        </a>
                    </td>
                </tr>"""
    
    html_content += """
            </tbody>
        </table>
    </div>
    
    <script>
        function filterTable() {
            const input = document.getElementById('q');
            const filter = input.value.toLowerCase();
            const table = document.getElementById('dataTable');
            const rows = table.getElementsByTagName('tr');
            
            for (let i = 1; i < rows.length; i++) {
                const row = rows[i];
                const text = row.textContent.toLowerCase();
                if (text.includes(filter)) {
                    row.style.display = '';
                } else {
                    row.style.display = 'none';
                }
            }
        }
    </script>
</body>
</html>"""
    
    # HTMLファイルを保存
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"✅ クリック可能画像付きHTML作成: {html_path}")
    return html_path

if __name__ == "__main__":
    csv_file = r"C:\Users\bnr39\OneDrive\カルテOCR\26147\vision_iop_26147.csv"
    create_html_with_clickable_images(csv_file)

