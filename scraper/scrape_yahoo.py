#!/usr/bin/env python3
"""
ヤフオク落札価格スクレイパー（毎日実行・同日重複スキップ）
落札済み新品商品の過去7日分から 最安・中央値・最高 を取得し prices.csv に追記する

実行:
    cd scraper
    python scrape_yahoo.py
"""

import asyncio
import csv
import io
import logging
import os
import random
import re
import sys
import urllib.parse
from datetime import datetime, timezone, timedelta
from pathlib import Path
from statistics import mean, median

from playwright.async_api import async_playwright, Page

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, str(Path(__file__).parent))
from products import ALL_PRODUCTS

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)
logger = logging.getLogger(__name__)

JST      = timezone(timedelta(hours=9))
TODAY    = datetime.now(JST).strftime('%Y-%m-%d')
CUTOFF   = (datetime.now(JST) - timedelta(days=7)).strftime('%Y-%m-%d')

BASE_DIR      = Path(__file__).parent.parent
DATA_FILE     = BASE_DIR / 'data' / 'prices.csv'
SCRAPE_MARKER = BASE_DIR / 'data' / 'last_yahoo_scrape.txt'
CSV_HEADERS   = ['date', 'product_name', 'store', 'price', 'jan', 'url']

SKIP_CATEGORIES = {'ポケカ', 'ワンピ'}

# 商品ごとにヤフオク検索クエリを上書き
CUSTOM_QUERIES: dict[str, str] = {
    'Nintendo Switch 2 マリオカート ワールドセット 日本語・国内専用': 'Nintendo Switch 2 マリオカートワールド セット',
    'Nintendo Switch 2 日本語・国内専用':              'Nintendo Switch 2 本体 国内版',
    'Nintendo Switch 2 多言語版':            'Nintendo Switch 2 本体 多言語版',
    'Nintendo Switch 2 Proコントローラー':             'Nintendo Switch 2 Proコントローラー',
    'Nintendo Switch (有機ELモデル) ホワイト':               'Nintendo Switch 有機ELモデル ホワイト',
    'Nintendo Switch (有機ELモデル) ネオンブルー・ネオンレッド':           'Nintendo Switch 有機ELモデル ネオン',
    'Nintendo Switch 新型 バッテリー強化版 ネオンブルー/(R) ネオンレッド':           'Nintendo Switch 本体 ネオンブルー ネオンレッド',
    'Nintendo Switch 新型 バッテリー強化版 グレー':           'Nintendo Switch 本体 グレー',
    'Nintendo Switch Lite グレー':           'Nintendo Switch Lite グレー',
    'Nintendo Switch Lite ブルー':           'Nintendo Switch Lite ブルー',
    'Nintendo Switch Lite コーラル':         'Nintendo Switch Lite コーラル',
    'Nintendo Switch Lite ターコイズ':       'Nintendo Switch Lite ターコイズ',
    'Nintendo Switch Lite イエロー':         'Nintendo Switch Lite イエロー',
    'Nintendo Switch Proコントローラー':              'Nintendo Switch Proコントローラー',
    'Nintendo Switch Proコントローラー ゼルダの伝説':       'Nintendo Switch Proコントローラー ゼルダの伝説 知恵のかりもの',
    'Nintendo Switch Proコントローラー スプラトゥーン3エディション':      'Nintendo Switch Proコントローラー スプラトゥーン3',
    'Nintendo Switch ニンテンドーサウンドクロック Alarmo':                      'Nintendo サウンドクロック Alarmo',
    'Pokemon GO Plus +':            'Pokemon GO Plus+',
    'PlayStation5 Pro CFI-7000B01':            'CFI-7000B01',
    'PlayStation5 Slim Disc CFI-2000A01':                'CFI-2000A01',
    'PlayStation5 Slim Digital エディション CFI-2000B01': 'CFI-2000B01',
    'PlayStation 5 デジタル ・ エディション 日本語 専用 CFI-2200B01': 'CFI-2200B01',
    'PlayStation 5 デジタルED ダブルパック 日本語専用 CFIJ-10032': 'CFIJ-10032',
    'PlayStation(R)5 ”Ghost of Yotei” ゴールド リミテッドエディション CFIJ-10029': 'CFIJ-10029',
    'PS5 ディスクドライブ  CFI-ZDD1J': 'CFI-ZDD1J',
    'PlayStation Portal リモートプレーヤー CFIJ-18000':          'PlayStation Portal リモートプレーヤー',
    'PlayStation Portal リモートプレーヤー ブラック CFIJ-18001': 'PlayStation Portal ブラック CFIJ-18001',
    'PlayStation VR2 CFIJ-17000':             'PlayStation VR2',
    'PlayStation VR2 “Horizon Call of the Mountain” 同梱版 CFIJ-17001': 'PlayStation VR2 Horizon Call of the Mountain',
    '【NS2】ゼルダの伝説 ティアーズ オブ ザ キングダム Nintendo Switch 2 Edition': 'ゼルダの伝説 ティアーズ オブ ザ キングダム Switch 2 Edition',
    '【NS2】スーパー マリオパーティ ジャンボリー Nintendo Switch 2 Edition ＋ ジャンボリーTV': 'スーパー マリオパーティ ジャンボリー Switch 2 Edition',
    '【NS2】スーパーマリオブラザーズ ワンダー Nintendo Switch 2 Edition + みんなでリンリンパーク': 'スーパーマリオブラザーズ ワンダー Switch 2 Edition',
    '【NS2】ゼルダの伝説 ブレス オブ ザ ワイルド Nintendo Switch 2 Edition': 'ゼルダの伝説 ブレス オブ ザ ワイルド Switch 2 Edition',
    '【NS2】ゼノブレイドクロス ディフィニティブエディション Nintendo Switch 2 Edition': 'ゼノブレイドクロス Switch 2 Edition',
    '【NS2】星のカービィ ディスカバリー Nintendo Switch 2 Edition ＋ スターリーワールド': '星のカービィ ディスカバリー Switch 2 Edition',
    '【NS2】桃太郎電鉄2 ～あなたの町も きっとある～ Nintendo Switch 2 Edition 東日本編＋西日本編/Switch 2': '桃太郎電鉄2 Switch 2 Edition',
    '【NS2】牧場物語 Lets！風のグランドバザール Nintendo Switch 2 Edition': '牧場物語 風のグランドバザール Switch 2 Edition',
    '【NS2】あつまれ どうぶつの森 Nintendo Switch 2 Edition': 'あつまれ どうぶつの森 Switch 2 Edition',
    '【NS2】ぽこ あ ポケモン': 'ぽこ あ ポケモン Switch 2',
    '【NS2】ゼルダ無双 封印戦記/Switch 2': 'ゼルダ無双 封印戦記 Switch 2',
    '【NS2】ドンキーコング バナンザ': 'ドンキーコング バナンザ Switch 2',
    '【PS5】仁王3': '仁王3 PS5',
    '【NS2】マリオテニス フィーバー': 'マリオテニス フィーバー Switch 2',
    '【NS2】ヨッシーとフカシギの図鑑': 'ヨッシーとフカシギの図鑑 Switch 2',
    '【NS2】カービィのエアライダー': 'カービィのエアライダー Switch 2',
    '【PS5】SILENT HILL f': 'SILENT HILL f PS5',
    '【PS5】黒神話：悟空': '黒神話 悟空 PS5',
    '【PS5】プラグマタ': 'プラグマタ PS5',
    '【NS2】ドラゴンクエストVII Reimagined -Switch': 'ドラゴンクエストVII Reimagined Switch 2',
    '【PS5】Ghost of Yotei': 'Ghost of Yotei PS5',
    '【PS5】アストロボット': 'アストロボット PS5',
    '【PS5】DEATH STRANDING 2: ON THE BEACH': 'DEATH STRANDING 2 PS5',
    '【PS5】Stellar Blade': 'Stellar Blade PS5',
    '【NS2】REANIMAL': 'REANIMAL Switch 2',
    '【PS5】Alan Wake 2 Deluxe': 'Alan Wake 2 Deluxe PS5',
    '【NS2】龍が如く０ 誓いの場所 Director’s Cut': '龍が如く0 Director’s Cut Switch 2',
    '【PS5】Split Fiction': 'Split Fiction PS5',
    '【PS5】Marvel’s Spider-Man 2': 'Marvel’s Spider-Man 2 PS5',
    '【PS5】Minecraft': 'Minecraft PS5',
    'Xbox Series X 1TB デジタル エディション ホワイト EP2-00708':         'Xbox Series X 1TB ホワイト',
    'Xbox Series S 1TB ホワイト EP2-00650':         'Xbox Series S 1TB ホワイト',
    'Xbox Series X RRT-00015':                      'Xbox Series X',
    'Xbox Series S 512 GB EP2-10065':                      'Xbox Series S',
    'Meta Quest 3 512GB':            'Meta Quest 3 512GB',
    'Meta Quest 3 128GB':            'Meta Quest 3 128GB',
    'Steam Deck 有機EL 1TB':        'Steam Deck OLED 1TB',
    'Steam Deck 有機EL 512GB':      'Steam Deck OLED 512GB',
    'FUJIFILM X100V [シルバー]': 'FUJIFILM X100V シルバー',
    'FUJIFILM X100V [ブラック]': 'FUJIFILM X100V ブラック',
    'RICOH GR IV HDF': 'RICOH GR IV HDF',
    'RICOH GR IIIx HDF 特別モデル': 'RICOH GR IIIx HDF',
    'RICOH GR III HDF 特別モデル': 'RICOH GR III HDF',
    'RICOH GR III Street Edition': 'RICOH GR III Street Edition',
    'デジタルカメラ サイバーショット DSC-RX100M7G シューティンググリップキット': 'DSC-RX100M7G',
    '◆DSC-RX100M7': 'DSC-RX100M7',
    'SONY DSC-RX100M6': 'DSC-RX100M6',
    'SONY サイバーショット DSC-RX100M5A': 'DSC-RX100M5A',
    '◆デジタルカメラ PowerShot G5 X Mark II': 'PowerShot G5 X Mark II',
    'PowerShot V10 [ホワイト]': 'PowerShot V10 ホワイト',
    'Canon PowerShot V10 [シルバー]': 'PowerShot V10 シルバー',
    'CANON PowerShot V10 [ブラック]': 'PowerShot V10 ブラック',
    'FUJIFILM X-E5 ボディ [ブラック]': 'FUJIFILM X-E5 ボディ ブラック',
    'FUJIFILM X-E5 ボディ [シルバー]': 'FUJIFILM X-E5 ボディ シルバー',
    'FUJIFILM X-M5 ボディ [シルバー]': 'FUJIFILM X-M5 ボディ シルバー',
    'FUJIFILM X-M5 ボディ [ブラック]': 'FUJIFILM X-M5 ボディ ブラック',
    'Nikon Z5II ボディ': 'Nikon Z5II ボディ',
    'Nikon Z6III ボディ': 'Nikon Z6III ボディ',
    # iPhone 17 Pro Max
    'iPhone 17 Pro Max 256GB シルバー':         'iPhone 17 Pro Max 256GB シルバー SIMフリー',
    'iPhone 17 Pro Max 256GB ディープブルー':   'iPhone 17 Pro Max 256GB ディープブルー SIMフリー',
    'iPhone 17 Pro Max 256GB コズミックオレンジ':'iPhone 17 Pro Max 256GB コズミックオレンジ SIMフリー',
    'iPhone 17 Pro Max 512GB シルバー':         'iPhone 17 Pro Max 512GB シルバー SIMフリー',
    'iPhone 17 Pro Max 512GB ディープブルー':   'iPhone 17 Pro Max 512GB ディープブルー SIMフリー',
    'iPhone 17 Pro Max 512GB コズミックオレンジ':'iPhone 17 Pro Max 512GB コズミックオレンジ SIMフリー',
    'iPhone 17 Pro Max 1TB シルバー':           'iPhone 17 Pro Max 1TB シルバー SIMフリー',
    'iPhone 17 Pro Max 1TB ディープブルー':     'iPhone 17 Pro Max 1TB ディープブルー SIMフリー',
    'iPhone 17 Pro Max 1TB コズミックオレンジ': 'iPhone 17 Pro Max 1TB コズミックオレンジ SIMフリー',
    'iPhone 17 Pro Max 2TB シルバー':           'iPhone 17 Pro Max 2TB シルバー SIMフリー',
    'iPhone 17 Pro Max 2TB ディープブルー':     'iPhone 17 Pro Max 2TB ディープブルー SIMフリー',
    'iPhone 17 Pro Max 2TB コズミックオレンジ': 'iPhone 17 Pro Max 2TB コズミックオレンジ SIMフリー',
    # iPhone 17 Pro
    'iPhone 17 Pro 256GB シルバー':             'iPhone 17 Pro 256GB シルバー SIMフリー',
    'iPhone 17 Pro 256GB ディープブルー':       'iPhone 17 Pro 256GB ディープブルー SIMフリー',
    'iPhone 17 Pro 256GB コズミックオレンジ':   'iPhone 17 Pro 256GB コズミックオレンジ SIMフリー',
    'iPhone 17 Pro 512GB シルバー':             'iPhone 17 Pro 512GB シルバー SIMフリー',
    'iPhone 17 Pro 512GB ディープブルー':       'iPhone 17 Pro 512GB ディープブルー SIMフリー',
    'iPhone 17 Pro 512GB コズミックオレンジ':   'iPhone 17 Pro 512GB コズミックオレンジ SIMフリー',
    'iPhone 17 Pro 1TB シルバー':               'iPhone 17 Pro 1TB シルバー SIMフリー',
    'iPhone 17 Pro 1TB ディープブルー':         'iPhone 17 Pro 1TB ディープブルー SIMフリー',
    'iPhone 17 Pro 1TB コズミックオレンジ':     'iPhone 17 Pro 1TB コズミックオレンジ SIMフリー',
}

# 商品ごとの価格上限（これを超えたら本体込みバンドルと判断）
PRICE_CAPS: dict[str, int] = {
    'PS5 ディスクドライブ  CFI-ZDD1J': 25000,  # MSRP ¥11,980
    'PlayStation Portal リモートプレーヤー CFIJ-18000':            50000,  # MSRP ¥29,980
    'PlayStation VR2 CFIJ-17000':              100000,  # MSRP ¥74,980
}

# 商品ごとの価格下限（ヤフオク検索の min= パラメータに渡す）
# カメラ系は「互換バッテリー」「レンズキャップ」等のアクセサリーが
# 商品名を含んで出品されるため、現実的な最低価格を設定して除外する
PRICE_FLOORS: dict[str, int] = {
    'Canon PowerShot G7 X MarkII':                    8000,
    '◆PowerShot G7 X Mark III\u3000SV':          8000,
    'PowerShot G7 X Mark III\u3000B':          8000,
    'CANON PowerShot G7 X Mark III PowerShot 30th Anniversary Edition':  30000,
    'デジタルカメラ PowerShot G1 X Mark III':         8000,
    'Canon PowerShot V10 [ブラック] トライポッドグリップキット':                   8000,
    'CANON PowerShot V1':                    8000,
    '◆デジタルカメラ PowerShot G5 X Mark II': 8000,
    'PowerShot V10 [ホワイト]':              8000,
    'Canon PowerShot V10 [シルバー]':        8000,
    'CANON PowerShot V10 [ブラック]':        8000,
    '◆デジタルカメラ IXY 650 [シルバー]':                5000,
    '◆デジタルカメラ IXY 650 [ブラック]':                5000,
    'CANON PowerShot IXY 650 m [シルバー]\u300025年':              5000,
    'CANON PowerShot IXY 650 m [ブラック] 25年':              5000,
    '◆Canon PowerShot SX740 HS [シルバー]':                  8000,
    '◆PowerShot SX740 HS [ブラック]':                  8000,
    'CANON PowerShot SX70 HS':                            5000,
    'FUJIFILM X100VI Silver 【新型2025】 E/J':          50000,
    'FUJIFILM X100VI Black 【新型2025】 E/J':          50000,
    'FUJIFILM X100VI [シルバー]':          50000,
    'FUJIFILM X100VI [ブラック]':          50000,
    'FUJIFILM X100V [シルバー]':           50000,
    'FUJIFILM X100V [ブラック]':           50000,
    'FUJIFILM X-E5 ボディ [ブラック]':      30000,
    'FUJIFILM X-E5 ボディ [シルバー]':      30000,
    'FUJIFILM X-M5 ボディ [シルバー]':      20000,
    'FUJIFILM X-M5 ボディ [ブラック]':      20000,
    'FUJIFILM X-T30 II XC15-45mmレンズキット':             15000,
    'Panasonic LUMIX DC-TZ99-K [ブラック]':         10000,
    'LUMIX DC-TZ99 ホワイト':         10000,
    'RICOH GR IV Monochrome':         50000,
    'RICOH GR IV Black':                    50000,
    'RICOH GR IV HDF':                      50000,
    'RICOH GR IIIx HDF 特別モデル':          30000,
    'RICOH GR III HDF 特別モデル':           30000,
    'RICOH GR III Street Edition':           30000,
    'RICOH GR IIIx Urban Edition':    30000,
    'RICOH GR III Diary Edition':     30000,
    '◆RICOH GR IIIx':                  30000,
    '◆RICOH GR III':                   30000,
    'Nikon Z50II ダブルズームキット': 30000,
    'Z50II 18-140 VR レンズキット':    25000,
    'Z50II 16-50 VR レンズキット':     20000,
    'Nikon Z50II ボディ':             20000,
    'Nikon Z5II ボディ':              30000,
    'Nikon Z6III ボディ':             50000,
    'デジタルカメラ サイバーショット DSC-RX100M7G シューティンググリップキット': 30000,
    '◆DSC-RX100M7':                  30000,
    'SONY DSC-RX100M6':               20000,
    'SONY サイバーショット DSC-RX100M5A': 20000,
    'OLYMPUS PEN E-P7 EZダブルズームキット [シルバー]':             15000,
    # PS5ソフトは特典・DLC・関連グッズがソフト名で落札検索に混ざりやすい
    '【PS5】仁王3': 3400,
    '【PS5】SILENT HILL f': 3000,
    '【PS5】黒神話：悟空': 2500,
    '【PS5】プラグマタ': 2800,
    '【PS5】Ghost of Yotei': 3100,
    '【PS5】アストロボット': 2800,
    '【PS5】DEATH STRANDING 2: ON THE BEACH': 3000,
    '【PS5】Stellar Blade': 2500,
    '【PS5】Alan Wake 2 Deluxe': 2500,
    '【PS5】Split Fiction': 2500,
    '【PS5】Marvel’s Spider-Man 2': 2000,
    '【PS5】Minecraft': 1000,
    '【PS5】モンスターハンターストーリーズ3 ～運命の双竜～': 3100,
    # iPhone 17 Pro Max
    'iPhone 17 Pro Max 256GB シルバー':          160000,
    'iPhone 17 Pro Max 256GB ディープブルー':    160000,
    'iPhone 17 Pro Max 256GB コズミックオレンジ':160000,
    'iPhone 17 Pro Max 512GB シルバー':          180000,
    'iPhone 17 Pro Max 512GB ディープブルー':    180000,
    'iPhone 17 Pro Max 512GB コズミックオレンジ':180000,
    'iPhone 17 Pro Max 1TB シルバー':            215000,
    'iPhone 17 Pro Max 1TB ディープブルー':      215000,
    'iPhone 17 Pro Max 1TB コズミックオレンジ':  215000,
    'iPhone 17 Pro Max 2TB シルバー':            250000,
    'iPhone 17 Pro Max 2TB ディープブルー':      250000,
    'iPhone 17 Pro Max 2TB コズミックオレンジ':  250000,
    # iPhone 17 Pro
    'iPhone 17 Pro 256GB シルバー':              140000,
    'iPhone 17 Pro 256GB ディープブルー':        140000,
    'iPhone 17 Pro 256GB コズミックオレンジ':    140000,
    'iPhone 17 Pro 512GB シルバー':              160000,
    'iPhone 17 Pro 512GB ディープブルー':        160000,
    'iPhone 17 Pro 512GB コズミックオレンジ':    160000,
    'iPhone 17 Pro 1TB シルバー':                195000,
    'iPhone 17 Pro 1TB ディープブルー':          195000,
    'iPhone 17 Pro 1TB コズミックオレンジ':      195000,
}

# アクセサリー出品の除外ワード
# （カメラ等で本体名を「対応機種」として記載した周辺機器が引っかかる対策）
ACCESSORY_WORDS = [
    'レンズキャップ', '前キャップ', 'レンズ前キャップ',
    '互換バッテリー', '互換充電器', '互換品',
    'ストラップ', 'ネックストラップ', 'ハンドストラップ',
    'フィルター', 'PLフィルター', 'UVフィルター', 'NDフィルター',
    'レンズフード', 'レンズ フード',
    '液晶保護フィルム', '液晶保護シート', 'スクリーン保護',
    'シリコンカバー', 'シリコンケース',
]


# ── ユーティリティ ────────────────────────────────────────────────────

async def sleep_human() -> None:
    await asyncio.sleep(random.uniform(2.5, 5.0))


def build_query(name: str) -> str:
    if name in CUSTOM_QUERIES:
        return CUSTOM_QUERIES[name]
    q = name
    q = re.sub(r'^Switch2\b',    'Nintendo Switch 2',   q)
    q = re.sub(r'^Switch Lite\b','Nintendo Switch Lite', q)
    q = re.sub(r'^Switch\b',     'Nintendo Switch',     q)
    q = re.sub(r'^Joy-Con 2\b',  'Nintendo Joy-Con 2',  q)
    q = re.sub(r'^Joy-Con\b',    'Nintendo Joy-Con',    q)
    if re.search(r'G7[_ ]?X|SX740|IXY|PowerShot|G1 X', q) and 'Canon' not in q:
        q = 'Canon ' + q
    if re.search(r'X100VI|instax|チェキ|WIDE 400|SQ1|mini (13|Evo)', q):
        if 'FUJIFILM' not in q and 'Fujifilm' not in q:
            q = 'FUJIFILM ' + q
    if re.search(r'Tamagotchi|たまごっち', q) and 'BANDAI' not in q:
        q = 'BANDAI ' + q
    q = q.replace('（新）', '').replace('（旧）', '').replace('（', ' ').replace('）', ' ')
    return re.sub(r'\s+', ' ', q).strip()


def parse_yahoo_date(date_str: str) -> str | None:
    """ヤフオクの各種日付フォーマットを YYYY-MM-DD に変換"""
    now = datetime.now(JST)
    s = date_str.strip()
    # "終了" / 時刻部分を除去: "5/18 22:58終了" → "5/18"
    s = s.replace('終了', '').strip()
    s = re.sub(r'\s+\d{1,2}:\d{2}.*$', '', s).strip()

    # "N分前" / "N時間前" → 今日
    if re.search(r'\d+(分|時間)前', s):
        return now.strftime('%Y-%m-%d')

    # "N日前"
    m = re.match(r'(\d+)日前', s)
    if m:
        return (now - timedelta(days=int(m.group(1)))).strftime('%Y-%m-%d')

    # "YYYY年M月D日"
    m = re.match(r'(\d{4})年(\d+)月(\d+)日', s)
    if m:
        return f'{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}'

    # "M月D日"（年なし → 今年、ただし未来なら昨年）
    m = re.match(r'(\d+)月(\d+)日', s)
    if m:
        mo, da = int(m.group(1)), int(m.group(2))
        yr = now.year
        if (mo, da) > (now.month, now.day):
            yr -= 1
        return f'{yr}-{mo:02d}-{da:02d}'

    # "YYYY/MM/DD" or "YYYY-MM-DD"
    m = re.match(r'(\d{4})[-/](\d{2})[-/](\d{2})', s)
    if m:
        return f'{m.group(1)}-{m.group(2)}-{m.group(3)}'

    # "M/D" or "M/DD"（年なし → 今年、ただし未来なら昨年）
    m = re.match(r'^(\d{1,2})/(\d{1,2})$', s)
    if m:
        mo, da = int(m.group(1)), int(m.group(2))
        yr = now.year
        if (mo, da) > (now.month, now.day):
            yr -= 1
        return f'{yr}-{mo:02d}-{da:02d}'

    # datetime 属性 (ISO8601 "2026-05-18T...")
    m = re.match(r'(\d{4}-\d{2}-\d{2})', s)
    if m:
        return m.group(1)

    return None


# ── ヤフオク スクレイパー ────────────────────────────────────────────

YAHOO_CLOSED = 'https://auctions.yahoo.co.jp/closedsearch/closedsearch'


async def fetch_closed_auctions(
    page: Page,
    query: str,
    min_price: int = 0,
) -> list[dict]:
    """
    ヤフオク落札済み検索（新品: istatus=1）から過去7日分の落札価格リストを取得。
    Returns: [{'title': str, 'price': int, 'date': 'YYYY-MM-DD', 'url': str, 'is_store': bool}, ...]
    """
    params = urllib.parse.urlencode({
        'p':       query,
        'istatus': '1',         # 新品
        'n':       '100',       # 1ページ最大件数
        'b':       '1',
        'ei':      'UTF-8',
    })
    if min_price > 0:
        params += f'&min={min_price}'

    url = f'{YAHOO_CLOSED}?{params}'
    try:
        await page.goto(url, wait_until='domcontentloaded', timeout=30_000)
    except Exception as e:
        logger.warning(f'  ページ遷移エラー ({query}): {e}')
        return []
    await sleep_human()

    raw = await page.evaluate(r"""() => {
        const results = [];
        // a[href*="/auction/"] を持つ li が商品カード
        const cards = Array.from(document.querySelectorAll('li'))
            .filter(li => li.querySelector('a[href*="/auction/"]'));

        for (const card of cards) {
            // タイトル: クラスなし p（最初に見つかったもの）→ h3 → h2 の順
            let title = '';
            for (const sel of ['p', 'h3', 'h2']) {
                const el = card.querySelector(sel);
                if (el && el.textContent.trim().length > 5) {
                    title = el.textContent.trim().replace(/\s+/g, ' ');
                    break;
                }
            }

            // 価格: "落札" ラベルの次の span → フォールバックで数字+"円" span
            let price = 0;
            const spans = Array.from(card.querySelectorAll('span'));
            for (let i = 0; i < spans.length; i++) {
                if (spans[i].textContent.trim() === '落札' && spans[i + 1]) {
                    const m = spans[i + 1].textContent.match(/[\d,]+/);
                    if (m) { price = parseInt(m[0].replace(/,/g, ''), 10); break; }
                }
            }
            if (!price) {
                for (const sp of spans) {
                    const m = sp.textContent.match(/^([\d,]+)円$/);
                    if (m) { price = parseInt(m[1].replace(/,/g, ''), 10); break; }
                }
            }

            // 日付: "終了" を含む span（例: "5/18 22:58終了"）
            let dateStr = '';
            for (const sp of spans) {
                const t = sp.textContent.trim();
                if (t.includes('終了') && /\d/.test(t)) {
                    dateStr = t;
                    break;
                }
            }
            // time[datetime] があればそちらを優先
            const timeEl = card.querySelector('time[datetime]');
            if (timeEl) dateStr = timeEl.getAttribute('datetime');

            // URL
            const linkEl = card.querySelector('a[href*="/auction/"]');
            const href = linkEl ? linkEl.href : '';
            const cardText = card.textContent.replace(/\s+/g, ' ').trim();
            const isStore = cardText.includes('ストア');

            if (title && price > 0) {
                results.push({ title, price, dateStr, url: href, isStore });
            }
        }
        return results;
    }""")

    # 日付パース & 7日以内フィルタ
    results = []
    for item in raw:
        date = parse_yahoo_date(item['dateStr'])
        if date and date >= CUTOFF:
            results.append({
                'title': item['title'],
                'price': item['price'],
                'date':  date,
                'url':   item['url'],
                'is_store': bool(item.get('isStore')),
            })

    return results


async def scrape_product_yahoo(
    page: Page,
    name: str,
    query: str,
    keywords: list[str],
    min_price: int = 0,
    max_price: int = 0,
) -> list[dict]:
    """
    1商品分のヤフオク落札データを取得し、最安・平均・最高をまとめて返す。
    max_price: 0 なら無制限。アクセサリー類の本体込みバンドル除外に使う。
    """
    items = await fetch_closed_auctions(page, query, min_price)

    if not items:
        logger.info(f'  -- {name}: 落札データなし')
        return []

    # キーワードマッチング（自分の商品に合致するものだけ使う）
    def matches(title: str) -> bool:
        t = title.lower().replace('　', ' ')
        for kw in keywords:
            if kw.lower() in t:
                return True
        return False

    # バンドル・セット売りを除外（本体単体価格のみ採用）
    BUNDLE_WORDS = [
        'まとめ', 'セット売り', '同梱版', 'ソフト付', 'ゲーム付',
        '付属品あり', '本体セット', '本体+', '本体＋', '+コントローラー',
        '＋コントローラー', 'おまけ付', '本付き', '本付]', '本付 ',
        'コントローラー付', 'ゲームセット', 'ソフトセット', 'セット品',
        'レンズ付', 'レンズセット',
        '充電器付', 'ケース付', 'カバー付',
        'おまけ',
    ]
    def is_bundle(title: str) -> bool:
        t = title.replace('　', ' ')
        if any(w in t for w in BUNDLE_WORDS):
            return True
        if re.search(r'(ソフト|ゲーム)\d+本', t):
            return True
        return False

    # 状態不良品を除外（安値方向の外れ値対策）
    BAD_CONDITION_WORDS = [
        'ジャンク', '動作未確認', '難あり', '難有り', '訳あり', '訳有り',
        '破損', '欠品', '部品取り', '動作不良', '水没', '要修理', 'ノークレーム',
    ]
    def is_bad_condition(title: str) -> bool:
        return any(w in title for w in BAD_CONDITION_WORDS)

    def is_accessory(title: str) -> bool:
        return any(w in title for w in ACCESSORY_WORDS)

    matched = [
        it for it in items
        if matches(it['title'])
        and not it.get('is_store')
        and not is_bundle(it['title'])
        and not is_bad_condition(it['title'])
        and not is_accessory(it['title'])
        and (min_price == 0 or it['price'] >= min_price)
        and (max_price == 0 or it['price'] <= max_price)
    ]
    if not matched:
        logger.info(f'  -- {name}: マッチする落札なし ({len(items)} 件中)')
        return []

    prices = [it['price'] for it in matched]

    # 外れ値除去（3件以上の場合）: 中央値の15%未満 or 400%超は除外
    if len(prices) >= 3:
        med = median(prices)
        prices = [p for p in prices if med * 0.15 <= p <= med * 4.0] or prices

    lo  = min(prices)
    hi  = max(prices)
    med = round(median(prices))
    url = matched[0]['url']  # 代表URL（最初にマッチしたもの）

    logger.info(
        f'  OK {name}: {len(matched)} 件 最安¥{lo:,} 中央値¥{med:,} 最高¥{hi:,}'
    )

    return [
        {'date': TODAY, 'product_name': name, 'store': 'ヤフオク 最安', 'price': lo,  'jan': '', 'url': url},
        {'date': TODAY, 'product_name': name, 'store': 'ヤフオク 中央値', 'price': med, 'jan': '', 'url': url},
        {'date': TODAY, 'product_name': name, 'store': 'ヤフオク 最高', 'price': hi,  'jan': '', 'url': url},
    ]


# ── CSV 書き込み ──────────────────────────────────────────────────────

def save_to_csv(records: list[dict]) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    write_header = not DATA_FILE.exists() or DATA_FILE.stat().st_size == 0

    # 価格変化があった商品のみ追記
    last_price: dict[tuple, str] = {}
    if DATA_FILE.exists():
        with open(DATA_FILE, newline='', encoding='utf-8') as f:
            for row in csv.DictReader(f):
                last_price[(row['product_name'], row['store'])] = row['price']

    new_records = [
        r for r in records
        if last_price.get((r['product_name'], r['store'])) != str(r['price'])
    ]

    if not new_records:
        logger.info('価格変化なし — 追記スキップ')
        return

    with open(DATA_FILE, 'a', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        if write_header:
            writer.writeheader()
        writer.writerows(new_records)

    logger.info(f'CSV に {len(new_records)} 件追記（価格変化あり）')


# ── エントリポイント ──────────────────────────────────────────────────

def _already_scraped_today() -> bool:
    """マーカーファイルで今日実行済みか判定"""
    if os.environ.get('SEDORI_FORCE_SCRAPE') == '1':
        logger.info('SEDORI_FORCE_SCRAPE=1 のため今日分も再取得します')
        return False
    return SCRAPE_MARKER.exists() and SCRAPE_MARKER.read_text(encoding='utf-8').strip() == TODAY

def _mark_scraped_today() -> None:
    SCRAPE_MARKER.write_text(TODAY, encoding='utf-8')


async def main() -> None:
    logger.info(f'=== ヤフオク落札価格収集開始 {TODAY} (過去7日: {CUTOFF}〜) ===')

    if _already_scraped_today():
        logger.info('今日分データ取得済み — スキップ')
        return

    targets = [
        p for p in ALL_PRODUCTS
        if p.get('category') not in SKIP_CATEGORIES
    ]
    logger.info(f'対象: {len(targets)} 商品')

    all_records: list[dict] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent=(
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/124.0.0.0 Safari/537.36'
            ),
            locale='ja-JP',
            timezone_id='Asia/Tokyo',
            viewport={'width': 1280, 'height': 900},
        )
        page = await ctx.new_page()

        for i, product in enumerate(targets, 1):
            name     = product['name']
            keywords = product.get('keywords', [name])
            query    = build_query(name)
            logger.info(f'[{i:3}/{len(targets)}] {name}  (検索: {query})')

            records = await scrape_product_yahoo(
                page, name, query, keywords,
                min_price=PRICE_FLOORS.get(name, 0),
                max_price=PRICE_CAPS.get(name, 0),
            )
            all_records.extend(records)

            # 20件ごとに中間保存
            if i % 20 == 0:
                save_to_csv(all_records)
                all_records = []
                logger.info(f'      ── 中間保存 ({i}/{len(targets)}) ──')

            await asyncio.sleep(random.uniform(1.0, 2.0))

        await browser.close()

    save_to_csv(all_records)
    _mark_scraped_today()
    logger.info('=== 完了 ===')


if __name__ == '__main__':
    asyncio.run(main())
