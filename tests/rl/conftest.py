"""学習まわりのテストは、torch と sb3-contrib が入っていなければ収集しません。

CI は CUDA 版 torch（約3GB）を落とさないために、これらを入れずに動かしています
（`.github/workflows/ci.yml` の `uv sync --no-install-package torch ...`）。

以前は除外するファイル名を CI 側に列挙していましたが、テストを追加したり
ディレクトリを移動したりするたびに指定が外れて CI が落ちました
（`--ignore=tests/test_rl_pipeline.py` が、ファイルを tests/rl/ へ移した時点で
効かなくなった）。必要な依存はテスト側が知っているので、ここで宣言します。
CI 側の設定を変えなくても、このディレクトリにテストを足せます。

import が失敗する以上スキップではなく**収集そのものを止める**必要があります
（モジュールの先頭で torch を import しているため、skip マーカーでは間に合わない）。
"""

REQUIRED = ("torch", "sb3_contrib", "stable_baselines3", "gymnasium")


def _missing_packages() -> list[str]:
    missing = []
    for name in REQUIRED:
        try:
            __import__(name)
        except ImportError:
            missing.append(name)
    return missing


_MISSING = _missing_packages()

# 依存が欠けていれば、このディレクトリの中身を丸ごと収集対象から外す
collect_ignore_glob = ["test_*.py"] if _MISSING else []


def pytest_report_header(config) -> str | None:  # noqa: ARG001
    """飛ばした場合は理由を出力の先頭に出す。黙って0件になるのを防ぐ。"""
    if _MISSING:
        return (
            f"tests/rl は収集しません（未インストール: {', '.join(_MISSING)}）。"
            " 学習まわりを変更した場合はローカルで実行してください。"
        )
    return None
