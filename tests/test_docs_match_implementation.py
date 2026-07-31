"""文書が実装と食い違っていないことを機械的に確かめる。

文書は放置すると必ず腐ります。実際、実装前に書かれた設計方針が
「行動空間21次元」「batch_size 16384」のまま残っており、どちらも
現在の値（122 / 2048）と違っていました。

人が読んで気付くのを期待するのではなく、機械で照合できる部分は
機械に任せます。ここで見るのは以下の3つです。

1. Markdown のリンク先が実在するか
2. 文書に書かれた定数が constants.h と一致するか
3. 守護神の行動カードと攻撃力がカードマスタと一致するか
"""

import re
from pathlib import Path

import pytest

from godfield_rl.cards import PROJECT_ROOT, all_cards, card_name

ROOT = Path(PROJECT_ROOT)
DOC_DIRS = [ROOT / "docs", ROOT / ".agents"]
DOCS = sorted(p for d in DOC_DIRS for p in d.glob("*.md")) + [ROOT / "README.md"]


def constants() -> dict[str, int]:
    text = (ROOT / "godfield_core" / "src" / "constants.h").read_text(encoding="utf-8")
    return {
        m.group(1): int(m.group(2))
        for m in re.finditer(r"constexpr\s+\w+\s+(\w+)\s*=\s*(\d+)", text)
    }


@pytest.mark.parametrize("doc", DOCS, ids=lambda p: p.name)
def test_markdown_links_resolve(doc: Path):
    """文書間のリンクが切れていないこと。

    ファイルを消したり移動したりすると真っ先に腐るのがここです。
    """
    text = doc.read_text(encoding="utf-8")
    missing = []
    for target in re.findall(r"\]\(((?:\.\./|\./)?[\w/.-]+\.(?:md|py|json|yaml|sh))\)", text):
        if not (doc.parent / target).resolve().exists():
            missing.append(target)
    assert not missing, f"{doc.name} のリンクが切れています: {missing}"


def test_guardian_actions_match_the_card_master():
    """rules.md の守護神一覧が、カードマスタの攻撃力と一致すること。"""
    cards = {c["name"]: c for c in all_cards()}
    text = (ROOT / "docs" / "rules.md").read_text(encoding="utf-8")

    checked, problems = 0, []
    for line in text.splitlines():
        guardian = re.match(r"\| \*\*([^ (|]+)", line)
        if guardian is None:
            continue
        for _pct, name, atk in re.findall(
            r"・(\d+)%:\s*([^\s(（]+)\s*[(（]?ATK\s*(\d+)?", line
        ):
            checked += 1
            card = cards.get(name)
            if card is None:
                problems.append(f"{guardian.group(1)}: 『{name}』がカードマスタに無い")
            elif atk and int(atk) != (card.get("attack_power") or 0):
                problems.append(
                    f"{name}: 文書 ATK {atk} / 実装 {card.get('attack_power') or 0}"
                )

    assert checked >= 25, f"守護神の記述を {checked} 件しか拾えていません（正規表現の劣化）"
    assert not problems, "rules.md と実装が食い違っています:\n  " + "\n  ".join(problems)


def test_guardian_action_probabilities_match():
    """行動確率 30/25/20/15/10 が文書と実装で一致すること。"""
    src = (ROOT / "godfield_core" / "src" / "combat_resolution.cpp").read_text(encoding="utf-8")
    m = re.search(r"GUARDIAN_ACTION_PERCENT\[[^\]]*\]\s*=\s*\{([^}]*)\}", src)
    assert m, "実装から GUARDIAN_ACTION_PERCENT を読めません"
    impl = [int(x) for x in re.findall(r"\d+", m.group(1))]

    text = (ROOT / "docs" / "rules.md").read_text(encoding="utf-8")
    for line in text.splitlines():
        pcts = [int(p) for p in re.findall(r"・(\d+)%:", line)]
        if pcts:
            assert pcts == impl, f"文書の確率 {pcts} が実装 {impl} と違います"


def test_documented_guardian_cards_exist():
    """実装が参照する守護神の行動カードが、すべてカードマスタにあること。"""
    src = (ROOT / "godfield_core" / "src" / "combat_resolution.cpp").read_text(encoding="utf-8")
    ids = (ROOT / "godfield_core" / "src" / "generated_card_ids.h").read_text(encoding="utf-8")
    id_by_macro = {
        m.group(1): int(m.group(2))
        for m in re.finditer(r"constexpr int (ID_\w+)\s*=\s*(\d+)", ids)
    }
    names = {c["name"] for c in all_cards()}

    used = set()
    for m in re.finditer(r"(?:static const|constexpr) int \w+_ACTIONS\[\d*\]\s*=\s*\{([^}]*)\}", src):
        used.update(re.findall(r"ID_\w+", m.group(1)))
    assert used, "実装から守護神の行動カード配列を読めません"

    unknown = [x for x in used if card_name(id_by_macro[x]).startswith("id")]
    assert not unknown, f"カードマスタに無いIDを参照しています: {unknown}"
    assert all(card_name(id_by_macro[x]) in names for x in used)


@pytest.mark.parametrize(
    "const_name",
    ["INITIAL_HP", "MAX_HAND_SIZE", "APOCALYPSE_TURN", "SUN_AMULET_REVIVE_HP"],
)
def test_key_constants_are_readable(const_name):
    """照合に使う定数が constants.h から読めること。

    定数名を変えたらこのテストが落ちて、文書側の見直しに気付けます。
    """
    assert const_name in constants()
