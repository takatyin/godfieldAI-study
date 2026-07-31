"""Custom feature extractor for GodField observations.

Handles categorical card ID features through embedding layers
and combines them with continuous features.
"""
import gymnasium as gym
import torch
import torch.nn as nn
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor

import godfield_core
from godfield_rl.feature_config import (
    CONTINUOUS_FEATURES_SIZE,
    EVENT_SIZE,
    HAND_CARDS_START,
    HAND_KNOWN_TO_OPP_START,
    HISTORY_HEAD_START,
    HISTORY_LENGTH,
    HISTORY_START,
    MAX_HAND_SIZE,
    NUM_CARD_TYPES,
    OPP_DEPLOYED_START,
    OPP_STAGED_CARDS_START,
)

# GameEvent の並びは [actor, event_type, card_id, target_id, value]。
# event_type == NONE(0) は「まだ何も起きていないスロット」を意味する。
EVENT_TYPE_INDEX = 1
EVENT_TYPE_NONE = int(godfield_core.EventType.NONE)


class GodFieldFeatureExtractor(BaseFeaturesExtractor):
    def __init__(self, observation_space: gym.spaces.Box,
                 card_embed_dim: int = 16,
                 features_dim: int = 256):
        super().__init__(observation_space, features_dim)

        # Embedding for card IDs (+1 for CARD_EMPTY mapped to 0)
        self.card_embedding = nn.Embedding(
            num_embeddings=NUM_CARD_TYPES + 1,
            embedding_dim=card_embed_dim,
            padding_idx=0
        )

        # Calculate dimensions
        num_card_slots = (MAX_HAND_SIZE * 4) + HISTORY_LENGTH
        continuous_dim = CONTINUOUS_FEATURES_SIZE + (HISTORY_LENGTH * (EVENT_SIZE - 1)) + 1 # +1 for history_head

        total_input_dim = continuous_dim + (num_card_slots * card_embed_dim)

        # Final projection
        self.linear = nn.Sequential(
            nn.Linear(total_input_dim, features_dim),
            nn.ReLU(),
        )

    def forward(self, observations: torch.Tensor) -> torch.Tensor:
        batch_size = observations.shape[0]

        # Extract continuous features before cards
        cont_features = observations[:, :CONTINUOUS_FEATURES_SIZE]

        # Extract cards (Hand, Staged, Opp Hand, Opp Staged)
        # Shift IDs by +1 so that -1 (CARD_EMPTY) becomes 0
        cards_start = HAND_CARDS_START
        cards_end = OPP_STAGED_CARDS_START + MAX_HAND_SIZE
        card_features = observations[:, cards_start:cards_end].long() + 1

        # Clamp out of bounds just in case
        card_features = torch.clamp(card_features, min=0, max=NUM_CARD_TYPES)

        # Extract history events
        history = observations[:, HISTORY_START:HISTORY_START + HISTORY_LENGTH * EVENT_SIZE]
        history = history.view(batch_size, HISTORY_LENGTH, EVENT_SIZE)

        # History continuous parts
        history_cont = torch.cat([history[:, :, :2], history[:, :, 3:]], dim=2).view(batch_size, -1)

        # History card IDs
        history_cards = history[:, :, 2].long() + 1
        history_cards = torch.clamp(history_cards, min=0, max=NUM_CARD_TYPES)

        # History head
        history_head = observations[:, HISTORY_HEAD_START].unsqueeze(1)

        # Embed all cards
        embedded_cards = self.card_embedding(card_features)
        embedded_cards = embedded_cards.view(batch_size, -1)

        embedded_history_cards = self.card_embedding(history_cards)
        embedded_history_cards = embedded_history_cards.view(batch_size, -1)

        # Concatenate everything
        x = torch.cat([
            cont_features,
            embedded_cards,
            history_cont,
            embedded_history_cards,
            history_head
        ], dim=1)

        return self.linear(x)


class GodFieldTransformerExtractor(BaseFeaturesExtractor):
    """自己注意（Transformer）で観測を要約する特徴抽出器。

    手札・仮置き・履歴を「トークンの列」として扱うので、スロット位置に依存せず
    カードの組み合わせ（例: 武器＋オーラ）や文脈を学べます。先頭に置いた
    グローバルトークンが列全体を要約し、その出力だけを方策へ渡します。

    系列長は `1 + MAX_HAND_SIZE*4 + HISTORY_LENGTH` です。注意は系列長の2乗で
    効くので、HISTORY_LENGTH を増やすときは実測で速度を確認してください。

    【空スロットの扱い】手札・仮置きの空スロットと、まだ何も起きていない履歴は
    注意の対象から外します（key_padding_mask）。外さないと、空きが多い序盤ほど
    「意味のないトークン」に注意が吸われます。カード埋め込みは padding_idx=0 で
    ゼロになりますが、種別・位置の埋め込みを足すため実際には非ゼロになる点に注意。
    """

    def __init__(self, observation_space: gym.spaces.Box,
                 d_model: int = 128,
                 nhead: int = 4,
                 num_layers: int = 2,
                 dim_feedforward: int = 256,
                 dropout: float = 0.0,
                 features_dim: int = 256,
                 grad_checkpointing: bool = False):
        super().__init__(observation_space, features_dim)

        if d_model % nhead != 0:
            raise ValueError(f"d_model({d_model}) は nhead({nhead}) で割り切れる必要があります")

        self.d_model = d_model
        self.num_card_slots = MAX_HAND_SIZE * 4
        self.grad_checkpointing = grad_checkpointing

        # 1. Global context token embedding (Continuous features -> d_model)
        self.global_proj = nn.Linear(CONTINUOUS_FEATURES_SIZE, d_model)

        # 2. Card Embeddings
        # Card ID embedding (includes +1 shift for CARD_EMPTY mapped to 0)
        self.card_embedding = nn.Embedding(NUM_CARD_TYPES + 1, d_model, padding_idx=0)
        # Type embedding: 0=My Hand, 1=My Staged, 2=Opp Hand, 3=Opp Staged
        self.card_type_embedding = nn.Embedding(4, d_model)
        # カードごとの2値属性（相手に見えているか / 展開済みか）をトークンに足すための射影
        self.card_flag_proj = nn.Linear(2, d_model)

        # 3. History Embeddings
        self.hist_cont_proj = nn.Linear(EVENT_SIZE - 1, d_model)
        # Positional Encoding for History timeline (0 = oldest, HISTORY_LENGTH-1 = newest)
        self.history_pos_emb = nn.Embedding(HISTORY_LENGTH, d_model)

        # 4. Transformer Encoder
        #
        # norm_first=True（Pre-LN）にしている。Post-LN は層を深くすると学習の初期に
        # 勾配が不安定になりやすく、warmup を前提にした設定が要る。ここは層数を
        # 増やして試す用途なので、深くしても壊れにくい側を既定にする。
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=dim_feedforward,
            dropout=dropout,
            activation="gelu",
            norm_first=True,
            batch_first=True,
        )
        self.transformer = nn.TransformerEncoder(
            encoder_layer,
            num_layers=num_layers,
            norm=nn.LayerNorm(d_model),
            # Pre-LN では nested tensor の最適化が効かない。既定のままだと
            # 毎回 UserWarning が出るので明示的に切る。
            enable_nested_tensor=False,
        )

        # Final projection from Global Token -> features_dim
        self.final_proj = nn.Sequential(
            nn.Linear(d_model, features_dim),
            nn.ReLU()
        )

    def _encode(self, seq: torch.Tensor, key_padding_mask: torch.Tensor) -> torch.Tensor:
        """Transformer を通します。grad_checkpointing なら層ごとに再計算します。

        逆伝播は連鎖律のために順伝播の途中結果を保持しますが、その量は層数と
        バッチに比例します。勾配チェックポイントは途中結果を捨て、逆伝播の直前に
        その層だけ順伝播をやり直します。保持するのが実質1層分で済む代わりに、
        逆伝播が約1.3倍になります。

        注意そのものは PyTorch が既にメモリ効率カーネル（EFFICIENT_ATTENTION）で
        処理しており、系列長に対して線形です（実測: 系列長2倍でVRAM1.97倍）。
        ここで削れるのは FFN や射影の活性のほうで、そちらが支配的になっています。

        勾配が要らない場面（ロールアウトの推論）では checkpoint を通さないので、
        収集の速度は変わりません。
        """
        if not (self.grad_checkpointing and torch.is_grad_enabled() and seq.requires_grad):
            return self.transformer(seq, src_key_padding_mask=key_padding_mask)

        for layer in self.transformer.layers:
            seq = torch.utils.checkpoint.checkpoint(
                layer, seq, src_key_padding_mask=key_padding_mask,
                # 既定(True)は入力の requires_grad を見て挙動が変わるうえ、
                # autocast の状態を再計算時に引き継がない。
                use_reentrant=False,
            )
        return self.transformer.norm(seq) if self.transformer.norm is not None else seq

    def forward(self, observations: torch.Tensor) -> torch.Tensor:
        batch_size = observations.shape[0]
        device = observations.device

        # 1. Global Token
        cont_features = observations[:, :CONTINUOUS_FEATURES_SIZE]
        global_tokens = self.global_proj(cont_features).unsqueeze(1)  # [B, 1, d_model]

        # 2. Card Tokens
        cards_start = HAND_CARDS_START
        cards_end = OPP_STAGED_CARDS_START + MAX_HAND_SIZE
        # Shape: [B, MAX_HAND_SIZE * 4]
        card_ids = observations[:, cards_start:cards_end].long() + 1
        card_ids = torch.clamp(card_ids, min=0, max=NUM_CARD_TYPES)

        card_embs = self.card_embedding(card_ids) # [B, 36, d_model]

        # Create type indices: 9 of 0s, 9 of 1s, 9 of 2s, 9 of 3s
        type_indices = torch.tensor(
            [0]*MAX_HAND_SIZE + [1]*MAX_HAND_SIZE + [2]*MAX_HAND_SIZE + [3]*MAX_HAND_SIZE,
            device=device
        ).unsqueeze(0).expand(batch_size, -1)
        type_embs = self.card_type_embedding(type_indices) # [B, 36, d_model]

        # カードごとの属性を、そのカードのトークンに足す。グローバルトークン側に
        # まとめて流すとどのカードの属性なのかが失われるので、ここで対応づける。
        #   ch0 … 自分のカードが相手に見えているか（自分の手札ブロックだけ）
        #   ch1 … 相手のカードが展開済みか（相手の手札ブロックだけ）
        # 仮置きの2ブロックには対応する属性が無いので0のまま。
        flags = torch.zeros(batch_size, self.num_card_slots, 2,
                            device=device, dtype=card_embs.dtype)
        flags[:, :MAX_HAND_SIZE, 0] = observations[
            :, HAND_KNOWN_TO_OPP_START : HAND_KNOWN_TO_OPP_START + MAX_HAND_SIZE
        ]
        flags[:, 2 * MAX_HAND_SIZE : 3 * MAX_HAND_SIZE, 1] = observations[
            :, OPP_DEPLOYED_START : OPP_DEPLOYED_START + MAX_HAND_SIZE
        ]

        card_tokens = card_embs + type_embs + self.card_flag_proj(flags)

        # 3. History Tokens
        history = observations[:, HISTORY_START:HISTORY_START + HISTORY_LENGTH * EVENT_SIZE]
        history = history.view(batch_size, HISTORY_LENGTH, EVENT_SIZE)

        # continuous parts of history (everything except card_id at index 2)
        hist_cont = torch.cat([history[:, :, :2], history[:, :, 3:]], dim=2) # [B, L, EVENT_SIZE-1]
        hist_cont_embs = self.hist_cont_proj(hist_cont) # [B, L, d_model]

        hist_card_ids = history[:, :, 2].long() + 1
        hist_card_ids = torch.clamp(hist_card_ids, min=0, max=NUM_CARD_TYPES)
        hist_card_embs = self.card_embedding(hist_card_ids) # [B, L, d_model]

        # Positional encoding (0 to HISTORY_LENGTH-1)
        pos_indices = torch.arange(HISTORY_LENGTH, device=device).unsqueeze(0).expand(batch_size, -1)
        hist_pos_embs = self.history_pos_emb(pos_indices) # [B, L, d_model]

        hist_tokens = hist_cont_embs + hist_card_embs + hist_pos_embs # [B, L, d_model]

        # 4. Concatenate Sequence
        # Sequence: [Global Token (1), Card Tokens (MAX_HAND_SIZE*4), Hist Tokens (HISTORY_LENGTH)]
        seq = torch.cat([global_tokens, card_tokens, hist_tokens], dim=1)

        # 5. 空スロット・未発生の履歴を注意の対象から外す。
        #    外さないと、空きが多い序盤ほど意味のないトークンに注意が吸われる。
        #    グローバルトークンは常に有効。
        card_pad = card_ids == 0                                  # CARD_EMPTY(+1) は 0
        hist_pad = history[:, :, EVENT_TYPE_INDEX] == float(EVENT_TYPE_NONE)
        global_pad = torch.zeros(batch_size, 1, dtype=torch.bool, device=device)
        key_padding_mask = torch.cat([global_pad, card_pad, hist_pad], dim=1)

        # 6. Transformer Pass
        out_seq = self._encode(seq, key_padding_mask)

        # 7. Extract Global Token (Index 0)
        global_out = out_seq[:, 0, :] # [B, d_model]

        return self.final_proj(global_out)
