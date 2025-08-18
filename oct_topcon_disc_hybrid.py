import os, re, csv, sys, argparse, glob
from pathlib import Path
import cv2, numpy as np

# Tesseract自動設定
try:
    import tesseract_config  # 自動生成された設定ファイル
    import pytesseract
    TESS_OK=True
except ImportError:
    try:
        import pytesseract
        # フォールバック: 手動パス設定
        pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
        TESS_OK=True
    except Exception:
        TESS_OK=False

ENC="utf-8-sig"

# ---------- 共通 ----------
def read_img(p: Path):
    arr=np.fromfile(str(p), np.uint8); return cv2.imdecode(arr, cv2.IMREAD_COLOR)

def norm(t:str)->str:
    t=t or ""
    return (t.replace("\u3000"," ").replace("㎛","um").replace("μm","um").replace("µm","um")
             .replace("㎟","mm2").replace("mm²","mm2").replace("㎣","mm3").replace("mm³","mm3")
             .replace("：",":").replace("，",",").replace("—","-").replace("−","-"))

def ocr_df(img, psm=6, lang="jpn+eng"):
    if not TESS_OK: return None, None
    g=cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    H,W=g.shape
    
    # 複数解像度で試行（精度向上）
    best_df = None
    best_score = 0
    
    for target_size in [1800, 2400, 3000]:  # 複数解像度試行
        if max(H,W) < target_size:
            s = target_size/max(H,W)
            g_resized = cv2.resize(g, (int(W*s), int(H*s)), cv2.INTER_CUBIC)
        else:
            g_resized = g.copy()
        
        # 画像前処理強化
        # 1. コントラスト調整
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
        g_enhanced = clahe.apply(g_resized)
        
        # 2. ガウシアンフィルタでノイズ除去
        g_filtered = cv2.GaussianBlur(g_enhanced, (3,3), 0)
        
        # 3. シャープニング
        kernel = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
        g_sharp = cv2.filter2D(g_filtered, -1, kernel)
        
        # 4. 二値化
        th = cv2.threshold(g_sharp, 0, 255, cv2.THRESH_BINARY+cv2.THRESH_OTSU)[1]
        
        # 複数PSMモードで試行
        for psm_mode in [psm, 6, 8, 13]:  # 指定PSM + フォールバック
            try:
                df = pytesseract.image_to_data(th, lang=lang, config=f"--oem 3 --psm {psm_mode}",
                                             output_type=pytesseract.Output.DATAFRAME)
                df = df.dropna(subset=["text"])
                df["text"] = df["text"].astype(str).str.strip()
                df = df[df["text"]!=""]
                
                # 品質スコア計算（数値の多さと信頼度で評価）
                score = len(df) * df['conf'].mean() if len(df) > 0 and 'conf' in df.columns else 0
                
                if score > best_score:
                    best_df = df
                    best_score = score
                    best_th = th
                    
            except Exception:
                continue
                
        # 最初の解像度で十分な結果が得られた場合は終了
        if best_score > 1000:  # 閾値は調整可能
            break
    
    # フォールバック処理
    if best_df is not None:
        return best_df, best_th if 'best_th' in locals() else th
    else:
        # 基本処理（従来方式）
        if max(H,W)<1800:
            s=1800/max(H,W); g=cv2.resize(g,(int(W*s),int(H*s)), cv2.INTER_CUBIC)
        th=cv2.threshold(g,0,255,cv2.THRESH_BINARY+cv2.THRESH_OTSU)[1]
        df=pytesseract.image_to_data(th, lang=lang, config=f"--oem 3 --psm {psm}",
                                     output_type=pytesseract.Output.DATAFRAME)
        df=df.dropna(subset=["text"])
        df["text"]=df["text"].astype(str).str.strip()
        df=df[df["text"]!=""]
        return df, th

def bbox_of_line(df, pattern):
    for (blk,par,ln), g in df.groupby(["block_num","par_num","line_num"]):
        line=" ".join(g["text"].tolist())
        if re.search(pattern, line, re.I):
            x1=int(min(g["left"])); y1=int(min(g["top"]))
            x2=int(max(g["left"]+g["width"])); y2=int(max(g["top"]+g["height"]))
            return (x1,y1,x2,y2), line
    return None, ""

def crop_rect(img, x1,y1,x2,y2, pad=(0,0,0,0)):
    l,t,r,b = pad
    H,W = img.shape[:2]
    x1=max(0,x1-l); y1=max(0,y1-t); x2=min(W,x2+r); y2=min(H,y2+b)
    return img[y1:y2, x1:x2]

def debug_dump(dirp: Path, name: str, im=None, txt=None):
    if not dirp: return
    dirp.mkdir(parents=True, exist_ok=True)
    if im is not None: cv2.imwrite(str(dirp/f"{name}.png"), im)
    if txt is not None: (dirp/f"{name}.txt").write_text(txt, encoding="utf-8")

def numeric_tokens(df):
    out=[]
    for _,r in df.iterrows():
        s=str(r["text"])
        if re.fullmatch(r"\d{1,3}(?:\.\d+)?", s):
            out.append((int(r["left"]), int(r["top"]), int(r["width"]), int(r["height"]), s))
    return out

def pick_row_values(df_roi, y, band=35, expect=2):  # band調整: 30→35
    """同じY帯にある数値をx昇順で返す（左=OD, 右=OS）"""
    nums = []
    for x,yy,w,h,s in numeric_tokens(df_roi):
        cy = yy + h/2
        if abs(cy - y) <= band:
            nums.append((x, s))
    nums.sort(key=lambda z:z[0])
    vals=[v for _,v in nums]
    return (vals[:expect] + [""]*expect)[:expect]

def keep_in(v, lo, hi):
    try:
        x=float(v); 
        return v if (lo is None or x>=lo) and (hi is None or x<=hi) else ""
    except: return ""

# ---------- 抽出（OCT Disc Report） ----------
def extract_ss(df) -> tuple[str,str]:
    """Signal Strength抽出の改良版：複数パターン・範囲チェック強化"""
    
    # 複数のパターンを試行
    patterns = [
        r"TopQ\s*Image\s*Quality",
        r"Image\s*Quality", 
        r"Signal\s*Strength",
        r"SS",
        r"Quality\s*Index",
        r"QI"
    ]
    
    for pattern in patterns:
        for (blk,par,ln), g in df.groupby(["block_num","par_num","line_num"]):
            line=" ".join(g["text"].tolist())
            if re.search(pattern, line, re.I):
                # 数値抽出パターンも強化
                nums = []
                # 2-3桁の数値を抽出
                for match in re.finditer(r"(\d{2,3})", line):
                    val = int(match.group(1))
                    # Signal Strengthの妥当範囲（20-100）
                    if 20 <= val <= 100:
                        nums.append(match.group(1))
                
                if len(nums) >= 2: 
                    return nums[0], nums[1]
                elif len(nums) == 1:
                    # 1つしかない場合は、近隣行も検索
                    nearby_nums = _search_nearby_ss(df, blk, par, ln)
                    if nearby_nums:
                        return nums[0], nearby_nums
    
    return "",""

def _search_nearby_ss(df, target_blk: int, target_par: int, target_ln: int) -> str:
    """近隣行からSignal Strengthの追加値を検索"""
    for (blk,par,ln), g in df.groupby(["block_num","par_num","line_num"]):
        # 同じブロック・段落で近い行番号
        if blk == target_blk and par == target_par and abs(ln - target_ln) <= 2:
            line=" ".join(g["text"].tolist())
            for match in re.finditer(r"(\d{2,3})", line):
                val = int(match.group(1))
                if 20 <= val <= 100:
                    return match.group(1)
    return ""

def extract_rnfl_table_v3(img, df, dbg=None):
    """
    v3方式: 「Average thickness RNFL(μm)」の直下テーブル。
    行ラベル( Total / Superior / Inferior )のY座標を拾い、その帯の数値を左右で取得。
    """
    out={"RNFL_Total_OD":"","RNFL_Total_OS":"",
         "RNFL_S_OD":"","RNFL_S_OS":"",
         "RNFL_I_OD":"","RNFL_I_OS":""}

    box, line = bbox_of_line(df, r"Average\s*thickness\s*RNFL")
    if not box: return out

    # テーブル領域（左右2列ぶん＋余白）を広めに切り出し
    x1,y1,x2,y2 = box
    roi = crop_rect(img, x1, y2, x2+650, y2+280, pad=(100,10,100,10))  # 範囲拡大
    debug_dump(dbg, "avg_roi", im=roi)

    # ROI 内で再TSV
    dfr, _ = ocr_df(roi, psm=6)
    if dfr is None or len(dfr)==0: return out

    def y_of(label_regex):
        for (b,p,ln), g in dfr.groupby(["block_num","par_num","line_num"]):
            line=" ".join(g["text"].tolist())
            if re.search(label_regex, line, re.I):
                yy=int(min(g["top"])); hh=int(max(g["top"]+g["height"]))-yy
                return yy + hh/2
        return None

    rows = {
        "Total": y_of(r"Total\s*Thickness|Total|平均|Average|TOTAL"),  # パターン拡張
        "Superior": y_of(r"Superior|上|S|Sup|SUPERIOR|上方"),  # パターン大幅拡張
        "Inferior": y_of(r"Inferior|下|I|Inf|INFERIOR|下方"),  # パターン大幅拡張
    }
    
    for key, yy in rows.items():
        if yy is None: continue
        vals = pick_row_values(dfr, yy, band=35, expect=2)  # band調整: 30→35
        if key=="Total":
            out["RNFL_Total_OD"], out["RNFL_Total_OS"] = vals
        elif key=="Superior":
            out["RNFL_S_OD"], out["RNFL_S_OS"] = vals
        elif key=="Inferior":
            out["RNFL_I_OD"], out["RNFL_I_OS"] = vals
    
    # 超強化フォールバック：行クラスタリング + Total OS特別処理
    if not out["RNFL_Total_OD"] or not out["RNFL_S_OD"] or not out["RNFL_I_OD"] or not out["RNFL_Total_OS"]:
        # 全数値を Y座標でクラスタリング
        all_tokens = numeric_tokens(dfr)
        rnfl_candidates = []
        
        for x, y, w, h, val_str in all_tokens:
            try:
                val = float(val_str)
                if 30 <= val <= 200:  # RNFL妥当範囲
                    cy = y + h/2
                    rnfl_candidates.append((x, cy, val_str))
            except:
                continue
        
        if len(rnfl_candidates) >= 2:  # 最低条件を緩和（4→2）
            # Y座標でクラスタリング
            rnfl_candidates.sort(key=lambda z: z[1])  # Y座標順
            clusters = []
            band = 45  # クラスタ帯幅を拡大（40→45）
            
            for x, cy, val_str in rnfl_candidates:
                if not clusters or abs(clusters[-1]["y"] - cy) > band:
                    clusters.append({"y": cy, "vals": [(x, val_str)]})
                else:
                    clusters[-1]["vals"].append((x, val_str))
            
            # 各クラスタから左右の値を抽出
            def extract_lr(cluster_vals):
                cluster_vals.sort(key=lambda z: z[0])  # X座標順
                return (cluster_vals[0][1] if len(cluster_vals) > 0 else "", 
                       cluster_vals[1][1] if len(cluster_vals) > 1 else "")
            
            # 上から順にTotal, Superior, Inferiorと仮定（改良版）
            if len(clusters) >= 1:
                od, os = extract_lr(clusters[0]["vals"])
                # Total ODが未設定の場合のみ設定
                if not out["RNFL_Total_OD"]:
                    out["RNFL_Total_OD"] = keep_in(od, 60, 150)
                # Total OSは積極的に設定（精度向上）
                if not out["RNFL_Total_OS"] or not out["RNFL_Total_OS"].strip():
                    total_os_candidate = keep_in(os, 60, 150)
                    if total_os_candidate:  # 妥当な値があれば設定
                        out["RNFL_Total_OS"] = total_os_candidate
                
            if len(clusters) >= 2 and not out["RNFL_S_OD"]:
                od, os = extract_lr(clusters[1]["vals"])
                out["RNFL_S_OD"] = keep_in(od, 30, 200)
                out["RNFL_S_OS"] = keep_in(os, 30, 200)
                
            if len(clusters) >= 3 and not out["RNFL_I_OD"]:
                od, os = extract_lr(clusters[2]["vals"])
                out["RNFL_I_OD"] = keep_in(od, 30, 200)
                out["RNFL_I_OS"] = keep_in(os, 30, 200)
            
            # Total OS超強化検索（複数戦略）
            if not out["RNFL_Total_OS"] or not out["RNFL_Total_OS"].strip():
                total_os_found = False
                
                # 戦略1: 最高値ベース（80-150範囲）
                max_os_candidates = []
                for cluster in clusters:
                    _, os_val = extract_lr(cluster["vals"])
                    if os_val:
                        try:
                            val = float(os_val)
                            if 80 <= val <= 150:  # Total RNFLの典型範囲
                                max_os_candidates.append((val, os_val))
                        except:
                            continue
                
                if max_os_candidates:
                    max_os_candidates.sort(key=lambda x: x[0], reverse=True)
                    out["RNFL_Total_OS"] = max_os_candidates[0][1]
                    total_os_found = True
                
                # 戦略2: 単独値検索（クラスタに関係なく）
                if not total_os_found:
                    for x, cy, val_str in rnfl_candidates:
                        try:
                            val = float(val_str)
                            if 90 <= val <= 140:  # より厳格なTotal範囲
                                # X座標が右側（OS側）にあるかチェック
                                if x > 200:  # 経験的閾値
                                    out["RNFL_Total_OS"] = val_str
                                    total_os_found = True
                                    break
                        except:
                            continue

    # 妥当域フィルタ（μm）
    for k in list(out.keys()):
        out[k] = keep_in(out[k], 30, 200)
    
    # デバッグ情報出力
    debug_info = f"ラベルベース検出:\n"
    for key, yy in rows.items():
        debug_info += f"{key}: Y={yy}\n"
    
    debug_info += f"\n抽出結果:\n"
    debug_info += f"Total: OD={out['RNFL_Total_OD']}, OS={out['RNFL_Total_OS']}\n"
    debug_info += f"Superior: OD={out['RNFL_S_OD']}, OS={out['RNFL_S_OS']}\n"
    debug_info += f"Inferior: OD={out['RNFL_I_OD']}, OS={out['RNFL_I_OS']}\n"
    
    # クラスタリング情報も追加
    if 'clusters' in locals():
        debug_info += f"\nクラスタリング結果:\n"
        for i, cluster in enumerate(clusters):
            vals_str = [f"({x},{val})" for x, val in cluster["vals"]]
            debug_info += f"クラスタ{i+1} (Y={cluster['y']:.1f}): {vals_str}\n"
    
    debug_dump(dbg, "rnfl_debug", txt=debug_info)
    
    return out

def extract_disc_topography_v4(img, df, dbg=None):
    """
    v4改良版: 「Disc Topography」下の表から数値クラスタリングでRim/Disc/Cup を左右で取得。
    """
    out={"RimArea_OD_mm2":"","RimArea_OS_mm2":"",
         "DiscArea_OD_mm2":"","DiscArea_OS_mm2":"",
         "CupVolume_OD_mm3":"","CupVolume_OS_mm3":""}

    box,_=bbox_of_line(df, r"Disc\s*Topography")
    if not box: return out
    x1,y1,x2,y2=box

    # 表全体（左右の数値列まで）をさらに広めに - pad拡大
    roi = crop_rect(img, x1-60, y2, x2+740, y2+320, pad=(130,10,130,10))  # 範囲大幅拡大
    debug_dump(dbg, "disc_roi", im=roi)

    # 数字だけTSV（小数優先）
    dfn, _ = ocr_df(roi, psm=6)  # 文字制限なし
    if dfn is None or len(dfn)==0: return out

    def _norm_num(s: str) -> str:
        s=s.replace(",",".")
        if s.startswith("."): s="0"+s
        return s

    # 小数候補（0.00〜4.00）
    toks=[]
    for _,r in dfn.iterrows():
        s=_norm_num(str(r["text"]))
        if re.fullmatch(r"\d?\.\d{1,2}", s) or re.fullmatch(r"\d{1}\.\d{1,2}", s) or re.fullmatch(r"\d{1,2}\.\d{1,2}", s):
            try:
                v=float(s)
                if 0.0<=v<=4.0:
                    cx=r["left"]+r["width"]/2; cy=r["top"]+r["height"]/2
                    toks.append((cx,cy,"%.2f"%v))
            except: pass
    if not toks: return out

    # 行クラスタリング（慎重な改良版）
    toks.sort(key=lambda z:z[1])
    rows=[]; band=35  # 元の35pxに戻す
    for cx,cy,s in toks:
        if not rows or abs(rows[-1]["y"]-cy)>band:
            rows.append({"y":cy,"vals":[(cx,s)]})
        else:
            rows[-1]["vals"].append((cx,s))

    # 行数は6行に戻す（安定性重視）
    rows=rows[:6]
    
    # フィルタリングは行わない（元の動作を維持）

    def two_enhanced(vals):
        """安定版：基本機能+軽微な改良のみ"""
        vals=sorted(vals, key=lambda z:z[0])  # X座標順
        arr=[v for _,v in vals]
        
        # 基本的には元のtwo()と同じ動作
        return (arr[0] if len(arr)>0 else "", arr[1] if len(arr)>1 else "")

    if len(rows)>=1:  # Rim Area
        od,os=two_enhanced(rows[0]["vals"])
        out["RimArea_OD_mm2"]=od; out["RimArea_OS_mm2"]=os
    if len(rows)>=2:  # Disc Area
        od,os=two_enhanced(rows[1]["vals"])
        out["DiscArea_OD_mm2"]=od; out["DiscArea_OS_mm2"]=os
    
    # Cup Volume: より柔軟な行位置特定
    # 1. キーワードベースでCup行を探す
    cup_found = False
    for i, row in enumerate(rows):
        # 各行の値をチェックして、Cup Volumeらしい値（0.0-1.5範囲）があるか
        for _, val_str in row["vals"]:
            try:
                val = float(val_str)
                if 0.0 <= val <= 1.5:  # Cup Volumeの妥当範囲
                    od, os = two_enhanced(row["vals"])
                    out["CupVolume_OD_mm3"] = keep_in(od, 0.0, 1.5)
                    out["CupVolume_OS_mm3"] = keep_in(os, 0.0, 1.5)
                    cup_found = True
                    break
            except:
                continue
        if cup_found:
            break
    
    # 2. キーワードベースで見つからなければ、従来の位置ベース（3-6行目を試行）
    if not cup_found:
        for cup_row_idx in [2, 3, 4, 5]:  # 元の3-6行目に戻す
            if len(rows) > cup_row_idx and not out["CupVolume_OD_mm3"]:
                od,os=two_enhanced(rows[cup_row_idx]["vals"])
                # Cupは 0.00〜1.50 の妥当域でフィルタ
                try:
                    od_val = float(od) if od else None
                    os_val = float(os) if os else None
                    if (od_val and 0.0 <= od_val <= 1.5) or (os_val and 0.0 <= os_val <= 1.5):
                        out["CupVolume_OD_mm3"] = od if od_val and 0.0 <= od_val <= 1.5 else ""
                        out["CupVolume_OS_mm3"] = os if os_val and 0.0 <= os_val <= 1.5 else ""
                        break
                except:
                    continue
    
    # デバッグ情報
    debug_info = f"検出された行数: {len(rows)}\n"
    for i, row in enumerate(rows):
        debug_info += f"行{i+1}: {[v for _,v in row['vals']]}\n"
    debug_dump(dbg, "disc_rows", txt=debug_info)
    
    return out

def extract_quad_optional_v3(img, df, dbg=None):
    """
    v3改良版: T/N を円グラフ付近から拾う（複数位置・PSM・範囲拡大）
    """
    out={"RNFL_T_OD":"","RNFL_T_OS":"","RNFL_N_OD":"","RNFL_N_OS":""}
    box, _ = bbox_of_line(df, r"Average\s*thickness\s*RNFL")
    if not box: return out
    x1,y1,x2,y2 = box
    H,W = img.shape[:2]
    
    # 複数の円グラフ位置候補を試行（改良）
    left_candidates = [
        crop_rect(img, x1-120, y2+10, x1+200, y2+220, pad=(30,0,30,0)),  # 拡大版1
        crop_rect(img, x1-80, y2+20, x1+160, y2+190, pad=(20,0,20,0)),   # 従来版
        crop_rect(img, x1-100, y2+30, x1+180, y2+200, pad=(25,0,25,0)),  # 中間版
    ]
    
    right_candidates = [
        crop_rect(img, x2-250, y2+10, x2+100, y2+220, pad=(30,0,30,0)),  # 拡大版1
        crop_rect(img, x2-200, y2+20, x2+60,  y2+190, pad=(20,0,20,0)),  # 従来版
        crop_rect(img, x2-220, y2+30, x2+80,  y2+200, pad=(25,0,25,0)),  # 中間版
    ]
    
    # デバッグ用に最大版を保存
    debug_dump(dbg, "quad_left_enhanced",  im=left_candidates[0])
    debug_dump(dbg, "quad_right_enhanced", im=right_candidates[0])
    debug_dump(dbg, "quad_left",  im=left_candidates[1])  # 従来版も保持
    debug_dump(dbg, "quad_right", im=right_candidates[1])
    
    def extract_best_nums(candidates, side_name):
        best_result = ("", "")
        best_score = 0
        debug_info = f"{side_name}側検出結果:\n"
        
        for i, im in enumerate(candidates):
            # 複数PSMモードで試行
            for psm in [6, 8, 13]:
                try:
                    df2,_ = ocr_df(im, psm=psm)
                    if df2 is None or len(df2)==0: continue
                    
                    vals=[]
                    for _,r in df2.iterrows():
                        s=str(r["text"])
                        if re.fullmatch(r"\d{2,3}", s):
                            try:
                                v=int(s)
                                if 30<=v<=200:  # RNFL妥当範囲
                                    conf = r.get('conf', 50)  # 信頼度取得
                                    vals.append((s, conf, r['left'], r['top']))
                            except:
                                pass
                    
                    # OSサイド（右円）の特別処理
                    if side_name == "OS" and len(vals) >= 1:
                        # OSサイドはT/N順序が逆になることがある
                        # Y座標でまずソート、次にX座標
                        vals.sort(key=lambda x: (x[3], x[2]))
                        
                        # 特にT_OS（Temporal）の検出強化
                        if len(vals) >= 2:
                            # 2つの値がある場合、左側をT、右側をNとする
                            t_val, n_val = vals[0][0], vals[1][0]
                            score = sum(v[1] for v in vals[:2])
                            debug_info += f"  候補{i+1}-PSM{psm}(OS特別): T={t_val}, N={n_val} (score:{score:.1f})\n"
                            
                            if score > best_score:
                                best_result = (t_val, n_val)
                                best_score = score
                        elif len(vals) == 1:
                            # 1つしかない場合、T位置として扱う
                            t_val = vals[0][0]
                            score = vals[0][1]
                            debug_info += f"  候補{i+1}-PSM{psm}(OS単独): T={t_val} (score:{score:.1f})\n"
                            
                            if score > best_score:
                                best_result = (t_val, "")
                                best_score = score
                    else:
                        # ODサイドは従来通り
                        vals.sort(key=lambda x: (x[3], x[2]))  # Y座標、X座標順
                        
                        if len(vals) >= 2:
                            score = sum(v[1] for v in vals[:2])  # 上位2つの信頼度合計
                            debug_info += f"  候補{i+1}-PSM{psm}: {[v[0] for v in vals[:2]]} (score:{score:.1f})\n"
                            
                            if score > best_score:
                                best_result = (vals[0][0], vals[1][0])
                                best_score = score
                    
                except Exception as e:
                    continue
        
        debug_info += f"  最終選択: {best_result} (score:{best_score:.1f})\n"
        debug_dump(dbg, f"quad_{side_name.lower()}_debug", txt=debug_info)
        return best_result
    
    # 左円（OD）と右円（OS）で最適抽出
    t_od, n_od = extract_best_nums(left_candidates, "OD")
    t_os, n_os = extract_best_nums(right_candidates, "OS")
    
    out["RNFL_T_OD"], out["RNFL_N_OD"] = t_od, n_od
    out["RNFL_T_OS"], out["RNFL_N_OS"] = t_os, n_os
    
    return out

def is_disc_oct(df):
    """OCT Disc vs Macular の判定"""
    all_text = " ".join([str(r["text"]) for _, r in df.iterrows()]).upper()
    
    # Disc OCTの特徴的キーワード
    disc_keywords = ["AVERAGE THICKNESS RNFL", "DISC TOPOGRAPHY", "RNFL THICKNESS", "OPTIC DISC"]
    # Macular OCTの特徴的キーワード  
    macular_keywords = ["THICKNESS MAP", "MACULAR", "FOVEA", "CENTRAL THICKNESS"]
    
    disc_score = sum(1 for kw in disc_keywords if kw in all_text)
    macular_score = sum(1 for kw in macular_keywords if kw in all_text)
    
    return disc_score > macular_score

def process_one(p: Path, out_rows: list, debug=False):
    print(f"🔍 処理中: {p.name}")
    img = read_img(p)
    if img is None:
        print(f"❌ 画像読み込み失敗: {p}")
        out_rows.append({"ソース":p.name})
        return
        
    df, _ = ocr_df(img, psm=6)
    if df is None or len(df)==0:
        print(f"❌ OCR失敗: {p}")
        out_rows.append({"ソース":p.name})
        return
    
    # OCT種別判定
    if not is_disc_oct(df):
        print(f"⏭️  Macular OCTのためスキップ: {p.name}")
        out_rows.append({"ソース":p.name, "備考":"Macular OCT - スキップ"})
        return
        
    print(f"📄 OCRデータ行数: {len(df)} (Disc OCT)")
    dbg = (Path("debug")/p.stem) if debug else None

    ss_od, ss_os = extract_ss(df)
    print(f"✅ Signal Strength: OD={ss_od}, OS={ss_os}")
    
    # v3方式でRNFL抽出
    rnfl = extract_rnfl_table_v3(img, df, dbg)
    rnfl_count = sum(1 for v in rnfl.values() if v)
    print(f"✅ RNFL抽出(v3): {rnfl_count}/6個の値")
    
    # v4改良版でTopography抽出
    topo = extract_disc_topography_v4(img, df, dbg)
    topo_count = sum(1 for v in topo.values() if v)
    print(f"✅ Topography抽出(v4改): {topo_count}/6個の値")
    
    # v3方式でQuadrant抽出
    quad = extract_quad_optional_v3(img, df, dbg)
    quad_count = sum(1 for v in quad.values() if v)
    print(f"✅ Quadrant抽出(v3): {quad_count}/4個の値")

    row = {"ソース":p.name, "SS_OD":ss_od, "SS_OS":ss_os, **rnfl, **topo, **quad}
    out_rows.append(row)
    print("✅ 処理完了\n")

def main():
    ap=argparse.ArgumentParser(description="Topcon OCT Disc Report 抽出 Hybrid（v3+v4改良）")
    ap.add_argument("patterns", nargs="+", help="画像パス（ワイルドカード可）")
    ap.add_argument("--out", default="oct_disc_hybrid.csv")
    ap.add_argument("--debug", action="store_true")
    args=ap.parse_args()

    print(f"🔬 Topcon OCT Disc Hybrid - {len(args.patterns)}パターン処理")
    if args.debug:
        print("🐛 デバッグモード: debug/<画像名>/にROI画像保存")
    print("=" * 60)

    out=[]
    for pat in args.patterns:
        try:
            # 絶対パスの場合の処理
            if os.path.isabs(pat):
                files = [Path(f) for f in glob.glob(pat)]
            else:
                files = list(Path().glob(pat))
        except Exception as e:
            print(f"❌ パターンエラー '{pat}': {e}")
            files = []
        
        print(f"📂 パターン '{pat}': {len(files)}ファイル")
        for p in files:
            process_one(p, out, debug=args.debug)

    cols=["ソース","備考","SS_OD","SS_OS",
          "RNFL_Total_OD","RNFL_Total_OS","RNFL_S_OD","RNFL_S_OS","RNFL_I_OD","RNFL_I_OS",
          "RimArea_OD_mm2","DiscArea_OD_mm2","CupVolume_OD_mm3",
          "RimArea_OS_mm2","DiscArea_OS_mm2","CupVolume_OS_mm3",
          "RNFL_T_OD","RNFL_T_OS","RNFL_N_OD","RNFL_N_OS"]
    
    with open(args.out,"w",encoding=ENC,newline="") as f:
        w=csv.DictWriter(f, fieldnames=cols); w.writeheader(); w.writerows(out)
    
    print("=" * 60)
    print(f"✅ 出力完了: {args.out}")
    print(f"📊 処理件数: {len(out)}件")
    
    # 結果サマリー
    if out:
        filled_counts = {}
        for col in cols[1:]:  # ソース以外
            filled_counts[col] = sum(1 for row in out if row.get(col, ""))
        
        print("\n📈 抽出成功率:")
        for col, count in filled_counts.items():
            rate = count / len(out) * 100
            print(f"  {col}: {count}/{len(out)} ({rate:.1f}%)")

if __name__=="__main__":
    main()
