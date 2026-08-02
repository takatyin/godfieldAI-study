"""カードの属性を、そのままネットワークに渡せる固定テーブルにする。

【なぜ必要か】

観測に入っているのはカードIDだけで、値段も攻撃力も入っていません。294枚それぞれが
何をするカードなのかを、勝ち負けの報酬だけから再発見する必要がありました。
37M ステップ学習したモデルを実測すると、

  - 売るフェイズで選ぶカードの平均価格 6.0
    （ランダムに選んだ場合 6.2 / 最も高いものを選べば 16.7）
  - 主行動で選ぶ武器の平均攻撃力 7.1
    （ランダム 7.1 / 最も強いものを選べば 11.7）

と、値段も攻撃力もまったく使えていませんでした。人手の戦略は
`feature(cid, "price")` を直接読んで指しているので、これは賢さの差ではなく
知識の差です。

【閾値を表しやすい形にする】

人が書く戦略は「値段15円以上なら売る」「所持金10円以上なら買う」のように閾値で
できています。生のスカラーを線形層に通すと、閾値は重み・バイアス・非線形の
組み合わせで作ることになり、学習に時間がかかります。

そこで各数値には **温度計符号（thermometer encoding）** を併記します。
`値 >= 15` がそのまま1つの次元になるので、閾値ルールは重み1つで表せます。
生の値も残してあるので、連続的な大小比較（どちらの武器が強いか）もできます。

【欠損と0の区別】

`price` は 264/294 枚、`attack_power` は 157/294 枚にしかありません。
「攻撃力0の防具」と「攻撃力という概念が無いカード」は別物なので、
値が存在するかどうかのフラグを別に立てます。

【テーブルはチェックポイントに保存しない】

カードマスタから決まる派生データなので、モデルには保存せず読み込み時に作り直します
（`persistent=False`）。カードマスタを増減させると次元が変わり、古いモデルの
読み込みは重みの形が合わずに失敗します（黙って別の意味の特徴で動くよりは良い）。
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np

from godfield_rl.cards import all_cards
from godfield_rl.feature_config import NUM_CARD_TYPES

# カードマスタに実在する値。想定外の値が来たら黙って落とさず気付けるよう、
# ここに列挙したものだけを受け付ける。
CARD_TYPES = ("deal", "defense", "devil", "guardian", "miracle", "phenomena",
              "sundry", "weapon")
ELEMENTS = ("火", "水", "木", "土", "光", "闇")
USAGE_TIMINGS = ("main_atk_phase", "main_miracle_phase", "main_sundry_phase",
                 "main_deal_phase", "atk_plus_phase", "miracle_plus_phase",
                 "atk_defence_phase", "miracle_defence_phase", "guardian_phase")
REACTION_TYPES = ("block", "bounce", "reflect")
HIT_CURSES = ("cold", "dark cloud", "dream", "flash", "fog", "heaven", "hell")

# (フィールド名, 正規化の分母, 温度計の閾値)
#
# 閾値は人手の戦略が使っている境目（値段15円、など）と、実データの分位点から選ぶ。
# 細かくしすぎても次元が増えるだけなので、意味のある境目に絞る。
NUMERIC_FIELDS = (
    ("price", 30.0, (1, 3, 5, 10, 15, 20, 25)),
    ("attack_power", 50.0, (1, 3, 5, 8, 10, 12, 15, 20)),
    ("defense_power", 30.0, (1, 3, 6, 9, 12, 15)),
    ("mp_cost", 30.0, (3, 5, 8, 10, 15)),
    ("accuracy", 100.0, (50, 75, 100)),
    ("drop_rate", 20.0, (1, 2, 5, 10, 20)),
)


def thermometer(value: float, edges: tuple[int, ...]) -> list[float]:
    """`値 >= 閾値` を閾値ごとに1次元ずつ並べます。

    one-hot だと「15円以上」を表すのに複数の次元の和が要りますが、
    こちらは1次元で済むため、閾値のルールを線形層が直接表せます。
    """
    return [1.0 if value >= e else 0.0 for e in edges]


def feature_names() -> list[str]:
    """テーブルの各列の名前。診断とテストのために公開しています。"""
    names: list[str] = []
    for field, _, edges in NUMERIC_FIELDS:
        names.append(f"has_{field}")
        names.append(f"{field}_norm")
        names += [f"{field}>={e}" for e in edges]
    names += [f"type={t}" for t in CARD_TYPES]
    names.append("has_element")
    names += [f"element={e}" for e in ELEMENTS]
    names += [f"timing={t}" for t in USAGE_TIMINGS]
    names.append("is_group_attack")
    names += [f"reaction={r}" for r in REACTION_TYPES]
    names += [f"curse={c}" for c in HIT_CURSES]
    return names


def _row(card: dict) -> list[float]:
    out: list[float] = []

    for field, scale, edges in NUMERIC_FIELDS:
        raw = card.get(field)
        if raw is None:
            # 「攻撃力0」と「攻撃力という概念が無い」を区別する
            out.append(0.0)
            out.append(0.0)
            out += [0.0] * len(edges)
            continue
        value = float(raw)
        out.append(1.0)
        out.append(value / scale)
        out += thermometer(value, edges)

    card_type = card.get("type")
    if card_type not in CARD_TYPES:
        raise ValueError(
            f"未知のカード種別 {card_type!r}（{card.get('name')}）。"
            f" card_features.CARD_TYPES に追加してください。"
        )
    out += [1.0 if card_type == t else 0.0 for t in CARD_TYPES]

    element = card.get("element")
    if element is not None and element not in ELEMENTS:
        raise ValueError(f"未知の属性 {element!r}（{card.get('name')}）")
    out.append(0.0 if element is None else 1.0)
    out += [1.0 if element == e else 0.0 for e in ELEMENTS]

    timings = card.get("usage_timing") or []
    for t in timings:
        if t not in USAGE_TIMINGS:
            raise ValueError(f"未知の使用タイミング {t!r}（{card.get('name')}）")
    out += [1.0 if t in timings else 0.0 for t in USAGE_TIMINGS]

    out.append(1.0 if card.get("is_group_attack") else 0.0)

    reaction = card.get("reaction_type")
    if reaction is not None and reaction not in REACTION_TYPES:
        raise ValueError(f"未知のリアクション {reaction!r}（{card.get('name')}）")
    out += [1.0 if reaction == r else 0.0 for r in REACTION_TYPES]

    curse = card.get("hit_curse")
    if curse is not None and curse not in HIT_CURSES:
        raise ValueError(f"未知の付与状態 {curse!r}（{card.get('name')}）")
    out += [1.0 if curse == c else 0.0 for c in HIT_CURSES]

    return out


@lru_cache(maxsize=1)
def card_attribute_table() -> np.ndarray:
    """`(NUM_CARD_TYPES + 1, 特徴数)` の float32 テーブル。

    行0は空スロット（CARD_EMPTY）用の全ゼロです。カード ID `i` は行 `i + 1` に
    対応します。埋め込みが `padding_idx=0` のために +1 ずらしているのと同じ規約です。
    """
    names = feature_names()
    table = np.zeros((NUM_CARD_TYPES + 1, len(names)), dtype=np.float32)
    for card in all_cards():
        row = _row(card)
        if len(row) != len(names):
            raise AssertionError(
                f"特徴の数が feature_names() と一致しません: {len(row)} != {len(names)}"
            )
        table[int(card["id"]) + 1] = row
    return table


@lru_cache(maxsize=1)
def standardized_card_attribute_table() -> np.ndarray:
    """ネットワークに渡す版。列ごとに平均0・標準偏差1へ揃えます。

    【なぜ生の表をそのまま渡してはいけないか】

    生の表は「ほぼ全カードで同じ値」の列を多く含みます（`has_drop_rate` は
    294枚すべてで 1.0、`drop_rate>=1` もほぼ全部、など。標準偏差 0.15 未満の列が
    81本中25本）。この共通成分はカードを区別する情報を持たないのに、射影すると
    **全カードトークンに同じベクトルが足される**ことになります。実測で

        共通成分のノルム 2.42 / カード固有成分のノルム 2.64

    と、情報を持たない側が固有成分と同じ大きさを占めていました。

    定数が乗ると ReLU 前の分布が偏ってユニットが死に、局面ごとの変動が薄まります。
    実測した被害は次のとおりです。

        |                    | 属性なし(v3) | 生の表(v4) |
        | 常にゼロのユニット |    0 / 256   | 134 / 256  |
        | 局面ごとのばらつき |     0.508    |    0.158   |

    方策が局面を区別できなくなり、approx_kl が 0.002（前回 0.02〜0.05）まで落ちて
    50M ステップまわしても学習が進まず、対 strategic の勝率は 44.9% から 21.0% へ
    落ちました。

    列ごとに中心化すれば共通成分は消え（実測 2.42 -> 0.00）、標準偏差で割れば
    どの属性も同じ土俵に乗ります。定数列（標準偏差0）はゼロになり何も足しません。

    行0（空スロット）は統計から除外したうえでゼロのままにします。埋め込みの
    `padding_idx=0` と同じ規約を保つためです。
    """
    raw = card_attribute_table()
    real = raw[1:]  # 行0は空スロット用なので統計に混ぜない
    mean = real.mean(axis=0)
    std = real.std(axis=0)
    # 定数列は割ると 0/0 になる。1 で割って中心化だけ効かせれば全ゼロになる。
    std = np.where(std < 1e-6, 1.0, std)

    table = np.zeros_like(raw)
    table[1:] = (real - mean) / std
    return table.astype(np.float32)


def card_attr_dim() -> int:
    """カード属性の特徴数。"""
    return len(feature_names())
