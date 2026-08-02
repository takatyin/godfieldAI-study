"""プールの既定が、スクリプトと設定で一致していることの検証。

`scripts/run_league.sh` の POOL_DIR と `godfield_rl/config.py` の
DEFAULT_POOL_DIR は別々に書かれています。片方だけ更新すると、

  - スクリプト経由 -> 新しいプール
  - train.py 直叩き -> 古いプール

と静かに食い違います。古いプールを掴んだ場合は SelfPlayCallback が起動時に
落ちるので致命傷にはなりませんが、そもそも食い違わないようにします。

実際 league_v5 へ切り替えるときも、run_league.sh は v4、config.py は v3 という
2世代ずれた状態になっていました。
"""

import re
from pathlib import Path

from godfield_rl.cards import PROJECT_ROOT
from godfield_rl.config import DEFAULT_POOL_DIR

ROOT = Path(PROJECT_ROOT)
SCRIPT = ROOT / "scripts" / "run_league.sh"


def script_pool_dir() -> str:
    text = SCRIPT.read_text(encoding="utf-8")
    m = re.search(r'^POOL_DIR="\$\{POOL_DIR:-([^}"]+)\}"', text, re.MULTILINE)
    assert m, f"{SCRIPT.name} から POOL_DIR の既定を読めません（書式が変わった？）"
    return m.group(1)


def test_script_and_config_agree_on_the_pool():
    assert script_pool_dir() == DEFAULT_POOL_DIR, (
        f"プールの既定が食い違っています:\n"
        f"  scripts/run_league.sh : {script_pool_dir()}\n"
        f"  godfield_rl/config.py : {DEFAULT_POOL_DIR}\n"
        f"どちらも同じ世代を指すようにしてください。"
    )


def test_the_pool_is_under_models():
    assert DEFAULT_POOL_DIR.startswith("models/"), (
        f"プールは models/ の下に置いてください: {DEFAULT_POOL_DIR}"
    )


def test_retired_pools_are_documented():
    """使えなくなった世代が、なぜ使えないのかと一緒に残っていること。

    「なぜ v4 を使ってはいけないか」が失われると、うっかり指して
    起動時エラーの原因を追うことになります。
    """
    text = SCRIPT.read_text(encoding="utf-8")
    current = DEFAULT_POOL_DIR.rsplit("_", 1)[-1]  # 例: "v5"
    generation = int(current.lstrip("v"))

    missing = [
        f"v{i}" for i in range(2, generation)
        if not re.search(rf"^#\s+v{i}\s", text, re.MULTILINE)
    ]
    assert not missing, (
        f"{SCRIPT.name} に引退した世代の説明がありません: {missing}\n"
        f"「なぜ読めないのか」を1行ずつ残してください。"
    )
