import godfield_core

from godfield_rl.cards import all_cards

all_cards()

pool = godfield_core.EnvPool(4)
pool.reset(42)

x = pool.get_observations_for(0)
y = pool.get_observations()

print(x.shape)
print(pool.get_observations().shape)

assert x.shape == y.shape