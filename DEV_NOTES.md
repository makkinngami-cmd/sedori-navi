# せどりナビ 開発メモ

## プロジェクト概要
ポイントせどり支援ツール。買取価格・定価・ヤフオク落札相場をグラフ表示する。  
GitHub Pages でホスティング。データ収集は GitHub Actions で自動化。

---

## ファイル構成

```
sedori-navi/
├── data/
│   ├── prices.csv          # 買取・ヤフオク価格の蓄積データ
│   └── msrp.csv            # 定価マスタ（effective_date列で値上げ履歴管理）
├── docs/
│   ├── index.html          # GitHub Pages フロントエンド（Chart.js）
│   ├── prices.csv          # data/ のコピー（Pages配信用）
│   └── msrp.csv            # data/ のコピー（Pages配信用）
├── scraper/
│   ├── products.py         # 商品マスタ（全スクレイパーが参照）
│   ├── scrape.py           # 買取一丁目 毎日スクレイプ
│   ├── scrape_msrp.py      # 定価取得（価格.com → Amazon参考価格、手動実行）
│   ├── scrape_yahoo.py     # ヤフオク落札相場 週1スクレイプ
│   ├── migrate_msrp_add_date.py  # マイグレーション済み（再実行不要）
│   └── requirements.txt    # requests, playwright
└── .github/workflows/
    ├── scrape.yml                      # 毎日 JST 12:00〜21:00 リトライ
    ├── scrape_yahoo.yml                # 毎週月曜 07:00 JST
    └── msrp_price_update_20260525.yml  # 2026/5/25 Switch値上げ自動適用（1回限り）
```

---

## prices.csv の構造

```
date, product_name, store, price, jan, url
```

`store` に入る値：
| 値 | 更新頻度 | 内容 |
|---|---|---|
| `買取一丁目` | 毎日自動 | 買取一丁目の買取価格 |
| `ヤフオク 最安` | 週1自動（月曜） | 過去7日落札の最安値 |
| `ヤフオク 平均` | 週1自動（月曜） | 過去7日落札の平均値 |
| `ヤフオク 最高` | 週1自動（月曜） | 過去7日落札の最高値 |

---

## msrp.csv の構造

```
product_name, msrp, effective_date, source_url, matched_title
```

- `effective_date` で値上げ前後の定価を管理（同一商品に複数行OK）
- `index.html` の `getMsrpForDate(name, date)` が日付時点の有効な定価を返す
- グラフの定価線が値上げ日に段差で表示される

### 手動でMSRPを修正するとき
`data/msrp.csv` と `docs/msrp.csv` の両方を編集してコミットする。

---

## 定期実行スケジュール

| ワークフロー | タイミング | 内容 |
|---|---|---|
| `scrape.yml` | 毎日 JST 12:00〜21:00（1時間ごとリトライ） | 買取一丁目の買取価格 |
| `scrape_yahoo.yml` | 毎週月曜 07:00 JST | ヤフオク落札相場 |
| `msrp_price_update_20260525.yml` | 2026/5/25 00:05 JST（1回限り） | Switch値上げ定価更新 |

---

## 各スクレイパーの仕様

### scrape.py（買取一丁目）
- 買取一丁目の JSON REST API を叩く
- `_already_scraped_today(threshold=100)` で当日取得済みならスキップ
- 毎時リトライ → 1回成功すれば以降は数秒でスキップ終了

### scrape_msrp.py（定価、手動実行）
```bash
cd scraper
python scrape_msrp.py
```
- **Step A**: 価格.com のメーカー希望小売価格欄
- **Step B**: Amazon の参考価格（Step A で取れなかった場合）
- `get_price_floor()` を下回る既存価格は自動的に再スクレイプ対象になる
- ポケカ・ワンピはスキップ（`SKIP_CATEGORIES`）
- 結果は `matched_title` 列で照合確認し、おかしければ `msrp` を手動修正

### scrape_yahoo.py（ヤフオク、週1自動）
- ヤフオク落札済み検索（`istatus=1` = 新品フィルター）
- 過去7日の落札価格から最安・平均・最高を計算
- `products.py` の `keywords` で商品名マッチング
- **ローカルテスト**: `cd scraper && python scrape_yahoo.py`

---

## Nintendo Switch 値上げ対応（2026/5/25）

5/25 JST 0:05 に `msrp_price_update_20260525.yml` が自動実行され、
以下の商品の新定価行が `msrp.csv` に追記される（既存行は残る）。

| 商品 | 旧価格 | 新価格 |
|---|---|---|
| Switch2 国内版 | ¥49,980 | ¥59,980 |
| Switch 有機EL（白/ネオン） | ¥37,980 | ¥47,980 |
| Switch 新型（ネオン/グレー） | ¥32,978 | ¥43,980 |
| Switch Lite 全5色 | ¥21,978 | ¥29,980 |

手動テストは Actions タブ → `Run workflow` で実行可能。

---

## 残タスク・要確認事項

### ⚠️ PS5デジタル ダブルパック（CFIJ-10032）定価要確認
現在の msrp.csv は推定値 ¥79,980。実際の公式価格を確認して手動修正が必要。

---

### ✅ ヤフオク動作確認（2026-05-18 完了）
ローカル実機テストで PS5 など動作確認済み。以下のバグを修正・push 済み：

- `ALL_PRODUCTS.items()` クラッシュ → カテゴリフィルタに修正
- JS セレクター（`.Product` クラス廃止）→ `li > a[href*="/auction/"]` 構造に変更
- 日付パーサー：`"5/18 22:58終了"` 形式に対応（`M/DD` パターン追加）
- CUSTOM_QUERIES の Steam Deck キーを products.py 名称（有機EL表記）に統一
- PS5 新商品追加：PS5デジタル 日本語版（CFI-2200B01）・PS5デジタル ダブルパック（CFIJ-10032）
- 5/18 誤データ修正：CFIJ-10032 が PS5デジタルとして記録されていたのを訂正

**落札データなし商品について（正常）：**  
Switch2 本体・Steam Deck など取引量が少ない商品は直近7日に落札がないことがある。  
スクレイパー自体の問題ではなく、商品の市況による。

**セレクターが再び壊れた場合の対処：**  
`scrape_yahoo.py` の `fetch_closed_auctions()` 内の JS を修正。  
`li` 要素の中に `a[href*="/auction/"]` があることが前提。価格は `span[text='落札']` の次 span。日付は `span[text*='終了']`。

---

## よくある作業

### 商品を追加する
1. `scraper/products.py` に追加
2. `docs/index.html` の `PRODUCT_CATEGORIES` と必要なら `SUBCATEGORIES` に追加
3. `scrape_msrp.py` を手動実行して定価を取得

### MSRPを手動修正する
```bash
# data/msrp.csv と docs/msrp.csv の両方を編集してコミット
git add data/msrp.csv docs/msrp.csv
git commit -m "fix: 手動修正の内容"
```

### 価格フロアを調整する
`scraper/scrape_msrp.py` の `get_price_floor(name)` を編集する。  
フロアを下回る既存価格は次回 `scrape_msrp.py` 実行時に再スクレイプされる。
