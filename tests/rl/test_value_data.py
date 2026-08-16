from godfield_rl.opponents import make_opponent
from godfield_rl.hand_value_data import collect_value_data

import numpy as np

def test_collect_value_data():
    seat0 = make_opponent('strategic', seed=0)  
    seat1 = make_opponent('strategic', seed=1)  

    data = collect_value_data(
        seat0,
        seat1,
        games=100,
        num_envs=16,
        seed=42,
        sample_every=10,
    )

    for key, value in data.items():
        print(key, value.shape)

    print('lebels;', np.unique(data['labels'], return_counts=True))

if __name__ == '__main__':
    test_collect_value_data()