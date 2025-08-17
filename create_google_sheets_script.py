import csv
import os
import sys
import json

def create_google_sheets_auto_freeze_script(csv_path):
    """Google SheetsでCSVインポート時に自動でヘッダーを固定するApps Scriptコードを生成"""
    
    if not os.path.exists(csv_path):
        print(f"❌ CSVファイルが見つかりません: {csv_path}")
        return
    
    # ベースファイル名
    base_name = os.path.splitext(os.path.basename(csv_path))[0]
    script_dir = os.path.dirname(csv_path)
    
    # Apps Scriptコード
    apps_script_code = f'''/**
 * Google Sheets用 自動ヘッダー固定スクリプト
 * CSVインポート後に実行してください
 */

function autoFreezeHeaderAndFormat() {{
  const sheet = SpreadsheetApp.getActiveSheet();
  
  // 1行目（ヘッダー）を固定
  sheet.setFrozenRows(1);
  
  // ヘッダー行のスタイル設定
  const headerRange = sheet.getRange(1, 1, 1, sheet.getLastColumn());
  headerRange.setBackground('#4285f4');  // Google Blue
  headerRange.setFontColor('#ffffff');
  headerRange.setFontWeight('bold');
  headerRange.setFontSize(11);
  
  // 列幅の自動調整
  sheet.autoResizeColumns(1, sheet.getLastColumn());
  
  // データ範囲に枠線を追加
  const dataRange = sheet.getDataRange();
  dataRange.setBorder(true, true, true, true, true, true, '#e0e0e0', SpreadsheetApp.BorderStyle.SOLID);
  
  // 交互の行に色を付ける
  const dataRows = sheet.getRange(2, 1, sheet.getLastRow() - 1, sheet.getLastColumn());
  dataRows.applyRowBanding(SpreadsheetApp.BandingTheme.LIGHT_GREY);
  
  // フィルターを追加
  dataRange.createFilter();
  
  SpreadsheetApp.getUi().alert('✅ ヘッダー固定とフォーマットが完了しました！');
}}

function onOpen() {{
  // メニューに追加
  const ui = SpreadsheetApp.getUi();
  ui.createMenu('📊 CSV Tools')
      .addItem('🔒 ヘッダー固定', 'autoFreezeHeaderAndFormat')
      .addToUi();
}}
'''

    # Apps Scriptファイルを保存
    script_path = os.path.join(script_dir, f"{base_name}_google_apps_script.js")
    with open(script_path, 'w', encoding='utf-8') as f:
        f.write(apps_script_code)
    
    # 手順書を作成
    instructions = f'''Google Spreadsheet でCSVを自動ヘッダー固定にする手順:

=== 方法1: Apps Script使用（推奨） ===

1. Google Drive でCSVファイルをアップロード
2. 右クリック → "アプリで開く" → "Google スプレッドシート"
3. スプレッドシートが開いたら：
   - [拡張機能] → [Apps Script]
   - 既存のコードを削除
   - 生成された '{base_name}_google_apps_script.js' の内容をコピペ
   - [保存] → [実行] ボタンクリック
   - 権限を許可
4. スプレッドシートに戻る
5. [📊 CSV Tools] メニュー → [🔒 ヘッダー固定]

=== 方法2: 手動設定 ===

1. CSVをGoogle Sheetsで開く
2. 1行目を選択
3. [表示] → [固定] → [1行]
4. [データ] → [フィルタを作成]

=== 方法3: URL経由（最も簡単） ===

Google SheetsのURL末尾に以下を追加:
&fvid=0&frid=1

例: https://docs.google.com/spreadsheets/d/YOUR_ID/edit#gid=0&fvid=0&frid=1

=== 生成ファイル ===
- Apps Script: {script_path}
- 手順書: この説明

注意: Google Sheetsは最初の行を自動でヘッダーとして認識することが多いです。
'''

    instructions_path = os.path.join(script_dir, f"{base_name}_google_sheets_instructions.txt")
    with open(instructions_path, 'w', encoding='utf-8') as f:
        f.write(instructions)
    
    # Google Sheets用の最適化されたCSVも作成
    optimized_csv_path = os.path.join(script_dir, f"{base_name}_for_google_sheets.csv")
    
    # UTF-8（BOM無し）でCSVを作成（Google Sheets推奨）
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        content = f.read()
    
    with open(optimized_csv_path, 'w', encoding='utf-8', newline='') as f:
        f.write(content)
    
    print(f"✅ Google Apps Script作成: {script_path}")
    print(f"✅ Google Sheets用CSV作成: {optimized_csv_path}")
    print(f"✅ 手順書作成: {instructions_path}")
    print()
    print("🚀 クイックスタート:")
    print("1. Google DriveにCSVをアップロード")
    print("2. Google Sheetsで開く")
    print("3. Apps Scriptコードを実行")
    print("4. 自動でヘッダー固定完了！")
    
    return script_path, optimized_csv_path, instructions_path

def create_google_sheets_bookmarklet():
    """Google Sheetsでワンクリックヘッダー固定するブックマークレット"""
    
    bookmarklet_js = '''javascript:(function(){{
var sheet = SpreadsheetApp.getActiveSheet();
sheet.setFrozenRows(1);
sheet.getRange(1,1,1,sheet.getLastColumn()).setBackground('#4285f4').setFontColor('#ffffff').setFontWeight('bold');
sheet.autoResizeColumns(1,sheet.getLastColumn());
sheet.getDataRange().createFilter();
alert('ヘッダー固定完了！');
}})();'''
    
    print("🔖 ブックマークレット（実験的）:")
    print("以下をブックマークに保存して、Google Sheetsで実行:")
    print(bookmarklet_js)

def main():
    if len(sys.argv) < 2:
        # 引数なしの場合、例として26147のCSVを処理
        csv_file = r"C:\Users\bnr39\OneDrive\カルテOCR\26147\vision_iop_26147.csv"
        if os.path.exists(csv_file):
            create_google_sheets_auto_freeze_script(csv_file)
        else:
            print("使用法: python create_google_sheets_script.py <CSVファイル>")
    else:
        csv_file = sys.argv[1]
        create_google_sheets_auto_freeze_script(csv_file)

if __name__ == "__main__":
    main()
