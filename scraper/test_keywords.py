import sys, importlib
sys.path.insert(0, r'C:\Users\makki\sedori-navi\scraper')
import products, scrape
importlib.reload(products); importlib.reload(scrape)
from scrape import match_product

titles_expected = [
    ('CANON PowerShot G7 X Mark III PowerShot 30th Anniversary Edition', 'G7X Mark III 30th Anniversary'),
    ('CANON PowerShot IXY 650 m [ブラック] 25年', 'IXY 650 m ブラック'),
    ('CANON PowerShot IXY 650 m [シルバー]　25年', 'IXY 650 m シルバー'),
    ('デジタルカメラ IXY 650 [ブラック]', 'IXY 650 ブラック'),
    ('デジタルカメラ IXY 650 [シルバー]', 'IXY 650 シルバー'),
    ('PowerShot SX740 HS [ブラック]', 'SX740 ブラック'),
    ('PowerShot SX740 HS [シルバー]', 'SX740 シルバー'),
    ('FUJIFILM X100VI Black 【新型2025】 E/J', 'X100VI ブラック（新）'),
    ('FUJIFILM X100VI Silver 【新型2025】 E/J', 'X100VI シルバー（新）'),
    ('FUJIFILM X100VI [シルバー]', 'X100VI シルバー（旧）'),
    ('FUJIFILM X100VI [ブラック]', 'X100VI ブラック（旧）'),
    ('instax WIDE 400 チェキ [ジェットブラック]', 'instax WIDE 400 ブラック'),
    ('【PRB-02】 THE BEST vol.2', 'PRB-02 THE BEST vol.2'),
    ('【PRB-01】 THE BEST', 'PRB-01 THE BEST'),
]

all_ok = True
for title, expected in titles_expected:
    p = match_product(title)
    got = p['name'] if p else 'NO MATCH'
    ok = (got == expected)
    status = 'OK' if ok else 'NG'
    if not ok:
        all_ok = False
    print(status + ' | expected: ' + expected + ' | got: ' + got)

print()
print('ALL OK!' if all_ok else 'SOME TESTS FAILED')
