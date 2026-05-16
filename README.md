# sedori-navi

買取店（モバイル一番・買取一丁目）の商品価格を毎日自動収集し、GitHub Pages で価格推移チャートを表示するシステム。

## 構成

```
sedori-navi/
├── .github/workflows/scrape.yml   # 毎日 JST 12:00 に自動実行
├── scraper/
│   ├── scrape.py                  # スクレイピング本体
│   ├── products.py                # 商品マスタ（約130商品）
│   └── requirements.txt
├── data/
│   └── prices.csv                 # 日付,商品名,店舗,価格 の形式で追記
├── docs/                          # GitHub Pages のルート
│   └── index.html                 # Chart.js 価格推移チャート UI
└── README.md
```

## セットアップ

### 1. リポジトリ作成

GitHub で `sedori-navi` という名前のパブリックリポジトリを作成し、このコードを push する。

```bash
cd sedori-navi
git init
git add .
git commit -m "initial commit"
git remote add origin https://github.com/<your-username>/sedori-navi.git
git push -u origin main
```

### 2. GitHub Pages の設定

`Settings` → `Pages` → `Source` を **Deploy from a branch** に設定し、
Branch: `main` / Folder: `/docs` を選択して Save。

数分後に `https://<your-username>.github.io/sedori-navi/` で表示される。

### 3. GitHub Actions の確認

`Actions` タブで **Daily Price Scraper** ワークフローが存在することを確認。
初回テストは **Run workflow** ボタンで手動実行できる。

## ローカルでのテスト

```bash
cd scraper
pip install -r requirements.txt
playwright install --with-deps chromium
python scrape.py
```

実行後、`data/prices.csv` に本日分のデータが追記される。

## データ形式

```csv
date,product_name,store,price
2026-05-10,Switch2 国内版,モバイル一番,47000
2026-05-10,Switch2 国内版,買取一丁目,52500
```

## スクレイパーのカスタマイズ

### 商品の追加・削除

`scraper/products.py` の `PRODUCTS` 辞書を編集する。
`docs/index.html` 内の `PRODUCT_CATEGORIES` オブジェクトにも同じ商品名を追加すること。

### URL の調整

各店舗のサイト構造が変わった場合は `scrape.py` の以下を更新する:

- `MOBILE_ICHIBAN_URLS` — モバイル一番のカテゴリページ URL リスト
- `ICHOME_URLS` — 買取一丁目のカテゴリページ URL リスト

### セレクターの確認

価格取得に失敗する場合は、スクレイパーが出力するログを確認し、
`_extract_from_page()` 内の CSS クラスパターンを実際のサイトに合わせて調整する。

## 対象店舗

| 店舗 | URL | 取得方法 |
|------|-----|---------|
| モバイル一番 | https://www.mobile-ichiban.com/ | requests + BeautifulSoup (SSR) |
| 買取一丁目 | https://www.1-chome.com/ | Playwright (動的レンダリング) |

## 対象カテゴリ

- 🎮 ゲーム（Switch2・PS5・Xbox・Meta Quest・Steam Deck 等）
- 📷 カメラ（instax・Canon・Fujifilm X100VI・RICOH GR 等）
- 🃏 ポケカ（ブースターパック各種）
- 🃏 ワンピカード（OP-10〜OP-15・EB・PRB シリーズ）
- 📦 その他（Tamagotchi 等）
