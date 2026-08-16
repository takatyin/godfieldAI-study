import torch
import torch.nn as nn


class HandValueModel(nn.Module):
    def __init__(
        self,
        num_card_types: int,
        obs_dim: int,
        stats_dim: int = 6,
        hand_embed_dim: int = 16,
        obs_feature_dim: int = 64,
        hidden_dim: int = 64,
    ):
        super().__init__()

        self.obs_encoder = nn.Sequential(
        nn.Linear(obs_dim, 128),
        nn.ReLU(),
        nn.Linear(128, obs_feature_dim),
        nn.ReLU(),
        )

        self.hand_embedding = nn.Embedding(
            num_embeddings=num_card_types + 1,
            embedding_dim=hand_embed_dim,
            padding_idx=0,
        )

        input_dim = obs_feature_dim + stats_dim + 2 * hand_embed_dim

        self.mlp = nn.Sequential(
            nn.Linear(input_dim, hidden_dim),
            nn.ReLU(),
            nn.Linear(hidden_dim, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
        )

    def _pool_hand(self, hands: torch.Tensor) -> torch.Tensor:
        hands = hands + 1

        mask = (hands != 0)

        emb = self.hand_embedding(hands)

        mask_f = mask.unsqueeze(-1).float()

        summed = (emb * mask_f).sum(dim=1)
        count = mask_f.sum(dim=1).clamp_min(1.0)

        return summed / count
    
    def forward(
            self,
            obs: torch.Tensor,
            stats: torch.Tensor,
            my_hands:torch.Tensor,
            opp_hands:torch.Tensor,
    ) -> torch.Tensor:
        
        obs_feat = self.obs_encoder(obs.float())
        
        my_feat = self._pool_hand(my_hands)
        opp_feat = self._pool_hand(opp_hands)

        x = torch.cat(
            [obs_feat, stats.float(), my_feat, opp_feat], 
             dim=1,
        )

        value = self.mlp(x)

        return value.squeeze(-1)