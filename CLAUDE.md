# sedori-navi — メンテナンスガイド

買取店（買取一丁目・モバイル一番）とヤフオクの価格を毎日自動収集し、GitHub Pages でチャート表示するシステム。

---

## ファイル構成

```
sedori-navi/
├── scraper/
│   ├── products.py          # 商品マスタ（PRODUCTS辞書 + CUSTOM_QUERIES）
│   ├── scrape.py            # 買取店スクレイパー本体（Playwright + BS4）
│   ├── scrape_yahoo.py      # ヤフオク落札価格スクレイパー
│   ├── scrape_msrp.py       # 定価/市場価格更新スクリプト（手動実行）
│   └── requirements.txt
├── data/
│   ├── prices.csv           # 日次買取価格（正本）
│   ├── msrp.csv             # 定価・市場参考価格（正本）
│   └── last_scrape.txt      # 最終スクレイプ日時
├── docs/                    # GitHub Pages ルート（data/ の内容をコピー）
│   ├── index.html           # フロントエンド（Chart.js / 単一ファイル）
│   ├── prices.csv
│   └── msrp.csv
├── run_scraper.ps1          # Windowsタスクスケジューラから実行するランチャー
└── logs/scraper.log         # スクレイプ実行ログ
```

**重要**: `data/` と `docs/` の CSV は常に同じ内容にする。
`run_scraper.ps1` が自動でコピー＆git pushするため、手動編集後は両方更新すること。

---

## データ形式

### prices.csv
```
date,product_name,store,price
2026-05-21,Switch 有機白,買取一丁目,46800
2026-05-21,Switch 有機白,ヤフオク 最安,44000
2026-05-21,Switch 有機白,ヤフオク 中央値,47500
2026-05-21,Switch 有機白,ヤフオク 最高,52000
```
- `store` の値: `買取一丁目` / `モバイル一番` / `ヤフオク 最安` / `ヤフオク 中央値` / `ヤフオク 最高`
- 同日・同商品・同店舗が重複した場合は最後の行が有効（上書きではなく追記形式）

### msrp.csv
```
product_name,msrp,source,effective_date,notes,price_type
Switch 有機白,37980,任天堂公式,2021-10-08,,
instax mini 12,9800,kakaku.com,2026-05-01,,market
```
- `price_type` が `market` → UI で「市場比」表示（カメラ・レンズ類）
- `price_type` が空 → UI で「買取率」表示（ゲーム機・定価明確な商品）

---

## よくある保守作業

### 1. 商品を追加する

**① scraper/products.py を編集**
```python
PRODUCTS = {
    # ...
    "新商品名": ["キーワード1", "キーワード2"],  # 追加
}
```
ヤフオクの検索クエリを変えたい場合は `CUSTOM_QUERIES` にも追加:
```python
CUSTOM_QUERIES = {
    "新商品名": "ヤフオク検索ワード",
}
```

**② docs/index.html の PRODUCT_CATEGORIES を更新**
```javascript
const PRODUCT_CATEGORIES = {
  // ...
  "新商品名": "ゲーム",  // カテゴリ: ゲーム/カメラ/ポケカ/ワンピ/スマートフォン/その他
};
```

**③ msrp.csv に定価を追加**（data/ と docs/ 両方）
```
新商品名,定価数値,メーカー公式,YYYY-MM-DD,,
```
カメラ・レンズで市場価格基準にする場合は末尾を `,,market` にする。

**④ コミット・push**
```
git add scraper/products.py docs/index.html data/msrp.csv docs/msrp.csv
git commit -m "feat: add 新商品名"
git push origin main
```

---

### 2. 定価・市場価格を修正する

`data/msrp.csv` と `docs/msrp.csv` の両方を編集して、該当行の `msrp` 列を更新する。
`effective_date` も修正した日付に変更する。

コミット:
```
git add data/msrp.csv docs/msrp.csv
git commit -m "fix: msrp update 商品名"
git push origin main
```

---

### 3. UIのスタイルを微修正する

`docs/index.html` はすべて1ファイルに収まっている（CSS・JS・HTML）。
- レスポンシブ対応は `@media (max-width: 720px)` ブロックに集約
- カラーはCSS変数（`:root` の `--accent` `--surface` 等）で管理

編集後:
```
git add docs/index.html
git commit -m "style: ..."
git push origin main
```

---

### 4. スクレイパーを手動実行する

```powershell
# PowerShell
C:\Users\makki\sedori-navi\run_scraper.ps1
```

またはPythonで個別実行:
```powershell
$PYTHON = "C:\Users\makki\AppData\Local\Programs\Python\Python311\python.exe"
& $PYTHON "C:\Users\makki\sedori-navi\scraper\scrape.py"
& $PYTHON "C:\Users\makki\sedori-navi\scraper\scrape_yahoo.py"
```

ログ: `C:\Users\makki\sedori-navi\logs\scraper.log`

---

### 5. タスクスケジューラの確認

```powershell
schtasks /query /tn "sedori-navi-scraper" /fo LIST
```

毎朝 JST 07:17 に `run_scraper.ps1` を自動実行する設定になっている。

---

## フロントエンド構造（index.html）

主要な関数・データ構造:

| 関数/変数 | 役割 |
|-----------|------|
| `allRows` | prices.csv 全行をパースしたオブジェクト配列 |
| `msrpHistory` | msrp.csv から商品名→MSRP履歴のマップ |
| `priceTypeMap` | 商品名→price_type（'market' or ''）のマップ |
| `PRODUCT_CATEGORIES` | 商品名→カテゴリ文字列のマップ（手動管理） |
| `urlMap` | 商品名→買取一丁目URL（手動管理） |
| `updateProductCards()` | 商品選択時のスタッツカード更新 |
| `buildChartDates()` | チャートのX軸日付配列を生成 |
| `getPriceLabel(name)` | '買取率' or '市場比' を返す |
| `getMsrpLatest(name)` | 指定商品の最新MSRP値を返す |

**前日比の仕組み**: グローバルの全スクレイプ日から「直前の日付(globalPrev)」を求め、
その日時点での当該商品の最新価格と比較する。カレンダー計算ではなくスクレイプ実績日基準。

---

## GitHub Pages

- URL: `https://makkinngami-cmd.github.io/sedori-navi/`
- `docs/` フォルダが公開ルート
- pushから反映まで通常1〜2分

---

## 注意事項

- `data/` と `docs/` のCSVは必ず同期する（run_scraper.ps1 が自動化しているが手動編集時は注意）
- GitHub Actions の cron は遅延・スキップが多いため、スクレイプの主体はWindowsタスクスケジューラ
- MSRPのカメラ類は kakaku.com の「新品最安値」を参照価格とする（Amazon出品価格は不正確）
