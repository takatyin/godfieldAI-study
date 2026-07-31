import json
import os

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
json_path = os.path.join(project_root, "assets", "godfield_cards.json")
with open(json_path, encoding="utf-8") as f:
    CARDS = json.load(f)

CARDS_BY_ID = {c["id"]: c for c in CARDS}

# Sickness names for observation state
SICKNESS_NAMES = ["なし", "風邪", "熱病", "地獄病", "天国病"]
SICKNESS_DICT = {1: "風邪", 2: "熱病", 3: "地獄病", 4: "天国病"}

# Guardian names for observation state
# 守護神の名前。並びは C++ の GuardianType と一対一で対応させること。
#
# 以前は同じものを表す配列と辞書が別々にあり、配列のほうが4番以降ずれていた。
# 表示は配列、ログは辞書を使っていたため、画面に「冥王星神」と出ているのに
# 実際は金星神が小銭ばらまきを使う、という食い違いが起きていた
# （配列の8番が冥王星神、C++ の 8 は VENUS）。
GUARDIAN_DICT = {
    0: "なし",
    1: "火星神", 2: "水星神", 3: "木星神", 4: "土星神", 5: "天王神",
    6: "冥王神", 7: "海王神", 8: "金星神", 9: "地球神", 10: "月神",
}

# 添字で引きたい場所のための派生。辞書を唯一の定義とし、二重管理しない。
GUARDIAN_NAMES = [GUARDIAN_DICT[i] for i in range(len(GUARDIAN_DICT))]

# Curse names for observation state
CURSE_NAMES = ["霧", "閃光", "暗雲", "夢"]
CURSE_DICT = {1: "霧", 2: "閃光", 3: "暗雲", 4: "夢"}

PHENOMENA_MESSAGES = [
    "夕焼けが発生！（全員熱病）",
    "濃霧が発生！（全員霧）",
    "きのこが大発生した！",
    "竜巻が発生！（全員HPが1になった）",
    "巨大なタライが降ってきた！",
    "ブラックホールが発生した！",
    "暖流が発生した！（HP+50）",
    "金山が発見された！（お金を独占）",
    "磁気嵐が発生した！（手札が入れ替わった）",
    "日食が発生した！（守護神が降臨した）"
]
