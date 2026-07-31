"""守護神の名前が、C++ の GuardianType と一対一で対応していること。

表示用の配列とログ用の辞書が別々にあり、配列のほうが4番以降ずれていた。
画面に「冥王星神」と出ているのに実際は金星神が小銭ばらまきを使う、という
食い違いが起きていた（配列の8番が冥王星神、C++ の 8 は VENUS）。

例外は出ず、対戦中に気づくしかない類の不具合なので、ここで固定する。
"""

import pytest

import godfield_core
from visualizer.constants import GUARDIAN_DICT, GUARDIAN_NAMES

# C++ の enum 名と日本語名の対応。どちらかを変えたらここも直す必要がある。
EXPECTED = {
    "NONE": "なし",
    "MARS": "火星神",
    "MERCURY": "水星神",
    "JUPITER": "木星神",
    "SATURN": "土星神",
    "URANUS": "天王神",
    "PLUTO": "冥王神",
    "NEPTUNE": "海王神",
    "VENUS": "金星神",
    "EARTH": "地球神",
    "MOON": "月神",
}


def guardian_members() -> dict[str, int]:
    return {
        name: int(getattr(godfield_core.GuardianType, name))
        for name in dir(godfield_core.GuardianType)
        if not name.startswith("_") and name not in ("name", "value")
    }


@pytest.mark.parametrize("enum_name,japanese", EXPECTED.items())
def test_each_guardian_maps_to_the_right_name(enum_name, japanese):
    value = int(getattr(godfield_core.GuardianType, enum_name))
    assert GUARDIAN_DICT[value] == japanese, (
        f"GuardianType.{enum_name}（値 {value}）が {GUARDIAN_DICT[value]} になっています"
    )


def test_venus_is_the_one_that_scatters_coins():
    """実際に食い違っていた組み合わせ。小銭ばらまきは金星神の行動。"""
    venus = int(godfield_core.GuardianType.VENUS)
    assert GUARDIAN_DICT[venus] == "金星神"
    assert GUARDIAN_NAMES[venus] == "金星神"


def test_display_list_and_log_dict_agree():
    """表示用の配列とログ用の辞書がずれていないこと。"""
    for value, name in GUARDIAN_DICT.items():
        assert GUARDIAN_NAMES[value] == name


def test_every_enum_member_has_a_name():
    missing = [n for n, v in guardian_members().items() if v not in GUARDIAN_DICT]
    assert not missing, f"名前の無い守護神があります: {missing}"


def test_no_extra_names():
    """使われていない名前が残っていないこと（以前は存在しない地殻神が入っていた）。"""
    values = set(guardian_members().values())
    extra = [f"{v}:{GUARDIAN_DICT[v]}" for v in GUARDIAN_DICT if v not in values]
    assert not extra, f"C++ に存在しない守護神が入っています: {extra}"


def test_count_matches_the_engine():
    assert len(GUARDIAN_DICT) == godfield_core.NUM_GUARDIAN_TYPES
    assert len(GUARDIAN_NAMES) == godfield_core.NUM_GUARDIAN_TYPES
