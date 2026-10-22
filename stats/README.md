# stats: ticket-flow token usage

Goal: same quality, fewer tokens per ticket. The flow started on 2026-10-05.

- `milestones.json`: **the critical changes to the ticket flow and how we work.** One entry per change: `hash`, `label`, `effect` (`down` saves tokens, `up` adds work, `mixed` adds work now and may save later, `base` baseline), `why`. `effect` is a reading of the commit message, not a measurement. Edit it when you know better.
- `build_flow.py`: reads `bin/usage export` and the milestones, writes `site/data.json`.
- `build.py`: the older CSV export (daily, weekly, tickets). Not used by the site.
- `site/`: the dashboard, deployed to brisk as `ticket-stats`.

## Refresh

```sh
python3 stats/build_flow.py 2026-10-05 2026-10-19 --usage .worktrees/igor/igr-18/bin/usage   # END is exclusive
BRISK_SERVER=http://localhost:8787 brisk deploy stats/site
```

`bin/usage` is not on local `main` yet; use the copy in the worktree (or `origin/main`) until it is. Set `BRISK_SERVER` explicitly: the active brisk profile is the remote instance.

## What counts as a critical change

A commit under `plugins/igr` that changes what a session or codex does per ticket:

- adds, removes or reorders a step, pass, review or check;
- changes how codex is driven (clearing, effort, briefs, passes);
- moves work to a script (`tk`) or to CI;
- changes context handling (resume, `/clear`, handoffs);
- changes test or tool-output policy.

Not critical: wording, the progress band, release bumps (`chore(release)`), agent-estimate internals, bug fixes to a mechanism that already exists, file locations.

## Reviewed through

Every `plugins/igr` commit up to `093019d` (2026-10-17 18:57, `origin/main`) has been read. To update, list only newer ones:

```sh
git log origin/main --reverse --format='%h %aI %s' --stat 093019d..origin/main -- plugins/igr
```

Read but not added, so nobody reads them again:

| commit | why not |
| --- | --- |
| 141bb05 | tk CLI added but not used by the loop; `8421409` is when the loop runs on it |
| efd9e52, 9481f6e, be8c666 | extend the cut / earn-its-place check; `9686720` and `78d9ad0` are the step |
| 8309afd, 8611d2a, caa7849, 14269be | approval report and brief wording |
| 504f09c | moves references into the plugin, same content |
| 57c4c75 | small test-run bound, next to `cd086fb` |
| 3957047, 49bed03, a753b76, 21928c3 | fixes to resume (`1a24aa2`) |
| 7cf5161 | Linear connection fix |
| 5d536c7, 5d27223 | where tk keeps its files |
| 7fb61f5 | parks herdr handoff tools, not used by the loop |
| 98e7a6b, 5b7958f, 4c60880, fb668bd | agent-estimate internals |
| 265dee8, c6f6722, 6be2234 | band UI, release |

## How to read the numbers

- **Weighted** is the IGR-14 proxy from `bin/usage` (cache read 0.1x, cache write 1.25-2x, output 5x, model multiplier). Claude only, uncalibrated. Codex has raw tokens only.
- Only calls tagged with a ticket count.
- Stage comes from `tk step` commands, which only exist after `8421409` (2026-10-10 16:10). Before it, develop and review cost sits under design or unknown. Compare totals across that change, not stages.
- Tickets can run for days: 90% finish within 1.4 days, the longest took 7. Tickets started in the last 2 days of data are treated as still running.
- Before/after around a change is observation, not proof: ticket size, neighbouring changes and small samples all move it. Quality is not measured.
