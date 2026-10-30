import csv
import os
import sys

d = os.path.expanduser('~/ros2_ws/data/')
orig = sys.argv[1] if len(sys.argv) > 1 else 'route.csv'
replay = sys.argv[2] if len(sys.argv) > 2 else 'route_replay.csv'


def load(name):
    with open(d + name) as f:
        return [tuple(map(float, r)) for r in list(csv.reader(f, skipinitialspace=True))[1:]]


a, b = load(orig), load(replay)
print('rows: original', len(a), ', replay', len(b), '(+1 завершальна команда Стоп)')
print('sequence and values equal:', all(x[1:] == y[1:] for x, y in zip(a, b)))
print('max time difference: %.1f ms' % (1000 * max(abs(x[0] - y[0]) for x, y in zip(a, b))))
