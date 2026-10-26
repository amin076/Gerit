
## Geometry-driven search v4 (after the 30-generation relative-orientation audit)

The `initv3-pilot30` experiment (n=12, seed=2715) confirmed that better
**initial** orientations alone do not ensure their survival: the 25 starters
included 18 packings with nonzero relative square angles, but only **3 of the
final 25** had relative-angle variation above 0.01 radians. The final ancestry
was 23 from connected tilings and 2 from `random_sparse` (none from
`random_rotated` or `random_perturbed`). Ancestry and orientation are distinct:
a tiling's evolved descendant can acquire relative angles.

The next change targets the search operators and selection (NOT the initial
population). When 25 parents compete, the selector keeps its usual quality
and broad-novelty seats, but uses **up to 3 of the existing near-best novelty
seats** to compare viable candidates whose internal relative orientation spread
is above 0.02 radians and whose side is at most `best+0.45`. During deep
`diversify`, the target grows to 5. This is a *geometric* niche, not a
fixed allowance for any initial parent or ancestry label. Its candidates are
ranked on novelty and side, and unfilled seats revert to normal competition.

The structural relocation branch now samples a **70% contact-guided / 30%
legacy uniform** mixture. A guided move repositions one or two unit squares
near a side of a *different, currently fixed or already relocated* square,
using a rotation-aware support distance and tangential displacement. Strict
collision and container checks apply to the **complete final packing**; no
continuous collision-free physical movement is claimed. This is not an
injection of any known ideal packing. Old operators (learning, local
compression, micro-refinement) remain available. Logs distinguish the two
structural relocation strategies and retain the actual code in `complete.zip`.

**Run a new matched 30-generation pilot on Windows (no imported parents):**

```powershell
cd C:\Physics\Gerit
git pull --ff-only
py -3 -m unittest discover -s tests -p "test_geometry_niches.py" -v
py -3 -m unittest discover -s tests -p "test_fresh_25.py" -v
py -3 scripts/run_fresh_25.py --squares 12 --population 25 --structural-seeds 7 --generations 30 --seed 2715 --output-dir results/fresh12-p25-geometryv4-pilot30
```

Read the two new diagnostics and compare to the prior v3 pilot's **3/25**
relatively rotated final parents and its 4.0 side:

```powershell
$r = Get-Content "results/fresh12-p25-geometryv4-pilot30/run_summary.json" -Raw | ConvertFrom-Json
$r | Select-Object best_side, initial_relative_orientation_count, final_relative_orientation_parent_count, final_strong_relative_orientation_parent_count, final_near_best_parent_count
$r.final_ancestry_counts
$r.structural_move_proposals
$r.structural_move_valid_children
Get-Content "results/fresh12-p25-geometryv4-pilot30/generations.jsonl" | ConvertFrom-Json | Where-Object { $_.generation -in 0,1,5,10,20,30 } | Select-Object generation,relative_orientation_parent_count,strong_relative_orientation_parent_count,near_best_parent_count
```

The v4 patch passed ten dedicated tests plus a locally executed 10-generation
smoke comparison, which still retained five relatively oriented parents at
generation 10. These short checks **do not prove** an advantage at generation
30 or on the global fitness objective. The user's machine should run the full
30-generation controlled pilot before investing in another 300 generations.

## Short diagnostic of the contact-guided operator (post-v4 pilot)

The independent 30-generation `geometryv4-pilot30` reported an initial 18
relatively tilted parents and five at generation 30 (all five with angle spread
above the stronger 0.02-radian threshold); it reported 22 close-to-best parents.
The ancestor breakdown was 22 `connected_tiling`, one `random_rotated` and two
`random_sparse`. The best remained at L=4.

**Crucial experimental limitation:** default stagnation thresholds are 40
(`precision`), 80 (`escape`), and 120 (`diversify`) idle generations, so a
30-generation default run tests the selection/niche policy only: it has *zero*
contact-guided and *zero* uniform structural relocations. Consequently,
`structural_move_proposals` and `structural_move_valid_children` serialize as
empty JSON objects `{}` (which PowerShell may display as a blank line).

To test the structural operators in a **short, independent diagnostic**, the CLI
now accepts optional stagnation thresholds. Use them only when deliberately
accelerating the search modes, without mistaking such an experiment for a
matched-control replication of the default 30-generation pilot:

```powershell
cd C:\Physics\Gerit
git pull --ff-only
py -3 -m unittest discover -s tests -p "test_geometry_niches.py" -v
py -3 scripts/run_fresh_25.py --squares 12 --population 25 --structural-seeds 7 --generations 30 --seed 2715 --precision-after 5 --escape-after 10 --diversify-after 15 --output-dir results/fresh12-p25-contact-modes30
$r = Get-Content "results/fresh12-p25-contact-modes30/run_summary.json" -Raw | ConvertFrom-Json
$r.mode_generations
$r.structural_move_proposals
$r.structural_move_valid_children
$r | Select-Object best_side, final_relative_orientation_parent_count, final_strong_relative_orientation_parent_count, final_near_best_parent_count
```

Without these three flags, the long-run production behavior remains identical.
No previous results or learned parameters are imported. The accelerated-phase
pilot is a *mechanism check*, not a controlled estimate of fitness benefit;
comparison of the structural operator's merit requires one-at-a-time ablations
with identical phase schedules, seeds and comparable geometry-check budgets.