# テストの書き方（乱数注入と宣言的DSL）

このリポジトリのテストは `tests/core/dsl.py` の宣言的DSLで書きます。ゲームロジックには
確率で分岐する箇所が30以上あるため、**乱数を固定できることがテストの前提**になっています。

---

## 1. なぜこの仕組みがあるのか

以前は「目的の結果になるシード値を総当たりで探す」方式でした。

```python
# かつてのテスト
for seed in range(100000):
    sim = SimulationRunner()
    sim.state.seed_rng(seed)
    ...
    if 目的の結果:
        break
assert seed is not None   # ← 探索が空振りしても、これだけは通ってしまう
```

この方式には4つの問題がありました。

1. 遅い（最大10万回のシミュレーション）
2. `seed_rng(42)` がどの分岐を意図しているのかコードから読めない
3. C++側の乱数消費順を1つ変えると、無関係なテストが一斉に落ちる
4. **探索が空振りしたテストが「シードが見つかった」だけを検証する空のテストに退化する**

4番は実際に起きていました。`test_earth_dangerous_pestle_mortar` は
「シードが見つかった」以外に何も検証していませんでした。

そこで、乱数を消費する箇所すべてに `RollKind` というラベルを付け、テストから
「この判定はこの値を返せ」と宣言的に指示できるようにしています。

**本番のコスト**: スクリプトは `thread_local` ポインタで保持し、本番では常に `nullptr` です。
追加コストは比較1回（実測 0.096 ns/draw）。詳細は `godfield_core/src/rng.h` を参照。

---

## 2. 基本の書き方

```python
def test_bounce_success_swaps_attacker_and_defender(board):
    """＜弾く＞成功時に攻守が入れ替わり、弾いた本人が無傷であることを検証します。"""
    g = board(
        p0=Side(hp=40, mp=10, hand=["miracles/absorption"]),
        p1=Side(hp=5,  mp=10, hand=["miracles/turbulence"]),
    )
    g.rng.deck_always(FILLER)          # 補充ドローを無害なカードに固定
    g.rng.bounce(success=True)         # ＜弾く＞の50%判定を固定

    g.attack("miracles/absorption")
    g.defend("miracles/turbulence")

    g.expect(attacker=1, defender=0, actor=0, p1_hp=5)
```

- `board(...)` で盤面を宣言する。`Side` の `hand` は**カード名**で書く（IDは書かない）
- `g.rng.*` で確率判定を固定する
- `g.expect(...)` で複数の期待値をまとめて検証する（不一致は全部まとめて報告される）

### 期待値にマジックナンバーを書かない

```python
# 悪い例: なぜ 39 なのか読めない
g.expect(p1_hp=39)

# 良い例: 計算式で書く
damage = card_feature(weapon, "attack_power") - card_feature(armor, "defense_power")
g.expect(p1_hp=40 - damage)
```

カードの性能はマスタ（`assets/cards/*.yaml`）が唯一の定義元です。テストに数値を直書きすると、
性能を変えたときに「どちらが正しいのか」が分からないまま落ちます。

---

## 3. 乱数の指示

### 主なヘルパー

| メソッド | 用途 |
|---|---|
| `g.rng.hits(always=True)` | 命中率判定を必中／必ず外す |
| `g.rng.bounce(success=True)` | ＜弾く＞の成否 |
| `g.rng.guardian_act(acts=True, action=3)` | 守護神が行動するか、5行動のどれか |
| `g.rng.guardian_action_card(SATURN, "gurdians/diamond-axe")` | 行動を**カード名**で指定 |
| `g.rng.moon_miracle("miracles/aura")` | 月神が発動する奇跡 |
| `g.rng.phenomenon(PhenomenonType.MUSHROOM)` | 運命のひもで起きる超常現象 |
| `g.rng.dream(real, disguised=True, as_card=fake)` | 夢の偽装の有無と偽装先 |
| `g.rng.next_draws(a, b, then=c)` | 山札から引く順番 |
| `g.rng.deck_always(card)` | 補充ドローを固定（背景固定用） |
| `g.rng.apocalypse_draws("devils/large-devil", None)` | 終末の時に引く悪魔 |

### 閾値・確率をテストに直書きしない

守護神の行動確率や悪魔の出現率は C++ 側の表から取得します。

```python
percents = godfield_core.get_guardian_action_percents()   # [30, 25, 20, 15, 10]
```

DSLのヘルパーがこれを使って代表値を導出するので、**C++側の確率配分を変えても
テストの書き換えは不要**です。カード名で指定する `guardian_action_card()` も同様で、
表の並び順が変わっても黙って別の行動を検証することがありません。

### センチネル

閾値の向き（`roll < RATE` で成功か、`roll >= accuracy` で失敗か）をテストに
書かせないため、`HAPPENS` / `NEVER` を使います。C++側の判定はすべて
「小さい値ほどイベントが起きる」向きに統一されています。

---

## 4. 未消費検査（最も重要な安全網）

`tests/conftest.py` の autouse フィクスチャが、**指示したのに一度も使われなかった
乱数を検出して失敗させます**。

```
Failed: 乱数の指示が使われませんでした: GUARDIAN_LEAVE
指定した確率判定が一度も行われていないため、このテストは意図したコードパスを
検証できていません。盤面の前提か操作手順を見直してください。
```

これは「テストが意図した経路を通っていない」ことの機械的な検出です。盤面の前提が
崩れて判定に到達しなくなったケースを、静かに通さずに落とします。

**背景固定は `optional=True` を付ける**: 補充ドローのように「起きるかどうかが
テストの主題でない」指示は未消費検査の対象外にします（`deck_always` は自動で付きます）。

---

## 5. 空のテストを書かないために

このリポジトリでは過去に「壊れても落ちないテスト」が11件見つかっています。
以下は実際にあった例です。

| 実例 | 何が問題か |
|---|---|
| `assert hp == 40 or hp == 30` | 弾きの成否どちらでも通る |
| `runner.state.current_turn = 149; assert current_turn < 150` | C++を一度も呼んでいない |
| `mushroom_turns += 6; assert mushroom_turns == 9` | Pythonの足し算を確認しているだけ |
| 「手札が一新される」と書いて `assert card != -1` | 一枚も入れ替わらなくても通る |
| `assert get_mp(0) > 10` | MPが1増えれば通る |

### チェックリスト

- **その検証は、実装を壊したら落ちるか？** 落ちないなら意味がない
- **前提を明示的にアサートしたか？**
  ```python
  assert damage > 0, "被弾0ではダメージが渡ったか検証できない"
  assert card_feature(real, "attack_power") != card_feature(fake, "attack_power"), \
      "真偽で攻撃力が異なる組み合わせでないと、確定処理を検証できない"
  ```
- **`or` でつないだアサーションになっていないか？** どちらでも通るなら、
  乱数を固定して両方を別々に検証する
- **確率的に失敗しうる不変条件を使っていないか？**
  夢の `apparent != true` は50%で成り立ちません。`is_confirmed` で判定します

---

## 6. 局面は実際の操作で作る

`state.current_phase = ...` のように直接代入して局面を組み立てると、
**その局面が実際に発生しうるかが検証されません**。攻撃力や属性が実装と食い違って
いても気付けず、逆に実装のセットアップ処理が壊れても通ります。

```python
# 悪い例: その局面が発生しうるか分からない
g.state.current_phase = GamePhase.PHASE_DEFENSE
g.state.pending_attack_power = 50
g.state.pending_attack_element = Element.ELEM_LIGHT

# 良い例: 実際に発生させる
g.rng.phenomenon(PhenomenonType.GIGANTIC_TUB)
g.attack("sundries/string-of-fate", to_self=True)
g.expect(phase=GamePhase.PHASE_DEFENSE,
         pending_power=card_feature("phenomena/gigantic-tub", "attack_power"))
```

純粋な写像の検証（フェイズ名から表示文言を決める等）だけは直接指定して構いません。

---

## 7. 実行

```bash
uv run pytest
```

`pyproject.toml` の `testpaths` で `tests/` が対象になっています。

C++を変更したら**必ず再ビルドしてからテストする**こと。ビルドは MSVC 環境が要るため、
PowerShell から実行します（Git Bash では失敗します）。

```bash
uv run python setup.py build_ext --inplace
```

型スタブの再生成も忘れずに（`.agents/AGENTS.md` 参照）。

```bash
.\.venv\Scripts\pybind11-stubgen.exe -o . --root-suffix="-stubs" godfield_core
```
