## ファイル名から抽出する項目と `kbn` マッピング（仕様と経緯）

### 抽出項目（ファイル名・患者テキストから）
- pidnum: 患者ID（必須、例: `&pidnum=20000`）
- pkana: フリガナ（`&pidnum=<PID>.txt` から補完）
- pname: 患者名（漢字、`&pidnum=<PID>.txt` から補完／`krt2-2` はファイル名にも含まれる）
- psex: 性別（患者テキストから補完）
- pbirth: 生年月日（患者テキストや保険証`hoken`から補完）
- cdate: 検査日（`old` 以外で有効）
- tmstamp, drNo, drName, kaNo, kaName: ファイル名から抽出
- kbn: 種別（下記マッピングを参照）
- no: 通し番号
- full_path: 元ファイルの絶対パス
- relative_path: `image_root` に対する相対パス（保存先変更に強いリンク用）
- cdate_valid: `kbn != old` で `1`、`old` は `0`

### `kbn` マッピング要約
- `kowaspe`: スペキュラーマイクロスコープ
- `old`: 古い紙カルテ（cdate 無効）
- `kowagantei`: 眼底カメラ（旧）
- `keikou` / `FAF`: 自発蛍光眼底
- `gantei2`: 新しい眼底カメラ
- `oct2`: OCT
- `angio`: OCTA
- `krt2-2`: 新しい紙カルテ（QRでID/漢字名/受診日がファイル名に）
- `hoken`: 保険証（生年月日/フリガナが含まれることがある）
- `kowaslit`: Kowa スリット（細隙灯）
- `kowatopo`: Kowa トポグラフィー（角膜形状解析）
- `kowaetc`: 古い 7OCT（旧OCT）
- `kensa`: ハンフリー視野検査

### 実装の要点（2025-08 現在）
1. 画像ファイル名から URL 形式のキー値を抽出（`&pidnum=...&kbn=...&no=...`）。
2. 患者フォルダ内の `&pidnum=<PID>.txt` を読み、`pkana/pname/psex/pbirth` を補完。
3. `cdate_valid` を `kbn` に応じて算出（`old=0`、それ以外=1）。
4. 出力先は `path_config.json` の `output_root` 配下に患者ごとに保存。
5. 互換性のため、UTF-8 BOM の CSV と UTF-16 の TSV を同時出力。
6. `by_kbn` フォルダに種別ごとの CSV/TSV を分割保存。
7. サムネイルは `thumbnails/` に最大幅512pxで保存。

### 保存場所（既定）
- 入力: `image_root`（例: `D:\画像`）
- 出力: `output_root`（例: `C:\Users\bnr39\OneDrive\カルテOCR`）

### 関連スクリプト
- `export_filename_params.py`: 任意フォルダを指定してファイル名メタのCSV/TSV出力＋`by_kbn`分割
- `patient_pack_export.py`: `--pid <ID>` で患者単位のCSV/TSV、サムネイル生成、`by_kbn`分割

### 経緯ダイジェスト
- `kbn` ごとの定義と `cdate` の有効性（`old`のみ無効）を確立。
- 患者テキスト（`&pidnum=<PID>.txt`）の存在を前提に、`pkana/pname/psex/pbirth` を補完する処理を追加。
- Excel/Google Sheets 両対応のため CSV(UTF-8 BOM) と TSV(UTF-16) を併用。
- 保存先を OneDrive に統一し、`path_config.json` で一括変更可能にした。

### リンク
- GitHub: https://github.com/hasemo1999/medical-ocr-system


