"""Deterministic, connected axis-aligned polyomino seeds for any n unit squares.

All unit squares occupy distinct integer cells with zero relative rotation.
A grid with side ceil(sqrt(n)) is constructive prior knowledge, not a
packing found by stochastic evolution. Mark seeded genomes as such.
"""
from __future__ import annotations
from dataclasses import dataclass
from math import isqrt
from random import Random
from typing import Iterator

from .geometry import Packing, Square, validate_packing
from .grid_bounds import grid_bounds


@dataclass(frozen=True)
class ConnectedTiling:
    packing: Packing
    row_lengths: tuple[int, ...]
    row_offsets: tuple[int, ...]
    cells: tuple[tuple[int, int], ...]

    def metadata(self) -> dict:
        return {
            'construction': 'connected_axis_aligned_unit_cell_rows',
            'row_lengths': list(self.row_lengths),
            'row_offsets': list(self.row_offsets),
            'container_side': self.packing.container_side,
            'source': 'constructive_known_feasible_baseline_not_evolutionary_discovery',
        }


def _partitions(n: int, max_side: int, max_profiles: int) -> Iterator[tuple[int, ...]]:
    """Generate row-compositions, capped to avoid combinatorial explosion."""
    emitted = 0
    # Favor tight low-row-count layouts but include all positive row lengths.
    def visit(left: int, rows_remaining: int, prefix: tuple[int, ...]):
        nonlocal emitted
        if emitted >= max_profiles:
            return
        if rows_remaining == 0:
            if left == 0:
                emitted += 1
                yield prefix
            return
        if left < rows_remaining or left > rows_remaining * max_side:
            return
        high = min(max_side, left - (rows_remaining - 1))
        low = max(1, left - (rows_remaining - 1) * max_side)
        for width in range(high, low - 1, -1):
            yield from visit(left - width, rows_remaining - 1, prefix + (width,))
            if emitted >= max_profiles:
                return
    first_rows = (n + max_side - 1) // max_side
    for num_rows in range(first_rows, min(max_side, n) + 1):
        yield from visit(n, num_rows, ())
        if emitted >= max_profiles:
            return


def _offsets(lengths: tuple[int, ...], side: int, layout: str, rng: Random) -> tuple[int, ...]:
    choices = []
    prev_start = prev_width = None
    for row, width in enumerate(lengths):
        legal = list(range(side - width + 1))
        if prev_start is not None:
            # Full unit-edge contact between at least one pair in adjacent rows.
            legal = [x for x in legal if x < prev_start + prev_width and prev_start < x + width]
        if not legal:
            raise RuntimeError('No connected row offset exists')
        if layout == 'left': x = min(legal)
        elif layout == 'right': x = max(legal)
        elif layout == 'center': x = min(legal, key=lambda x: (abs(2*x+width-side),x))
        elif layout == 'zigzag': x = (max(legal) if row % 2 else min(legal))
        elif layout == 'random': x = rng.choice(legal)
        else: raise ValueError('Unknown row offset mode')
        choices.append(x)
        prev_start,prev_width = x,width
    return tuple(choices)


def _shape(lengths: tuple[int, ...], max_side: int, layout: str, rng: Random) -> ConnectedTiling:
    offsets = _offsets(lengths,max_side,layout,rng)
    cells = tuple((offsets[y]+x,y) for y,width in enumerate(lengths) for x in range(width))
    if len(set(cells)) != len(cells):
        raise AssertionError('Duplicate integer grid cells')
    minx = min(x for x,y in cells)
    miny = min(y for x,y in cells)
    cells = tuple(sorted((x-minx,y-miny) for x,y in cells))
    L = float(max(max(x for x,y in cells)+1,max(y for x,y in cells)+1))
    packing = Packing(tuple(Square(x+.5,y+.5,0.0) for x,y in cells),L)
    # All coordinates are exact integer lattice cells; pair overlaps and
    # containment are mathematically excluded here. A full SAT validation
    # is still required before selected seeds enter the breeding population.
    # All cells form one connected body under horizontal or vertical edge contacts.
    visited = {cells[0]}
    fringe = [cells[0]]
    cellset = set(cells)
    while fringe:
        x,y = fringe.pop()
        for c in ((x-1,y),(x+1,y),(x,y-1),(x,y+1)):
            if c in cellset and c not in visited:
                visited.add(c)
                fringe.append(c)
    if len(visited) != len(cells):
        raise AssertionError('Disconnected row pattern')
    return ConnectedTiling(packing,lengths,offsets,cells)


def connected_tiling_candidates(n: int, *, max_extra_side: int = 0,
                                max_profiles: int = 220, seed: int = 0) -> list[ConnectedTiling]:
    """Enumerate a finite, diverse bank of connected flush-aligned candidates.

    max_extra_side=0 gives guaranteed L<=ceil(sqrt(n)); +1 also admits
    e.g. [5,5,2] for n=12. For large n, cap enumeration by max_profiles.
    """
    if type(n) is not int or n < 1: raise ValueError('n must be positive integer')
    if type(max_extra_side) is not int or max_extra_side < 0:
        raise ValueError('max_extra_side must be nonnegative integer')
    if type(max_profiles) is not int or max_profiles < 1:
        raise ValueError('max_profiles must be positive integer')
    bound = grid_bounds(n).grid_upper_side
    max_side = bound + max_extra_side
    rng = Random(seed)
    result = []
    used = set()
    for lengths in _partitions(n,max_side,max_profiles):
        for layout in ('left','right','center','zigzag'):
            candidate = _shape(lengths,max_side,layout,rng)
            key = candidate.cells
            if key in used: continue
            if candidate.packing.container_side > max_side: raise AssertionError('invalid side')
            used.add(key)
            result.append(candidate)
    return result


def choose_tilings(n: int, amount: int = 3, *, max_extra_side: int = 0,
                   seed: int = 0, quality_bias: float = 1.0) -> list[ConnectedTiling]:
    """Choose distinct, tight, structurally distant configurations.

    Include the canonical [k,k,...,remainder] grid first, then use a
    fitness-and-diversity tradeoff in the integer-cell candidate pool.
    """
    if type(amount) is not int or amount < 0: raise ValueError('amount must be >=0')
    if amount == 0: return []
    options = connected_tiling_candidates(n,max_extra_side=max_extra_side,seed=seed)
    # The canonical ceil(sqrt(n)) grid must always be represented, even when
    # allowing an extra row/column for structurally diverse candidates.
    k = grid_bounds(n).grid_upper_side
    greedy_rows = (k,) * (n // k) + ((n % k,) if n % k else ())
    canonical = _shape(greedy_rows, k, 'left', Random(seed))
    options = [canonical] + [opt for opt in options if opt.cells != canonical.cells]
    if not options: raise RuntimeError('No connected tiling produced')
    reference = grid_bounds(n).grid_upper_side
    chosen = [options[0]]  # canonical greedy full-width row fill.
    unused = [opt for opt in options[1:] if opt.cells != chosen[0].cells]
    # Cell symmetric difference is a fast geometric novelty proxy; no O(n^3)
    # pairwise-distance descriptors needed for this constructive seeding stage.
    cellsets = {opt.cells: set(opt.cells) for opt in options}
    while unused and len(chosen) < amount:
        chosen_profiles={tuple(sorted(c.row_lengths)) for c in chosen}
        best_index = max(range(len(unused)), key=lambda i: (
            (0.30 if tuple(sorted(unused[i].row_lengths)) not in chosen_profiles else 0.)
            + min(len(cellsets[unused[i].cells] ^ cellsets[c.cells]) / (2*n)
                  for c in chosen)
            - quality_bias * max(0.0,unused[i].packing.container_side-reference),
            -unused[i].packing.container_side,
            -i))
        chosen.append(unused.pop(best_index))
    for candidate in chosen:
        if not validate_packing(candidate.packing,tolerance=0.0).valid:
            raise AssertionError('Selected constructive packing failed SAT validation')
    return chosen