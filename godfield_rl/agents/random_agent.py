import numpy as np


class RandomAgent:
    """
    A simple agent that takes random valid (or just random) actions
    from the environment's action space.
    """

    def __init__(self, action_space):
        self.action_space = action_space

    def predict(self, observation):
        # MultiDiscrete action sampling
        # E.g. [card_index_1, card_index_2, card_index_3, target]
        return self.action_space.sample()

    def predict_batch(self, observations):
        # sample for a batch of environments
        batch_size = observations.shape[0]
        return np.array([self.action_space.sample() for _ in range(batch_size)])
