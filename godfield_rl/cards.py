"""カードマスタの読み込みと参照。

カードの属性（攻撃力・防御力・値段・種別）は C++ の registry にも入っていますが、
Python からは名前しか引けません。方策の実装やツールでは値が要るので、
ここで JSON を1度だけ読んで共有します。

以前は同じ読み込みが env_wrapper / visualizer / tools / tests に散っていました。
`init_game_logic` の呼び出しも兼ねるので、どこから import しても登録簿が
初期化済みであることが保証されます（読み込み済みなら何もしません）。
"""

from __future__ import annotations

import json
import os
from functools import lru_cache

import godfield_core

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARDS_JSON = os.path.join(PROJECT_ROOT, "assets", "godfield_cards.json")


@lru_cache(maxsize=1)
def all_cards() -> list[dict]:
    """カードマスタ全件。副作用として C++ 側の登録簿も初期化します。"""
    with open(CARDS_JSON, encoding="utf-8") as f:
        cards = json.load(f)
    if godfield_core.get_registry_size() == 0:
        godfield_core.init_game_logic(cards)
    return cards


@lru_cache(maxsize=1)
def _by_name() -> dict[str, dict]:
    return {c["name"]: c for c in all_cards()}


@lru_cache(maxsize=1)
def _by_id() -> dict[int, dict]:
    return {c["id"]: c for c in all_cards()}


def card_id(name: str) -> int:
    """カード名からIDを引きます。名前が存在しなければ例外にします。

    黙って落とすと「戦略で名指ししたカードが1枚も対象にならない」まま動いてしまい、
    方策が意図と違う挙動をしていても気付けません。
    """
    card = _by_name().get(name)
    if card is None:
        raise KeyError(
            f"カード『{name}』が assets/godfield_cards.json にありません。"
            f" 表記を確認してください（例: 奇跡は ＜炎＞ のように山括弧つき）"
        )
    return card["id"]


def card_ids(*names: str) -> frozenset[int]:
    """複数のカード名をIDの集合にします。"""
    return frozenset(card_id(n) for n in names)


def card_info(cid: int) -> dict:
    return _by_id().get(int(cid), {})


def feature(cid: int, key: str, default=0):
    value = card_info(cid).get(key, default)
    return default if value is None else value


def card_name(cid: int) -> str:
    return card_info(cid).get("name", f"id{cid}")
