"""Custom feature extractor for GodField observations.

Handles categorical card ID features through embedding layers
and combines them with continuous features.
"""
import math
import gymnasium as gym
import torch
import torch.nn as nn
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor

from godfield_rl.feature_config import (
    CONTINUOUS_FEATURES_SIZE,
    EVENT_SIZE,
    HAND_CARDS_START,
    HISTORY_HEAD_START,
    HISTORY_LENGTH,
    HISTORY_START,
    MAX_HAND_SIZE,
    NUM_CARD_TYPES,
    OPP_STAGED_CARDS_START,
)


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
    """
    Advanced Feature Extractor using Self-Attention (Transformer).
    
    Treats hand cards, staged cards, and history events as a sequence of tokens,
    allowing the network to learn combinatorial synergies (e.g. Card A + Card B)
    and contextual history independent of fixed slot positions.
    """
    def __init__(self, observation_space: gym.spaces.Box,
                 d_model: int = 128,
                 nhead: int = 4,
                 num_layers: int = 2,
                 dim_feedforward: int = 256,
                 features_dim: int = 256):
        super().__init__(observation_space, features_dim)
        
        self.d_model = d_model
        
        # 1. Global context token embedding (Continuous features -> d_model)
        self.global_proj = nn.Linear(CONTINUOUS_FEATURES_SIZE, d_model)
        
        # 2. Card Embeddings
        # Card ID embedding (includes +1 shift for CARD_EMPTY mapped to 0)
        self.card_embedding = nn.Embedding(NUM_CARD_TYPES + 1, d_model, padding_idx=0)
        # Type embedding: 0=My Hand, 1=My Staged, 2=Opp Hand, 3=Opp Staged
        self.card_type_embedding = nn.Embedding(4, d_model)
        
        # 3. History Embeddings
        self.hist_cont_proj = nn.Linear(EVENT_SIZE - 1, d_model)
        # Positional Encoding for History timeline (0 = oldest, HISTORY_LENGTH-1 = newest)
        self.history_pos_emb = nn.Embedding(HISTORY_LENGTH, d_model)
        
        # 4. Transformer Encoder
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=nhead, dim_feedforward=dim_feedforward, batch_first=True
        )
        self.transformer = nn.TransformerEncoder(encoder_layer, num_layers=num_layers)
        
        # Final projection from Global Token -> features_dim
        self.final_proj = nn.Sequential(
            nn.Linear(d_model, features_dim),
            nn.ReLU()
        )
        
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
        
        card_tokens = card_embs + type_embs # [B, 36, d_model]
        
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
        # Sequence: [Global Token (1), Card Tokens (36), Hist Tokens (10)]
        seq = torch.cat([global_tokens, card_tokens, hist_tokens], dim=1) # [B, 1 + 36 + 10, d_model]
        
        # 5. Transformer Pass
        out_seq = self.transformer(seq) # [B, SeqLen, d_model]
        
        # 6. Extract Global Token (Index 0)
        global_out = out_seq[:, 0, :] # [B, d_model]
        
        return self.final_proj(global_out)
