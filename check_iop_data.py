import pandas as pd
import os

def check_iop_data():
    csv_path = r"C:\Users\bnr39\OneDrive\カルテOCR\26147\vision_iop_26147.csv"
    
    if not os.path.exists(csv_path):
        print(f"❌ CSVファイルが見つかりません: {csv_path}")
        return
    
    # CSVを読み込み
    df = pd.read_csv(csv_path, encoding='utf-8-sig')
    
    print(f"🔍 総データ数: {len(df)}")
    
    # 紙カルテのみを抽出
    paper_charts = df[df['file'].str.contains('krt2|old', case=False, na=False)]
    print(f"📄 紙カルテ数: {len(paper_charts)}")
    
    # 眼圧データがある紙カルテ
    iop_found = paper_charts[(paper_charts['IOP_R'].notna() & (paper_charts['IOP_R'] != '')) | 
                            (paper_charts['IOP_L'].notna() & (paper_charts['IOP_L'] != ''))]
    
    print(f"🔢 眼圧データがある紙カルテ: {len(iop_found)}")
    
    if len(iop_found) > 0:
        print("\n✅ 眼圧データが見つかった紙カルテ:")
        for idx, row in iop_found.head(5).iterrows():
            file_name = os.path.basename(row['file'])
            print(f"  {file_name[:50]}...")
            print(f"    IOP_R: {row['IOP_R']}, IOP_L: {row['IOP_L']}")
    else:
        print("\n❌ 眼圧データが見つかりません")
        print("紙カルテの例（最初の3件）:")
        for idx, row in paper_charts.head(3).iterrows():
            file_name = os.path.basename(row['file'])
            print(f"  {file_name[:50]}...")
            print(f"    IOP_R: '{row['IOP_R']}', IOP_L: '{row['IOP_L']}'")

if __name__ == "__main__":
    check_iop_data()
