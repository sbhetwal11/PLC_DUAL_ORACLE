# Benchmark format

Each task is a folder under `tasks/<tier>/<TASK_ID>/` containing:

- **`meta.json`** - parsed into `plcbench.schema.Task`
- **`reference.st`** - a correct reference IEC 61131-3 Structured Text solution

## `meta.json` fields
| field | meaning |
|---|---|
| `id` | unique task id (matches folder name) |
| `title` | short human title |
| `difficulty` | `easy` \| `medium` \| `hard` |
| `domain` | e.g. `motor control`, `process control`, `safety interlock` |
| `nl_spec` | the natural-language requirement handed to the LLM (the prompt) |
| `interface` | list of typed I/O vars: `name`, `type` (BOOL/INT/REAL/…), `direction` (input/output/internal), `description`, optional `range` `[min,max]` |
| `safety_properties` | list of formal properties: `id`, `kind` (safety/invariant/liveness), `nl`, `ltl` and/or `ctl`, `severity` |
| `scenarios` | optional execution traces: ordered `steps` of `{inputs, expect}` |
| `tags`, `notes` | metadata |

## Property formulas
LTL/CTL are written in **tool-agnostic** form over interface variable names, using
nuXmv-style operators: `!` (not), `&` (and), `|` (or), `->` (implies), and temporal
operators `G` (globally), `F` (eventually), `X` (next), `U` (until). Examples:
- `G(!EStop -> !Motor)` - invariant safety
- `G(!(DoorA & DoorB))` - mutual exclusion
- `G(Level >= 90 -> !PumpIn)` - bounded-numeric safety

Phase B translates these to the model checker (PLCverif/nuXmv). Numeric inputs
should carry a `range` so the state space stays finite and model-checkable.

## Design principles (the moat)
- Every task carries **formal safety properties**, not just I/O examples - this is
  what distinguishes this benchmark from compilation-only sets (e.g. AutoPLC).
- Properties encode **real automation safety** (interlocks, e-stops, overflow,
  mutual exclusion) grounded in industrial practice.
- Difficulty tiers grow from single-interlock (easy) to multi-component sequencing
  and timed logic (medium/hard).

## Current contents (15 tasks, 46 safety properties - all verify via nuXmv)
**Easy (6)** - combinational / latch interlocks:
- `easy/E01_motor_interlock` - latching motor + e-stop priority
- `easy/E02_tank_overflow` - hysteresis level + overflow prevention
- `easy/E03_airlock_interlock` - two-door mutual exclusion
- `easy/E04_conveyor_permissive` - guard + fault start permissive
- `easy/E05_alarm_latch` - set-dominant alarm latch (LTL X property)
- `easy/E06_heater_overtemp` - over-temperature safety cutout

**Medium (9)** - timers (TON) and CASE state machines:
- `medium/M01_motor_startup_delay` - on-delay start (TON)
- `medium/M02_star_delta_starter` - timed state machine + contactor interlock
- `medium/M03_pedestrian_crossing` - 3 phase timers, traffic mutual exclusion
- `medium/M04_tank_fill_drain_cycle` - level-driven state machine
- `medium/M05_conveyor_sequence` - sequenced start (anti-pileup ordering)
- `medium/M06_burner_purge_sequence` - pre-purge/ignition/run, flame supervision
- `medium/M07_two_hand_control` - anti-tie-down two-hand control
- `medium/M08_pump_alternation` - duty/standby lead rotation (edge detection)
- `medium/M09_gate_limits_obstruction` - gate with limits + obstruction stop

(Target: grow to a few hundred tasks; add a HARD tier - multi-component plants, counters.)
