# Gerit: connected, parallel-square constructive diversity

Gerit now supports a **separate, opt-in constructor** of packed, edge-connected, mutually parallel unit-square shapes. This uses provably feasible integer grid-cell placements with `angle=0`, not mutation/discovery by evolution. For `n` squares it computes the constructive upper bound `k=ceil(sqrt(n))`, then enumerates **positive row-length compositions** with at most `k` rows and at most `k` units per row. Offsets are chosen so adjacent rows share a full unit edge. The result is one connected body, with no gaps between neighboring unit squares along its occupied rows. This does **not** demand a completely filled k×k square; unused grid cells remain empty.

For **n=12**, all of `[4,4,4]`, `[4,4,3,1]`, `[4,4,2,2]` and `[4,3,3,2]` are enumerated as valid **L=4** shapes. For example, `4+4+4` occupies three four-cell rows. The diverse selection generally chooses different geometric silhouettes rather than always exactly those example row sequences. With `--tiling-extra-side 1`, the bank additionally includes `[5,5,2]` and `[5,3,2,2]`, but those require L=5; the default is the tighter L=k. For n=23, k=5; for n=26, k=6. The process works for any positive integer n (number of shapes grows, so profile enumeration is capped). For exact square numbers such as n=36, the tight k×k full-grid solution has only one occupancy pattern; use an extra side if alternatives are desirable.

## Continue previous evolved population and seed limited diversity

```powershell
cd C:\Physics\Gerit
git pull --ff-only
py -3 -m unittest discover -s tests -p "test_connected_tilings.py" -v
py -3 scripts/run_adaptive_tilings.py --input results/round21-adaptive-v4/selected_population_final.json --generations 300 --seed 2613 --output-dir results/round22-connected
```

By default `--tiling-seeds 3` **replaces only 3 of the worst original 20 parents** and retains 17 original parents with their full inherited individual policies plus the inherited global policy. The original best parent is never displaced; its unseeded descendant lineage gets **a separate protected archive slot**, so known-grid initialization cannot erase the old search pathway. These 3 seeds have fresh neutral individual policies and are labelled `constructive_ancestor: true` in offspring records and the final population. The 18/2 (or 12/8 when stagnating) fitness/diversity competition is otherwise unchanged. The new construction appears only at initialization; no unrequested recurring injection. Option `--tiling-seeds 0` leaves the imported population intact, and `--tiling-seeds 2` uses two seeds. Set `--tiling-extra-side 1` to include candidate shapes that may require L=k+1, but they can be selected less often due their worse side.

**Scientific provenance:** if n=12 is seeded, the best overall recorded `L` immediately becomes 4 at generation zero, **because the constructed layout was injected**. This is *not an evolutionary breakthrough* and is clearly marked in `run_summary.json` (`known_grid_injected`, `best_record_origin`, `constructive_initial_seed_count`) and `initial_population_after_seeding.json` (the actual starting 20 and each inserted pattern). The user-supplied 20 are also archived untouched in `input_selected_population.json`. Separately, `best_unseeded_evolutionary_lineage` tracks the true improvement on the pre-existing evolved line. Claims of a novel packing beating L=4 require an independently verified **L<4** result. Floating-point Shapely/SAT verification is not an exact mathematical certificate.

To continue from a seeded run's final population, avoid reinjecting the same known baseline by using `--tiling-seeds 0` on subsequent runs. `constructive_ancestor` persists across runs.

## Start a new independent n-square study with a structural library

```powershell
py -3 scripts/make_tiling_population.py --squares 23 --output data/connected23.json
py -3 scripts/run_adaptive_tilings.py --input data/connected23.json --tiling-seeds 0 --generations 100 --seed 2323 --output-dir results/connected23
```

For 26 squares use `--squares 26`. Every initial solution is constructed, so **the starting grid bound cannot be credited to evolution**. The generator fills 20 slots from the distinct connected shape bank; if only a few different tight shapes exist, it repeats some and reports the actual number.

The prior `run_adaptive_auto.py`, `run_adaptive_v4.py`, and all historical experiments remain available unchanged. The tiling constructor is a *diversity seed source*, not a proof that the search will find a rotated L<k packing or a global optimum.

## Fix: progress history when injecting a better constructive seed (2026-10-27)

If a saved v4 run has a best-side record above the constructed tiling's initial best (e.g. imported 4.004995911653 and injected 4.000000000000), the prior rolling-window / idle history describes a **different starting reference**. Reusing it caused `ValueError: Saved rolling best does not match imported best` before generation 1.

The runner now **resets only the stagnation/window history** when the newly added constructive seed strictly improves the initial best. This event is reported as `PROGRESS_RESET` and in `config.json`, `run_summary.json`, and the final population. Individual/global learned policies and the imported source data are not reset or altered. With `--tiling-seeds 0`, or when new seeds do not improve the initial record, the previous progress history is restored as before.

A failed run may have left behind its output directory; the runner deliberately refuses to overwrite it. Run the same experiment with a **new output directory** instead, for example:

```powershell
cd C:\Physics\Gerit
git pull --ff-only
py -3 -m unittest discover -s tests -v
py -3 scripts/run_adaptive_tilings.py --input results/round21-adaptive-v4/selected_population_final.json --generations 300 --seed 2613 --output-dir results/round22-connected-fixed --tiling-seeds 3
```
