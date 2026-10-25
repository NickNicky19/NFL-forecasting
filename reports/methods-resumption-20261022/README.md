# Resumed methods work — October 22, 2026

Research and implementation resumed. Historical data can support useful model
development even when a method has not earned a default replacement. This packet
contains one newly executed historical comparison, one implemented research
adapter, and an updated [twelve-category index](category-status.json). Earlier
studies and consumed budgets remain separate and unchanged.

## New historical comparison

The fixed question was whether a longer efficiency window helps when holding
the saved passing-attempt forecast constant. Two formulas, zero fits and one
scoring pass were declared before execution. Both variants require the same
eight-appearance history gate and use the same saved pooled-yard fallback.
The held workload is the saved chronological tree-attempt point, **not the
original website-attempt point**. This is a different experiment from the
original website-relative H3 lead.

| Method | MAE, yards | RMSE, yards | Signed bias, yards |
|---|---:|---:|---:|
| Saved recent-yard control | 75.6532 | 96.0826 | +15.0545 |
| Saved pooled-yard control | **73.5458** | **92.8388** | **+13.7275** |
| Held tree attempts × pooled H3 efficiency | 76.7268 | 96.1089 | +20.9636 |
| Held tree attempts × pooled H8 efficiency | 74.4522 | 93.8199 | +20.3621 |

All methods score the same **1,960 supported QB appearances in 815 games and
54 season-weeks**, from exposed 2022–2024 data. All 4,091 offered opportunities
remain: 801 DNP, 1,275 unknown participation and 55 played with missing yardage
are not converted to zero. There are 110 supported zero-yard outcomes.
Both efficiency variants have 1,061 history-informed opportunities and 3,030
fallbacks; respectively 940 and 1,020 are scored.

H8 improves MAE by 2.2745 yards over H3. Its descriptive 99% week interval is
[−3.2197, −1.5657], with only 500 bootstrap draws and coarse adjusted tails.
**Both variants lose to the pooled control.** On the 940 history-informed scored
rows, H8 also loses both controls. The all-row improvement over recent yards
partly comes from the shared pooled fallback. No new formula was selected,
refitted or promoted from these results.

[Aggregate results and all five declared comparisons](history-passing.json)
include protocol/code hashes, yearly diagnostics, tails, full coverage and
resource use. All years were previously exposed; the source uses revised
history and an assumed seven-day availability lag. Historical raw Sleeper and
website forecasts are unavailable for this panel. No new website-relative win,
untouched confirmation or original-runner reproduction is claimed.

## Implemented opt-in method

`website-held-attempts-h3-ypa-research-v1` is available through
[`nfl_lab.research_passing`](../../nfl_lab/research_passing.py) with an explicit
method argument. It implements original held website attempts × pooled YPA
over exactly three qualified current-team/current-season appearances. Unknown
or invalid intervening history stops selection; supported played zero remains;
unsupported inputs retain the unchanged website-yard fallback or abstain when
that original point cannot be authenticated. Signed yards remain legal.

The earlier exposed Week 6 reconstruction scored 27 matched player-games in
13 games: website MAE 56.622963 versus candidate 45.205603 (+20.16%), while
bias worsened from −19.081481 to −24.072824. That promising but limited result
does not establish a generally better default.

The portable adapter matches all 37 previously saved opportunity points and
states, including 15 full-population fallbacks. This is software acceptance on
old predictions, not 37 new validation observations. The replay's calendar
generation/version clock does not establish independent local pre-cutoff
capture. Original runner recovery and source-as-of qualification remain
unproven. The output always records its actual calculation clock and marks
itself unrecorded, unqualified research arithmetic.

The full software suite passed **377 tests**; 30 exercise the new adapter using
fictional fixtures. The separate read-only reviewer accepted the source/score
arithmetic, point parity and implementation with the calendar-clock limitation.
Software tests add no NFL predictive observations.

See [usage, source contracts and recovery](../../docs/research-passing.md).
No raw NFL inputs or private reference rows are included in this public packet.
The existing defaults, workflow and frozen receptions registration are
unchanged. This branch does not activate a website or research recorder.
