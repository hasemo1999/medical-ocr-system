import csv
import html
import os
import sys
import argparse

def csv_to_sticky_html(csv_path, output_path=None):
    """CSVファイルをスティッキーヘッダー付きHTMLテーブルに変換"""
    
    if not os.path.exists(csv_path):
        print(f"❌ CSVファイルが見つかりません: {csv_path}")
        return
    
    # 出力パスを決定
    if output_path is None:
        output_path = csv_path.replace('.csv', '_sticky.html')
    
    # CSVを読み込み
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        headers = reader.fieldnames
    
    if not rows:
        print(f"❌ CSVファイルが空です: {csv_path}")
        return
    
    # ファイル名を取得
    file_name = os.path.basename(csv_path)
    
    # HTMLを生成
    html_content = f"""<!doctype html>
<html>
<head>
    <meta charset="utf-8">
    <title>{html.escape(file_name)} - スティッキーヘッダー</title>
    <style>
        body {{ 
            font-family: ui-sans-serif, system-ui, "Segoe UI", Meiryo, Arial; 
            margin: 16px; 
            background: #fafafa;
        }}
        h1 {{ 
            font-size: 18px; 
            margin: 0 0 12px; 
            color: #333;
        }}
        .controls {{ 
            display: flex; 
            gap: 12px; 
            align-items: center; 
            margin: 12px 0; 
            padding: 12px; 
            background: white; 
            border-radius: 8px; 
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}
        input[type=text] {{ 
            padding: 8px 12px; 
            border: 1px solid #ddd; 
            border-radius: 6px; 
            min-width: 300px; 
            font-size: 14px;
        }}
        .badge {{ 
            display: inline-block; 
            padding: 4px 8px; 
            background: #e3f2fd; 
            border: 1px solid #90caf9; 
            border-radius: 999px; 
            font-size: 12px; 
            color: #1565c0;
        }}
        .table-wrap {{ 
            height: 75vh; 
            overflow: auto; 
            border: 1px solid #ddd; 
            border-radius: 8px; 
            background: white;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        table {{ 
            border-collapse: collapse; 
            width: 100%; 
        }}
        th, td {{ 
            padding: 10px 12px; 
            border-bottom: 1px solid #eee; 
            text-align: left;
            font-size: 13px;
        }}
        thead th {{ 
            position: sticky; 
            top: 0; 
            background: #f5f5f5; 
            z-index: 10; 
            border-bottom: 2px solid #ddd; 
            font-weight: 600;
            color: #333;
        }}
        tbody tr:nth-child(even) {{ 
            background: #fafafa; 
        }}
        tbody tr:hover {{ 
            background: #e3f2fd; 
        }}
        .numeric {{ 
            text-align: right; 
        }}
        .path-cell {{
            font-family: 'Courier New', monospace;
            font-size: 11px;
            max-width: 200px;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }}
    </style>
</head>
<body>
    <h1>📊 {html.escape(file_name)}</h1>
    <div class="controls">
        <input id="searchInput" type="text" placeholder="🔍 検索（全列対象）" oninput="filterTable()">
        <span class="badge" id="rowCount">{len(rows)} 行</span>
        <span style="font-size:12px; color:#666;">※ヘッダーは固定表示されます</span>
    </div>
    <div class="table-wrap">
        <table id="dataTable">
            <thead>
                <tr>
"""
    
    # ヘッダーを追加
    for header in headers:
        html_content += f'                    <th>{html.escape(header)}</th>\n'
    
    html_content += """                </tr>
            </thead>
            <tbody>
"""
    
    # 各行のデータを追加
    for row in rows:
        html_content += "                <tr>\n"
        for header in headers:
            value = row.get(header, '')
            
            # 数値列の判定
            is_numeric = False
            try:
                float(value.replace(',', ''))
                is_numeric = True
            except:
                pass
            
            # パス列の判定
            is_path = 'path' in header.lower() or 'ファイル' in header
            
            # セルのクラス
            cell_class = ''
            if is_numeric:
                cell_class = 'numeric'
            elif is_path:
                cell_class = 'path-cell'
            
            # file://リンクの生成
            if is_path and value and ('\\' in value or '/' in value):
                if '\\' in value:  # Windowsパス
                    path_for_url = value.replace('\\', '/')
                    file_url = f"file:///{path_for_url}"
                else:
                    file_url = f"file:///{value}"
                cell_content = f'<a href="{file_url}" target="_blank" title="{html.escape(value)}" style="color:#0b69c7;text-decoration:none;">{html.escape(value)}</a>'
            else:
                cell_content = html.escape(value)
            
            html_content += f'                    <td class="{cell_class}">{cell_content}</td>\n'
        html_content += "                </tr>\n"
    
    html_content += """            </tbody>
        </table>
    </div>
    
    <script>
        let allRows = [];
        
        // 初期化時に全行を保存
        window.onload = function() {
            const table = document.getElementById('dataTable');
            const tbody = table.getElementsByTagName('tbody')[0];
            allRows = Array.from(tbody.getElementsByTagName('tr'));
        };
        
        function filterTable() {
            const input = document.getElementById('searchInput');
            const filter = input.value.toLowerCase();
            const table = document.getElementById('dataTable');
            const tbody = table.getElementsByTagName('tbody')[0];
            const rowCount = document.getElementById('rowCount');
            
            let visibleCount = 0;
            
            allRows.forEach(row => {
                const text = row.textContent.toLowerCase();
                if (text.includes(filter)) {
                    row.style.display = '';
                    visibleCount++;
                } else {
                    row.style.display = 'none';
                }
            });
            
            rowCount.textContent = `${visibleCount} 行`;
            if (filter) {
                rowCount.textContent += ` (${allRows.length} 行中)`;
            }
        }
        
        // Enterキーでの検索
        document.getElementById('searchInput').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                filterTable();
            }
        });
    </script>
</body>
</html>"""
    
    # HTMLファイルを保存
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    
    print(f"✅ スティッキーヘッダーHTML作成: {output_path}")
    return output_path

def main():
    parser = argparse.ArgumentParser(description='CSVをスティッキーヘッダー付きHTMLに変換')
    parser.add_argument('csv_file', help='変換するCSVファイル')
    parser.add_argument('-o', '--output', help='出力HTMLファイル名')
    args = parser.parse_args()
    
    csv_to_sticky_html(args.csv_file, args.output)

if __name__ == "__main__":
    if len(sys.argv) == 1:
        # 引数なしの場合、例として26147のCSVを変換
        csv_file = r"C:\Users\bnr39\OneDrive\カルテOCR\26147\vision_iop_26147.csv"
        if os.path.exists(csv_file):
            csv_to_sticky_html(csv_file)
        else:
            print("使用法: python csv_to_sticky_html.py <CSVファイル> [-o 出力ファイル]")
    else:
        main()
