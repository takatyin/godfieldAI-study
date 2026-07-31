"""カードマスタの読み込みが1箇所に集約されていること。

`init_game_logic` はプロセス全体のグローバルを書き換えます。どこかが独自に
読み込んで差し替えると、他のテストや実行時のカードIDが黙ってずれます。

実際 `tests/rl/test_transformer.py` が import 時にダミー1枚で登録簿を
上書きしており、テストをディレクトリに分けて実行順が変わった途端に
486 件が「カードID 118 が存在しない」で落ちました。単体では通るので、
実行順が変わるまで気付けない類の事故です。
"""

import re
from pathlib import Path

import pytest

import godfield_core
from godfield_rl.cards import CARDS_JSON, PROJECT_ROOT, all_cards

# 読み込みと初期化を担う唯一の場所
LOADER = Path("godfield_rl/cards.py")

SEARCH_DIRS = ("godfield_rl", "tools", "visualizer", "tests")


def python_files() -> list[Path]:
    root = Path(PROJECT_ROOT)
    files = [p for d in SEARCH_DIRS for p in (root / d).rglob("*.py")]
    files += [root / "visualize_server.py", root / "train.py"]
    return [p for p in files if p.exists() and "__pycache__" not in p.parts]


def test_registry_holds_the_real_card_master():
    """登録簿が実データで初期化されていること（ダミーに差し替わっていない）。"""
    assert godfield_core.get_registry_size() == len(all_cards())
    assert godfield_core.get_registry_size() > 200, "ダミーの登録簿になっています"


def test_only_the_loader_initialises_the_registry():
    """init_game_logic を呼ぶのは godfield_rl/cards.py だけであること。"""
    root = Path(PROJECT_ROOT)
    offenders = [
        str(p.relative_to(root)).replace("\\", "/")
        for p in python_files()
        if p.relative_to(root) != LOADER
        and re.search(r"^\s*godfield_core\.init_game_logic\(", p.read_text(encoding="utf-8"),
                      re.MULTILINE)
    ]
    assert not offenders, (
        "init_game_logic はプロセス全体のグローバルを書き換えます。"
        f"godfield_rl/cards.py の all_cards() を使ってください: {offenders}"
    )


def test_only_the_loader_reads_the_card_json():
    """カードマスタの JSON を直接開くのも1箇所だけであること。

    別に読むと、C++ 側の登録簿を初期化しないまま進む経路ができます。

    例外は2つ。
      tests/core/dsl.py     … torch を入れずに動かすため独立している
      tools/validate_cards.py … カードマスタ自体を検証する。共通の読み込みを
                                通すと、検証したい壊れ方で先に落ちてしまう
    """
    root = Path(PROJECT_ROOT)
    allowed = {LOADER, Path("tests/core/dsl.py"), Path("tools/validate_cards.py")}
    offenders = [
        str(p.relative_to(root)).replace("\\", "/")
        for p in python_files()
        if p.relative_to(root) not in allowed
        and "godfield_cards.json" in p.read_text(encoding="utf-8")
        and re.search(r"json\.load", p.read_text(encoding="utf-8"))
    ]
    assert not offenders, f"カードマスタを直接読んでいます: {offenders}"


def test_loader_is_idempotent():
    """何度呼んでも登録簿が壊れないこと。"""
    before = godfield_core.get_registry_size()
    all_cards()
    all_cards()
    assert godfield_core.get_registry_size() == before


def test_card_json_path_exists():
    assert Path(CARDS_JSON).is_file()


@pytest.mark.parametrize("name", ["パンチ", "＜氷＞", "神の盾"])
def test_known_cards_are_present(name):
    """登録簿がダミーだとここで落ちる。"""
    assert any(c["name"] == name for c in all_cards())
