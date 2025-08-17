import re, csv, sys, argparse
from pathlib import Path
import cv2, numpy as np

try:
    import pytesseract
    # Tesseractパスを設定
    import os
    tesseract_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.path.isfile(tesseract_path):
        pytesseract.pytesseract.tesseract_cmd = tesseract_path
    TESS_OK = True
except Exception:
    TESS_OK = False

ENC = "utf-8-sig"

# ---------- 画像読み（日本語パス対応） ----------
def read_img(p: Path):
    arr = np.fromfile(str(p), np.uint8)
    return cv2.imdecode(arr, cv2.IMREAD_COLOR)

# ---------- OCR 基本 ----------
def ocr_data(img, psm=6, lang="jpn+eng"):
    """全体をTSVで読む（小さいと拾えないので自動拡大）"""
    if not TESS_OK: return None, None
    g = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    H, W = g.shape
    if max(H, W) < 1800:
        s = 1800 / max(H, W)
        g = cv2.resize(g, (int(W*s), int(H*s)), cv2.INTER_CUBIC)
    th = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU)[1]
    df = pytesseract.image_to_data(
        th, lang=lang, config=f"--oem 3 --psm {psm}",
        output_type=pytesseract.Output.DATAFRAME
    )
    df = df.dropna(subset=["text"])
    df["text"] = df["text"].astype(str).str.strip()
    df = df[df["text"] != ""]
    return df, th

def ocr_string(img, cfg="--oem 3 --psm 7 -c tessedit_char_whitelist=0123456789.", lang="eng"):
    return pytesseract.image_to_string(img, lang=lang, config=cfg) if TESS_OK else ""

# ---------- デバッグ ----------
def dump_debug(dirp: Path, name: str, im=None, txt=None):
    if not dirp: return
    dirp.mkdir(parents=True, exist_ok=True)
    if im is not None: cv2.imwrite(str(dirp/f"{name}.png"), im)
    if txt is not None: (dirp/f"{name}.txt").write_text(txt, encoding="utf-8")

# ---------- 抽出ロジック ----------
AVG_PAT = re.compile(r"\bA[vu]g\b\.?:?", re.I)  # Avg / Aug / Avg. / Avg:
NUM_PAT = re.compile(r"\b(\d{1,2}\.\d)\b")   # 小数1桁（例 13.7）

def find_avg_line_boxes(df):
    """TSVから 'Avg' を含む行の外接矩形と行テキストを返す（複数あれば全部）"""
    hits = []
    for (blk, par, ln), g in df.groupby(["block_num","par_num","line_num"]):
        line = " ".join(g["text"].tolist())
        if AVG_PAT.search(line):
            x1 = int(min(g["left"])); y1 = int(min(g["top"]))
            x2 = int(max(g["left"]+g["width"])); y2 = int(max(g["top"]+g["height"]))
            hits.append(((x1,y1,x2,y2), line))
    return hits

def extract_avg_from_roi(img, box, debug_dir=None):
    """Avg行の矩形を中心に左右へ広げてROIを作り、同じ行帯の小数×2を取得"""
    x1,y1,x2,y2 = box
    H,W = img.shape[:2]
    # 行の左右に数字が並ぶので、横に広めに＋上下に少し（パディング調整）
    lpad, rpad, upad, dpad = 300, 500, 8, 24
    X1 = max(0, x1 - lpad); Y1 = max(0, y1 - upad)
    X2 = min(W, x2 + rpad); Y2 = min(H, y2 + dpad)
    roi = img[Y1:Y2, X1:X2]
    dump_debug(debug_dir, "avg_roi", im=roi)

    # ROIは数字だけを読みたいので英語数字限定で
    txt = ocr_string(roi, cfg="--oem 3 --psm 6 -c tessedit_char_whitelist=0123456789.", lang="eng")
    dump_debug(debug_dir, "ocr", txt=txt)

    nums = NUM_PAT.findall(txt)
    # ノイズを弾きつつ左→右の2つを採用（多すぎる時は先頭2つ）
    if len(nums) >= 2:
        return nums[0], nums[1]
    return "", ""

def extract_iop_avg_from_image(img, debug_dir=None):
    df, _ = ocr_data(img, psm=6)
    if df is None or len(df)==0: return "",""

    # 1) Avg 行を探す（複数ヒットなら IOP/ mmHg に近いものを優先）
    avg_lines = find_avg_line_boxes(df)
    if not avg_lines:
        # 代替：全テキストから Avg 行を探す（改行崩れ対策）
        alltxt = " ".join(df["text"].tolist())
        if not AVG_PAT.search(alltxt): return "",""
        # Avg単語の近傍を拾えない場合は、全体の数字列から信頼の高い2小数を選ぶ
        whole = " ".join(df["text"].tolist())
        nums = NUM_PAT.findall(whole)
        if len(nums) >= 2: return nums[0], nums[1]
        return "",""

    # 2) IOPアンカー位置（あれば近いAvgを優先）
    iop_candidates = []
    for (blk, par, ln), g in df.groupby(["block_num","par_num","line_num"]):
        line = " ".join(g["text"].tolist())
        if re.search(r"\bIOP\b|\bmmHg\b", line, re.I):
            x1 = int(min(g["left"])); y1 = int(min(g["top"]))
            x2 = int(max(g["left"]+g["width"])); y2 = int(max(g["top"]+g["height"]))
            iop_candidates.append(((x1,y1,x2,y2), line))
    def dist(a, b):
        ax,ay = (a[0]+a[2])//2, (a[1]+a[3])//2
        bx,by = (b[0]+b[2])//2, (b[1]+b[3])//2
        return (ax-bx)**2 + (ay-by)**2

    if iop_candidates:
        # 最も近い Avg 行を採用
        best = None; bestd = 10**12
        for abox,_ in avg_lines:
            d = min(dist(abox, ibox) for ibox,_ in iop_candidates)
            if d < bestd: bestd, best = d, abox
        avg_box = best
    else:
        # 先頭のAvg行
        avg_box = avg_lines[0][0]

    # 3) そのAvg行の帯から小数×2を取得
    r, l = extract_avg_from_roi(img, avg_box, debug_dir=debug_dir)
    return r, l

# ---------- CLI ----------
def process_file(p: Path, out_rows: list, debug=False):
    print(f"🔍 処理中: {p.name}")
    img = read_img(p)
    dbg = (Path("debug")/p.stem) if debug else None
    r, l = extract_iop_avg_from_image(img, debug_dir=dbg)
    out_rows.append({"ソース": p.name, "Avg_R": r, "Avg_L": l})
    print(f"   結果: R={r}, L={l}")

def main():
    ap = argparse.ArgumentParser(description="紙カルテの IOP ステッカーから Avg.（左右）だけ抜く")
    ap.add_argument("patterns", nargs="+", help="画像のパス（ワイルドカード可）")
    ap.add_argument("--out", default="iop_avg.csv")
    ap.add_argument("--debug", action="store_true", help="ROI画像とOCRテキストを保存")
    args = ap.parse_args()

    # デバッグフォルダを作成
    if args.debug:
        debug_dir = Path("debug")
        debug_dir.mkdir(exist_ok=True)
        print(f"📁 デバッグフォルダ: {debug_dir.absolute()}")

    rows=[]
    for pat in args.patterns:
        # 絶対パスの場合はPathlibで直接処理
        if Path(pat).is_absolute():
            from glob import glob
            for path_str in glob(pat):
                p = Path(path_str)
                if p.is_file():
                    process_file(p, rows, debug=args.debug)
        else:
            for p in Path().glob(pat):
                process_file(p, rows, debug=args.debug)

    with open(args.out, "w", encoding=ENC, newline="") as f:
        w = csv.DictWriter(f, fieldnames=["ソース","Avg_R","Avg_L"])
        w.writeheader(); w.writerows(rows)
    print(f"✅ 出力: {args.out}")

if __name__ == "__main__":
    main()
