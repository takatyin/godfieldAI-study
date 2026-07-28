"""観測ベクトルのレイアウトが、C++の Observation 構造体と一致していることの検証。

C++ の `Observation` と `godfield_rl/feature_config.py` のオフセット表は二重管理で、
ズレても例外は起きません。特徴抽出器が別のフィールドを読み始めるだけなので、
**学習の精度が落ちるという形でしか現れず、気付くのが極めて難しい**種類の不具合です。

【このファイルが独立している理由】
これらの検証は元々 tests/test_rl_pipeline.py にありましたが、同ファイルは冒頭で
torch を import します。CI は torch（CUDA版・約3GB）を入れないためそのファイルを
丸ごと除外しており、結果として「最も静かに壊れる箇所」だけが CI で検証されない
状態になっていました。ここは godfield_core と feature_config しか使わないので、
学習まわりの依存が無い環境でも実行できます。

VecEnv や特徴抽出器そのものの検証は引き続き tests/test_rl_pipeline.py にあります。
"""

import godfield_core
from godfield_rl import feature_config as fc


def test_block_lengths_come_from_the_core_module():
    """観測ブロックの長さがすべてC++側の定数から来ていることを検証します。

    Python 側に数値をコピーすると、種別が1つ増えただけで以降のスライス位置が
    全部ズレます。
    """
    assert fc.ACTION_SPACE_SIZE == godfield_core.ACTION_SPACE_SIZE
    assert fc.MAX_HAND_SIZE == godfield_core.MAX_HAND_SIZE
    assert fc.HISTORY_LENGTH == godfield_core.HISTORY_LENGTH
    assert fc.NUM_SICKNESS_TYPES == godfield_core.NUM_SICKNESS_TYPES
    assert fc.NUM_CURSE_TYPES == godfield_core.NUM_CURSE_TYPES
    assert fc.NUM_GUARDIAN_TYPES == godfield_core.NUM_GUARDIAN_TYPES
    assert fc.NUM_PHASES == godfield_core.NUM_PHASES
    assert fc.EVENT_SIZE == godfield_core.EVENT_SIZE


def test_total_feature_size_matches_the_core_observation():
    """マスクを除いた特徴量サイズが、C++が報告する値と一致することを検証します。

    ブロック長を個別に確認していても、順序や漏れがあれば合計がズレます。
    ここが最終的な砦です。
    """
    expected = godfield_core.OBSERVATION_FEATURE_SIZE - godfield_core.ACTION_SPACE_SIZE
    assert fc.TOTAL_OBSERVATION_FEATURE_SIZE_NO_MASK == expected


def test_card_id_blocks_are_contiguous():
    """カードIDの4ブロック（自分の手札・仮置き・相手の手札・相手の仮置き）が
    隙間なく並んでいることを検証します。

    特徴抽出器はこの4ブロックをまとめて1回の埋め込み参照で処理するため、
    間に別の特徴が入ると連続値がカードIDとして解釈されます。
    """
    assert fc.STAGED_CARDS_START == fc.HAND_CARDS_START + fc.MAX_HAND_SIZE
    assert fc.OPP_HAND_CARDS_START == fc.STAGED_CARDS_START + fc.MAX_HAND_SIZE
    assert fc.OPP_STAGED_CARDS_START == fc.OPP_HAND_CARDS_START + fc.MAX_HAND_SIZE
    assert fc.HISTORY_START == fc.OPP_STAGED_CARDS_START + fc.MAX_HAND_SIZE


def test_embedding_table_covers_every_card_in_the_registry():
    """埋め込みテーブルの語彙数が、実際に存在するカード枚数以上であることを検証します。

    カードが追加されて NUM_CARD_TYPES を超えると、特徴抽出器の clamp によって
    別のカードとして扱われます。これも例外は出ず、静かに精度が落ちるだけです。
    """
    registry_size = godfield_core.get_registry_size()
    assert registry_size > 0, "カードマスタが読み込まれていません（conftest の初期化を確認）"
    assert fc.NUM_CARD_TYPES >= registry_size, (
        f"カードが {registry_size} 枚あるのに埋め込みは {fc.NUM_CARD_TYPES} 語彙しかありません"
    )
