"""Custom feature extractor for GodField observations.

Handles categorical card ID features through embedding layers
and combines them with continuous features.
"""
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
