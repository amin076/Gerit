"""Non-geometric example: minimize (x-2)^2+(y+3)^2."""
import argparse
from dataclasses import fields
from pathlib import Path
from gerit_core import Search, Settings


class Quadratic:
    def initial(self, rng):
        return [rng.uniform(-15, 15), rng.uniform(-15, 15)]

    def evaluate(self, state):
        return (state[0]-2)**2 + (state[1]+3)**2

    def feasible(self, state):
        return len(state) == 2 and all(-100 <= v <= 100 for v in state)

    def distance(self, a, b):
        return sum((x-y)**2 for x,y in zip(a,b))**0.5

    def encode(self, state):
        return list(state)

    def decode(self, value):
        return list(value)


def move_coordinate(state, rng, intensity):
    index = rng.randrange(2)
    state[index] += rng.gauss(0, 0.3*intensity)
    return state


def jump(state, rng, intensity):
    return [x+rng.gauss(0, 1.5*intensity) for x in state]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Gerit domain-independent optimizer example")
    for item in fields(Settings):
        default = item.default
        name = "--" + item.name.replace("_","-")
        if isinstance(default, bool):
            parser.add_argument(name, action="store_true", default=default)
        else:
            parser.add_argument(name, type=type(default), default=default)
    args = parser.parse_args()
    cfg = Settings(**{f.name:getattr(args,f.name) for f in fields(Settings)})
    result = Search(Quadratic(), {"coordinate":move_coordinate,"jump":jump}, cfg).run()
    print(f"generation={result.generations} evaluations={result.evaluations} best={result.best_objective:.12g} state={result.best_state}")
    print(f"output={Path(cfg.output_dir).resolve()}")
