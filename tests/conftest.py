import json
import os

import pytest

import godfield_core
from tests.core.dsl import Game, Side


@pytest.fixture(scope="session", autouse=True)
def setup_card_registry():
    # Construct absolute path to assets/godfield_cards.json based on project root
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    json_path = os.path.join(project_root, "assets", "godfield_cards.json")

    with open(json_path, encoding="utf-8") as f:
        cards = json.load(f)

    godfield_core.init_game_logic(cards)


@pytest.fixture(autouse=True)
def rng_script_isolation():
    """乱数の指示をテストごとに隔離し、使われなかった指示を失敗として報告します。

    「指示したのに一度も使われなかった」= テストが意図したコードパスが実行されて
    いない、ということなので、静かに通してしまうと中身のないテストになります
    （以前 assert seed is not None だけを検証していたテストがまさにそれでした）。
    ここで機械的に検出します。

    また、指示は thread_local なグローバルに載るため、テスト間の持ち越しを
    防ぐために前後で必ず破棄します。
    """
    godfield_core.rng_clear_script()
    yield
    unconsumed = godfield_core.rng_unconsumed_kinds()
    godfield_core.rng_clear_script()
    if unconsumed:
        pytest.fail(
            "乱数の指示が使われませんでした: " + ", ".join(unconsumed) + "\n"
            "指定した確率判定が一度も行われていないため、このテストは意図した"
            "コードパスを検証できていません。盤面の前提か操作手順を見直してください。"
        )


@pytest.fixture
def board():
    """宣言的に盤面を組み立てて Game を返すファクトリ。

        def test_x(board):
            g = board(p0=Side(hand=["weapons/punch"]), p1=Side(hp=40))
            g.attack("weapons/punch")
            g.expect(p1_hp=...)
    """

    def _make(p0: Side | None = None, p1: Side | None = None, **kwargs) -> Game:
        return Game(p0, p1, **kwargs)

    return _make
