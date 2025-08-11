# Medical OCR System - Tools

医療カルテOCRシステムのツール群

## 📁 プロジェクト構造

```
tools/
├── Python版
│   ├── p1_distribute.py          # QRコード読取・CSV管理
│   ├── p2_printed_ocr.py         # 印刷系OCR（NCT・レフ値・IOLシール）
│   ├── login.py                  # 基本ログイン処理
│   ├── login_optimized.py        # 最適化版ログイン処理
│   ├── test_p2_ocr.py           # P2 OCRテスト
│   └── requirements_p2.txt       # Python依存関係
├── TypeScript版
│   ├── login.ts                  # TypeScript版ログイン処理
│   ├── login.test.ts             # TypeScript版テスト
│   ├── package.json              # Node.js依存関係
│   └── tsconfig.json             # TypeScript設定
└── README.md                     # このファイル
```

## 🎯 主要機能

### P1: QRコード読取
- 患者ID・日付・患者名の抽出
- 精度: ≥99.5%

### P2: 印刷系OCR
- **NCT平均値**: 右眼/左眼（≥98%精度）
- **レフ値**: S/C/Ax形式（誤差≤±0.25D）
- **IOLシール**: 度数・製品名（正確読取）

### 認証システム
- JWTトークン生成・検証
- レート制限（15分間に5回）
- アカウントロック（5回失敗で15分）
- トークンブラックリスト

## 🚀 使用方法

### Python版

```bash
# 依存関係インストール
pip install -r requirements_p2.txt

# P1: QRコード読取
python p1_distribute.py --patients-root ".\Patients" --master-csv ".\Patients\master.csv" --apply

# P2: 印刷系OCR
python p2_printed_ocr.py --patients-root ".\Patients" --master-csv ".\Patients\master.csv" --apply

# ログインテスト
python login.py
python login_optimized.py

# P2 OCRテスト
python test_p2_ocr.py
```

### TypeScript版

```bash
# 依存関係インストール
npm install

# 開発実行
npm run dev

# ビルド
npm run build

# テスト実行
npm test

# 型チェック
npm run type-check
```

## 📊 合格基準

| 項目 | 精度基準 | 備考 |
|------|----------|------|
| P1 QR読取 | ≥99.5% | 患者ID・日付・患者名 |
| P2 NCT | ≥98% | 右眼/左眼平均値 |
| P2 レフ値 | 誤差≤±0.25D | S/C/Ax形式 |
| P2 IOLシール | 正確読取 | 度数・製品名 |

## 🔧 設定

### 環境変数
```bash
# JWTシークレットキー
export JWT_SECRET="your-secret-key"

# Google Vision API
export GOOGLE_APPLICATION_CREDENTIALS="path/to/service-account.json"
```

### サンプルユーザー
- `admin` / `admin` - 管理者
- `user1` / `123` - 一般ユーザー
- `doctor` / `空文字` - 医師

## 🧪 テスト

### Python版テスト
```bash
# P2 OCRテスト実行
python test_p2_ocr.py

# 結果確認
cat p2_test_results.json
```

### TypeScript版テスト
```bash
# Jestテスト実行
npm test

# カバレッジ確認
npm run test:coverage
```

## 📝 ログ

### ログレベル
- `DEBUG` - デバッグ情報
- `INFO` - 正常処理完了
- `WARNING` - 警告
- `ERROR` - エラー発生
- `CRITICAL` - 致命的エラー

### ログ出力例
```
2024-01-15 10:30:15 - INFO - ログイン成功: admin
2024-01-15 10:30:16 - INFO - P2 OCR処理開始: 100件
2024-01-15 10:30:20 - INFO - P2 OCR処理完了: 成功=98件, 失敗=2件
```

## 🔒 セキュリティ

### 実装済み機能
- ✅ パスワードハッシュ化（SHA256）
- ✅ JWTトークン（24時間有効）
- ✅ レート制限（15分間に5回）
- ✅ アカウントロック（5回失敗で15分）
- ✅ トークンブラックリスト
- ✅ 入力値検証
- ✅ エラーハンドリング

### 推奨設定
- 本番環境では強力なJWTシークレットを使用
- HTTPS通信の強制
- 定期的なパスワード変更
- アクセスログの監視

## 📞 サポート

問題が発生した場合は、以下を確認してください：

1. 依存関係のインストール状況
2. 環境変数の設定
3. ファイルパスの正確性
4. ログファイルの確認

## 📄 ライセンス

MIT License
