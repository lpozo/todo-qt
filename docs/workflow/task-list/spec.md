# Specification — task-list

## Overview
A desktop day planner: tasks are timed slots that can be added, edited, rescheduled, completed,
deleted, and reordered (reordering re-chains times as a timeline). Every change is saved
automatically and restored on the next launch (goal in `requirements.md`). This spec defines the
framework-free domain (`todo_qt.domain`), the use-case API with a persistence port
(`todo_qt.services`), the user-visible UI behavior (`todo_qt.ui`), and the composition root
(`todo_qt.cli`), per ADR-0001. The Qt binding, storage format, and default data directory are
Phase 3 decisions and do not appear here. No signature contains a Qt type.

## Conventions (apply to every interface)
- **Time model.** All datetimes are *naive local wall-clock* values (`tzinfo is None`). Persisted
  and user-entered times have **minute precision** (`second == 0` and `microsecond == 0`).
  Arithmetic is plain wall-clock arithmetic (`+ timedelta`); no DST or time-zone adjustment.
  The only datetimes allowed to carry seconds are `now` values (from the clock).
- **Titles.** A title is stored stripped of leading/trailing whitespace; it is never empty.
  Internal whitespace is preserved. There is no maximum length.
- **Immutability.** Domain values are frozen; every domain operation returns a new value and never
  mutates its input. A failed operation leaves its input and all service state unchanged.
- **Indexes** are 0-based. (Requirements' "position *i*" is 1-based: position *i* = index *i − 1*.)
- **"Same plan"** means `==` on the resulting `Plan` (value equality).
- Reference date in examples: `FRI` = 2026-10-09 (a Friday); `T(h, m)` = `datetime(2026, 10, 9, h, m)`
  unless a date is given.
- Domain exceptions all derive from `DomainError`; store exceptions from `StoreError`.

## Public Interfaces

Authoritative typed signatures are in the "Data Models / Schemas" section (also checked with mypy).
Each interface section below repeats the signature it specifies.

---

### Domain: `todo_qt.domain` errors

```python
class DomainError(Exception): ...


class EmptyTitleError(DomainError): ...


class InvalidTimeSlotError(DomainError): ...


class EndNotAfterStartError(InvalidTimeSlotError): ...


class InvalidDayStartError(DomainError): ...


class NaiveDatetimeRequiredError(DomainError, ValueError): ...


class TaskNotFoundError(DomainError):
    task_id: TaskId


class DuplicateTaskIdError(DomainError):
    task_id: TaskId


class IndexOutOfRangeError(DomainError, IndexError):
    index: int
    size: int
```

| Exception | Raised when |
|---|---|
| `EmptyTitleError` | a title is empty or whitespace-only after stripping |
| `EndNotAfterStartError` | `TimeSlot.end <= TimeSlot.start` |
| `InvalidTimeSlotError` | a slot datetime is timezone-aware, or has non-zero seconds/microseconds (`EndNotAfterStartError` is the subclass for the ordering rule) |
| `InvalidDayStartError` | a day start `time` is timezone-aware or has non-zero seconds/microseconds |
| `NaiveDatetimeRequiredError` | a `now` argument is timezone-aware |
| `TaskNotFoundError` | a `TaskId` is not in the plan |
| `DuplicateTaskIdError` | adding/restoring a task whose id is already in the plan, or building a `Plan` with duplicate ids |
| `IndexOutOfRangeError` | `to_index` is not in `0 <= to_index < len(plan.tasks)` |

---

### `normalize_title(raw: str) -> str`

**Pre-conditions:** none.
**Post-conditions:** returns `raw.strip()`; result is non-empty.
**Failure modes:** raises `EmptyTitleError` when `raw.strip() == ""`.

| # | Name | Given | When | Then |
|---|---|---|---|---|
| 1 | `normalize_title_strips_surrounding_whitespace` | `"  Buy milk \t"` | `normalize_title` | returns `"Buy milk"` |
| 2 | `normalize_title_rejects_whitespace_only` | `"   \n"` | `normalize_title` | raises `EmptyTitleError` |
| 3 | `normalize_title_rejects_empty_string` | `""` | `normalize_title` | raises `EmptyTitleError` |

---

### `TimeSlot(start: datetime, end: datetime)` — frozen dataclass

**Pre-conditions:** `start`, `end` naive, minute precision, `end > start`.
**Post-conditions:** `duration == end - start` (always `> timedelta(0)`). Value-equal by fields.
**Failure modes (raised from the constructor):**
- `InvalidTimeSlotError` when either datetime is aware or has seconds/microseconds.
- `EndNotAfterStartError` when `end <= start` (equal times are rejected: zero-length slots do not exist).
  If a datetime is both aware/imprecise and mis-ordered, `InvalidTimeSlotError` (not the subclass) is raised.

| # | Name | Given | When | Then |
|---|---|---|---|---|
| 1 | `time_slot_accepts_end_after_start` | start 15:00, end 15:30 | construct | `duration == timedelta(minutes=30)` |
| 2 | `time_slot_rejects_end_equal_to_start` | start 15:00, end 15:00 | construct | raises `EndNotAfterStartError` |
| 3 | `time_slot_rejects_end_before_start` | start 15:00, end 14:00 | construct | raises `EndNotAfterStartError` |
| 4 | `time_slot_rejects_timezone_aware_datetime` | start with `tzinfo=UTC` | construct | raises `InvalidTimeSlotError` |
| 5 | `time_slot_rejects_non_zero_seconds` | start `15:00:30` | construct | raises `InvalidTimeSlotError` |
| 6 | `time_slot_spans_midnight` | start Fri 23:30, end Sat 00:15 | construct | valid; `duration == 45 min` |

---

### `Task(id: TaskId, title: str, slot: TimeSlot, done: bool = False)` — frozen dataclass

**Pre-conditions:** `title` non-blank. **Post-conditions:** fields as given (the constructor does
*not* strip; `Plan` operations always store `normalize_title(...)` output).
**Failure modes:** `EmptyTitleError` when `title.strip() == ""`.

| # | Name | Given | When | Then |
|---|---|---|---|---|
| 1 | `task_defaults_to_not_done` | id "a", "Buy milk", slot | construct without `done` | `done is False` |
| 2 | `task_rejects_blank_title` | title `"  "` | construct | raises `EmptyTitleError` |

---

### `Plan(tasks: tuple[Task, ...] = (), day_start: time = time(9, 0))` — frozen dataclass

The ordered task list plus the day start time. The list order is the user-defined order.

**Pre-conditions (constructor):** task ids unique; `day_start` naive, minute precision.
**Post-conditions:** `Plan()` is the empty plan with day start 09:00.
**Failure modes (constructor):** `DuplicateTaskIdError` on duplicate ids; `InvalidDayStartError`
on aware / non-minute `day_start`.

All methods below return a *new* `Plan` (or a tuple containing one) and never mutate `self`.

#### `Plan.index_of(task_id) -> int` / `Plan.get(task_id) -> Task`
Return the 0-based index / the task. Raise `TaskNotFoundError` when absent.

#### `Plan.add(task_id: TaskId, title: str, slot: TimeSlot) -> Plan`
**Post-conditions:** new task `Task(task_id, normalize_title(title), slot, done=False)` is the
**last** element; all other tasks (order, times, flags) unchanged; `day_start` unchanged. Past slots
are allowed (no validation against "now"); overlaps are allowed.
**Failure modes:** `EmptyTitleError` (blank title); `DuplicateTaskIdError` (id present).

| # | Name | Given | When | Then |
|---|---|---|---|---|
| 1 | `add_appends_task_at_bottom_not_done` | plan [A]; add "Buy milk" slot 15:00–15:30 | `add` | tasks = [A, Buy milk]; new task not done, slot as given |
| 2 | `add_rejects_whitespace_only_title` | any plan; title `"   "` | `add` | raises `EmptyTitleError`; original plan unchanged |
| 3 | `add_accepts_slot_entirely_in_past` | slot 08:00–08:30 (any "now") | `add` | task added (overdue-ness is computed elsewhere) |
| 4 | `add_rejects_duplicate_id` | plan containing id "a"; add id "a" | `add` | raises `DuplicateTaskIdError` |
| 5 | `add_strips_title` | title `"  Buy milk "` | `add` | stored title `"Buy milk"` |

#### `Plan.edit_title(task_id, title) -> Plan`
**Post-conditions:** only that task's `title` changes (to the stripped title); position, slot, done
flag unchanged. Editing to an identical title returns an equal plan.
**Failure modes:** `TaskNotFoundError`; `EmptyTitleError` (plan unchanged, original title kept).

| # | Name | Given | When | Then |
|---|---|---|---|---|
| 1 | `edit_title_keeps_position_times_and_done_flag` | [A, "Buy milk" done 10:00–11:00, C] | `edit_title("Buy milk" id, "Buy oat milk")` | index 1 titled "Buy oat milk", same slot, done still true |
| 2 | `edit_title_rejects_blank_title_and_keeps_original` | task "Buy milk" | `edit_title(id, "  ")` | raises `EmptyTitleError`; original plan still has "Buy milk" |
| 3 | `edit_title_unknown_id_raises` | plan without id "zz" | `edit_title("zz", "x")` | raises `TaskNotFoundError` |

#### `Plan.reschedule(task_id, slot: TimeSlot) -> Plan`
**Post-conditions:** only that task's `slot` changes; no other task's times or position change (no
re-chaining; overlaps allowed). Title/done unchanged.
**Failure modes:** `TaskNotFoundError`. (An invalid slot cannot reach this method: `TimeSlot`
construction raises `EndNotAfterStartError` first, so the original times are kept.)

| # | Name | Given | When | Then |
|---|---|---|---|---|
| 1 | `reschedule_changes_only_target_task_times` | A 09:00–10:00, B 10:00–11:00 | `reschedule(A, 13:00–13:45)` | A is 13:00–13:45 at index 0; B unchanged 10:00–11:00 |
| 2 | `reschedule_may_create_overlap` | A 09:00–10:00, B 10:00–11:00 | `reschedule(B, 09:30–10:30)` | accepted; no other task changes |
| 3 | `reschedule_with_end_not_after_start_is_rejected_at_slot_construction` | task with 09:00–10:00 | `TimeSlot(10:00, 09:00)` | raises `EndNotAfterStartError`; plan never changed |

#### `Plan.set_done(task_id, done: bool) -> Plan`
**Post-conditions:** only that task's `done` is set to `done` (idempotent); position and times
unchanged. **Failure modes:** `TaskNotFoundError`.

| # | Name | Given | When | Then |
|---|---|---|---|---|
| 1 | `set_done_marks_task_done_in_place` | [A, B, C], B open | `set_done(B, True)` | B.done true, still index 1, times unchanged |
| 2 | `set_done_false_reopens_task` | B done | `set_done(B, False)` | B.done false |
| 3 | `set_done_is_idempotent` | B done | `set_done(B, True)` | plan equals the input plan |

#### `Plan.delete(task_id) -> tuple[Plan, RemovedTasks]`
**Post-conditions:** the task is removed; remaining tasks keep order and times (no re-chaining).
`RemovedTasks.entries == (RemovedEntry(index=<old index>, task=<removed task>),)`.
**Failure modes:** `TaskNotFoundError`.

| # | Name | Given | When | Then |
|---|---|---|---|---|
| 1 | `delete_removes_task_without_touching_others` | A 09–10, B 10–11, C 11–12 | `delete(B)` | plan [A, C] with unchanged times; removed = ((1, B),) |
| 2 | `delete_unknown_id_raises` | plan without id "zz" | `delete("zz")` | raises `TaskNotFoundError` |

#### `Plan.clear_completed() -> tuple[Plan, RemovedTasks | None]`
**Post-conditions:** all done tasks removed; open tasks keep order and times. Returns
`RemovedTasks` with every removed `(old_index, task)` in ascending index order. If no task is done,
returns `(self, None)`.
**Failure modes:** none.

| # | Name | Given | When | Then |
|---|---|---|---|---|
| 1 | `clear_completed_removes_only_done_tasks` | [A open, B done, C open, D done] | `clear_completed` | plan [A, C] times unchanged; removed = ((1,B),(3,D)) |
| 2 | `clear_completed_with_nothing_done_returns_none` | [A open, B open] | `clear_completed` | returns (same plan, `None`) |

#### `Plan.restore(removed: RemovedTasks) -> Plan`
**Post-conditions:** entries are re-inserted in ascending `index` order, each at
`min(entry.index, len(current tasks))` (so an index beyond the current length appends). Restored
tasks keep their stored title, slot, and done flag (**no re-chaining**). Other tasks are untouched.
**Failure modes:** `DuplicateTaskIdError` when a restored id is already present.

| # | Name | Given | When | Then |
|---|---|---|---|---|
| 1 | `restore_reinserts_deleted_task_at_previous_index` | [A, C] with removed ((1, B),) | `restore` | [A, B, C] with B's original title/times/done |
| 2 | `restore_reinserts_cleared_tasks_at_previous_positions` | [A, C] with removed ((1,B),(3,D)) | `restore` | [A, B, C, D] |
| 3 | `restore_after_add_inserts_at_old_index_not_at_end` | [B, C, D(new)] with removed ((0, A)) | `restore` | [A, B, C, D] |
| 4 | `restore_clamps_index_beyond_current_length` | [A] with removed ((5, Z)) | `restore` | [A, Z] |
| 5 | `restore_keeps_done_flag_and_times` | removed done task X 09:00–10:00 | `restore` | X done, 09:00–10:00 |
| 6 | `restore_duplicate_id_raises` | plan already containing the removed id | `restore` | raises `DuplicateTaskIdError` |

#### `Plan.move(task_id, to_index: int) -> Plan` — the timeline cascade

`to_index` is the **final** 0-based index of the task in the resulting list (the drop position after
the task has been lifted out). Let `i = to_index`, `old = plan.index_of(task_id)`.

**Pre-conditions:** `task_id` in plan; `0 <= to_index < len(tasks)`.
**Post-conditions:**
- If `i == old`: returns a plan equal to `self` (no-op; nothing re-chained).
- Otherwise the task is removed from `old` and inserted at `i`, then:
  - **`i > 0` and `old > 0`** (a task other than the first moves): tasks at indexes `0..i-1` are
    unchanged (times, order). For `k >= i`: `start_k = end_{k-1}` (end of the task directly above,
    after its own re-chaining) and `end_k = start_k + duration_k`. Durations, done flags and titles
    are preserved; done tasks are re-chained like any other.
  - **`i > 0` and `old == 0`** (the old first task moves down): the **new first task** (the task now
    at index 0, formerly at index 1) starts at `day_start` on **its own start date**
    (`new_first.slot.start.date()`), keeping its duration; every task below it (indexes `1..`,
    including the moved task) re-chains with the same `start_k = end_{k-1}` rule, done tasks included.
  - **`i == 0`:** the moved task starts at `day_start` on the **date of the start of the first task
    *before* the move** (i.e. `old_first.slot.start.date()`), keeping its duration; every task
    below then chains as above.
- Re-chaining uses plain wall-clock `+ timedelta`, so ends/starts that pass midnight roll into the
  next calendar day.
- The first task is re-anchored to `day_start` only when the move changes which task is first
  (`i == 0`, or `old == 0` with `i > 0`); otherwise tasks above the destination are untouched.
**Failure modes:** `TaskNotFoundError`; `IndexOutOfRangeError(index=to_index, size=len)` (also for
an empty plan: every index is out of range).

| # | Name | Given | When | Then |
|---|---|---|---|---|
| 1 | `move_into_middle_rechains_tail` | A 09:00–10:00, B 10:00–11:30, C 14:00–14:30 | `move(C, 1)` | order A, C, B; A 09:00–10:00, C 10:00–10:30, B 10:30–12:00 |
| 2 | `move_keeps_tasks_above_destination_unchanged` | A 09–10, B 10–11, C 11–12, D 13–14 | `move(D, 2)` | A, B identical to before; D 11:00–12:00; C 12:00–13:00 |
| 3 | `move_to_top_starts_at_day_start_on_old_first_tasks_date` | day start 09:00; A Fri 10:00–11:00, B Fri 11:00–12:00, C Fri 15:00–15:30 | `move(C, 0)` | C Fri 09:00–09:30, A Fri 09:30–10:30, B Fri 10:30–11:30 |
| 4 | `move_to_top_uses_date_of_previous_first_task_not_moved_task` | day start 09:00; A Sat 10:00–11:00, C Fri 15:00–15:30 | `move(C, 0)` | C Sat 09:00–09:30, A Sat 09:30–10:30 |
| 5 | `move_rechains_done_task_and_keeps_done_flag` | A 09–10, B(done) 10–11, C 12–13 | `move(C, 1)` | C 10–11, B 11–12; B.done still true |
| 6 | `move_cascade_crosses_midnight` | A Fri 22:00–23:00, B Fri 23:00–23:45, C Fri 09:00–10:00 | `move(C, 1)` | C Fri 23:00–Sat 00:00, B Sat 00:00–Sat 00:45 |
| 7 | `move_to_own_position_is_noop` | A, B, C with a gap between B and C | `move(B, 1)` | returned plan equals input; no times change |
| 8 | `move_first_task_to_end_rechains_from_new_first` | day start 09:00; A 09–10, B 10–11, C 11–12 | `move(A, 2)` | order B, C, A; B 09:00–10:00 (snapped to day start; equals its old time here), C 10:00–11:00, A 11:00–12:00 |
| 9 | `move_first_task_down_snaps_new_first_to_day_start` | day start 09:00; A Fri 09:00–10:00, B Fri 10:30–11:30, C Fri 12:00–13:00 | `move(A, 1)` | order B, A, C; B Fri 09:00–10:00, A Fri 10:00–11:00, C Fri 11:00–12:00 |
| 9b | `move_first_task_down_uses_new_first_tasks_own_date` | day start 09:00; A Fri 09:00–10:00, B Sat 10:30–11:30 | `move(A, 1)` | order B, A; B Sat 09:00–10:00, A Sat 10:00–11:00 |
| 9c | `move_non_first_task_down_leaves_tasks_above_untouched` | day start 09:00; A Fri 08:00–09:00, B 10–11, C 11–12, D 13–14 | `move(B, 2)` | order A, C, B, D; A (08:00–09:00, not snapped) and C (11–12) unchanged; B 12:00–13:00; D 13:00–14:00 |
| 10 | `move_index_out_of_range_raises` | 3 tasks | `move(A, 3)` and `move(A, -1)` | raises `IndexOutOfRangeError` |
| 11 | `move_unknown_id_raises` | any plan | `move("zz", 0)` | raises `TaskNotFoundError` |
| 12 | `move_preserves_durations_titles_and_ids` | any move | `move` | multiset of (id, title, duration, done) unchanged |

#### `Plan.set_day_start(day_start: time) -> Plan`
**Pre-conditions:** `day_start` naive, minute precision.
**Post-conditions:**
- If `day_start == self.day_start`: returns an equal plan (**no-op; nothing re-chained**).
- Otherwise `day_start` is replaced. If there are tasks, the first task is moved to `day_start` on
  **its own start date**, keeping its duration, and each following task is re-chained after the one
  above (same chaining rule as `move`, done tasks included). If there are no tasks only `day_start`
  changes.
**Failure modes:** `InvalidDayStartError` (aware / seconds / microseconds).

| # | Name | Given | When | Then |
|---|---|---|---|---|
| 1 | `set_day_start_rechains_from_first_task` | day start 09:00; A Fri 10:00–11:00, B Fri 11:00–12:00 | `set_day_start(08:00)` | A Fri 08:00–09:00, B Fri 09:00–10:00; `day_start == 08:00` |
| 2 | `set_day_start_on_empty_plan_only_changes_day_start` | empty plan | `set_day_start(07:30)` | `tasks == ()`, `day_start == 07:30` |
| 3 | `default_day_start_is_nine_oclock` | `Plan()` | read `day_start` | `time(9, 0)` |
| 4 | `set_day_start_to_same_value_is_noop` | day start 09:00; A Fri 10:00–11:00 | `set_day_start(09:00)` | A still Fri 10:00–11:00 |
| 5 | `set_day_start_rechain_crosses_midnight` | A Fri 10:00–23:30, B Fri 23:30–23:50; set 22:00 | `set_day_start(22:00)` | A Fri 22:00–Sat 11:30, B Sat 11:30–Sat 11:50 |
| 6 | `set_day_start_rejects_seconds` | any | `set_day_start(time(8, 0, 30))` | raises `InvalidDayStartError` |
| 7 | `set_day_start_rechains_done_tasks_too` | A(done) Fri 10:00–11:00, B Fri 11:00–12:00 | `set_day_start(08:00)` | A 08:00–09:00 still done; B 09:00–10:00 |

---

### `default_slot(now: datetime) -> TimeSlot`

**Pre-conditions:** `now` naive (seconds/microseconds allowed).
**Post-conditions:** `start` = the first full hour **strictly after** `now` (`now` truncated to the
hour, plus 1 hour); `end = start + 30 min`. Independent of day start. Crosses midnight naturally.
**Failure modes:** `NaiveDatetimeRequiredError` when `now` is aware.

| # | Name | Given | When | Then |
|---|---|---|---|---|
| 1 | `default_slot_rounds_up_to_next_full_hour` | now 14:20 | `default_slot` | 15:00–15:30 |
| 2 | `default_slot_at_exact_hour_uses_following_hour` | now 14:00:00 | `default_slot` | 15:00–15:30 |
| 3 | `default_slot_rolls_over_midnight` | now Fri 23:20 | `default_slot` | Sat 00:00–Sat 00:30 |
| 4 | `default_slot_ignores_seconds` | now 14:59:59.999999 | `default_slot` | 15:00–15:30 |
| 5 | `default_slot_rejects_aware_now` | now with `tzinfo=UTC` | `default_slot` | raises `NaiveDatetimeRequiredError` |
| 6 | `default_slot_ignores_day_start` | `Plan.set_day_start(08:00)` applied, now 14:20 | `default_slot(now)` | 15:00–15:30 (the function takes no plan) |

### `is_overdue(task: Task, now: datetime) -> bool`

**Post-conditions:** `True` iff `not task.done and task.slot.end < now` (**strictly**: at
`now == end` the task is not yet overdue). `now` may carry seconds.
**Failure modes:** `NaiveDatetimeRequiredError` when `now` is aware.

| # | Name | Given | When | Then |
|---|---|---|---|---|
| 1 | `is_overdue_true_for_open_task_ended_before_now` | open, end 10:00 | now 10:00:01 | `True` |
| 2 | `is_overdue_false_at_exact_end` | open, end 10:00 | now 10:00:00 | `False` |
| 3 | `is_overdue_false_for_done_task` | done, end 10:00 | now 12:00 | `False` |
| 4 | `is_overdue_false_for_future_task` | open, end 10:00 | now 09:00 | `False` |
| 5 | `is_overdue_returns_after_uncomplete` | done→open, end in past | `is_overdue` | `True` |
| 6 | `is_overdue_rejects_aware_now` | any task | aware now | raises `NaiveDatetimeRequiredError` |

---

### Services: persistence port and errors (`todo_qt.services`)

```python
type PlanSnapshot = Plan


class StoreError(Exception):
    path: Path
    reason: str


class StoreCorruptError(StoreError): ...


class StoreWriteError(StoreError): ...


class PlanStore(Protocol):
    def load(self) -> PlanSnapshot | None: ...
    def save(self, snapshot: PlanSnapshot) -> None: ...
```

`PlanSnapshot` *is* the `Plan` value (tasks in order + day start); the undo slot is never part of it.
The logical on-disk schema is under "Persisted schema" below.

**`PlanStore.load()`**
- *Pre-conditions:* none (the data location was fixed when the store was created).
- *Post-conditions:* returns the saved `Plan` exactly (same order, titles, starts, ends, done flags,
  day start); returns `None` when nothing has ever been saved (no data file). **Never writes,
  renames, truncates, or deletes** anything.
- *Failure modes:* raises `StoreCorruptError(path, reason)` when saved data exists but cannot be
  read (I/O or permission error), cannot be decoded, has a missing/invalid required field, has a
  `schema_version` other than the supported one (including newer), or violates `Plan` invariants
  (duplicate ids, end not after start, non-minute times). The whole snapshot is rejected; there is
  no partial load.

**`PlanStore.save(snapshot)`**
- *Pre-conditions:* `snapshot` is a valid `Plan`.
- *Post-conditions:* afterwards `load()` returns an equal plan. **Atomic:** if the process dies at
  any point during `save`, a later `load()` returns either the previous snapshot or the new one,
  never a partial one. The data directory and file are accessible only by the current user. Creates
  the data directory if missing.
- *Preservation of unreadable data:* if the preceding `load()` of this store raised
  `StoreCorruptError`, the first successful `save` must keep the unreadable content recoverable
  (it must not be destroyed or silently replaced); if it cannot be preserved, `save` raises
  `StoreWriteError` and writes nothing. Where/how it is preserved is a Phase 3 decision.
- *Failure modes:* raises `StoreWriteError(path, reason)` on any failure to persist (disk full, not
  writable, directory not creatable). A failed `save` leaves the previously saved snapshot intact.

| # | Name | Given | When | Then |
|---|---|---|---|---|
| 1 | `store_load_returns_none_when_nothing_saved` | fresh empty data dir | `load()` | `None` |
| 2 | `store_roundtrip_preserves_order_titles_times_done_and_day_start` | plan with 3 tasks (one done), day start 08:00 | `save(p)`; new store on same dir; `load()` | equals `p` |
| 3 | `store_load_corrupt_data_raises_and_leaves_file_untouched` | data file with undecodable bytes | `load()` | raises `StoreCorruptError`; file bytes and mtime unchanged |
| 4 | `store_load_rejects_unknown_schema_version` | file with `schema_version` 2 | `load()` | raises `StoreCorruptError` |
| 5 | `store_load_rejects_end_not_after_start` | file with a task whose end == start | `load()` | raises `StoreCorruptError` |
| 6 | `store_save_failure_raises_store_write_error` | data dir not writable | `save(p)` | raises `StoreWriteError` |
| 7 | `store_save_is_atomic_previous_state_survives_failed_write` | saved plan P1; a write fails midway | `save(P2)` fails | `load()` returns P1 |
| 8 | `store_save_after_corrupt_load_preserves_unreadable_content` | corrupt file, `load()` raised | `save(p)` | the old unreadable bytes still exist somewhere in the data dir and `load()` returns `p` |
| 9 | `store_files_are_user_only` | save on POSIX | inspect modes | directory `0o700`, file `0o600` (no group/other bits) |

---

### `PlanService` (`todo_qt.services`)

```python
type Clock = Callable[[], datetime]  # returns naive local "now"
type IdFactory = Callable[[], TaskId]  # returns a fresh, unique id per call


@dataclass(frozen=True, slots=True)
class ChangeResult:
    plan: Plan
    changed: bool
    save_error: StoreWriteError | None = None
    task_id: TaskId | None = None


class PlanService:
    def __init__(self, store: PlanStore, clock: Clock, new_id: IdFactory) -> None: ...
    # state / queries
    @property
    def plan(self) -> Plan: ...
    @property
    def startup_error(self) -> StoreCorruptError | None: ...
    @property
    def can_undo(self) -> bool: ...
    @property
    def can_clear_completed(self) -> bool: ...
    def now(self) -> datetime: ...
    def default_slot(self) -> TimeSlot: ...
    def is_overdue(self, task_id: TaskId) -> bool: ...
    def overdue_ids(self) -> frozenset[TaskId]: ...
    # commands
    def add_task(self, title: str, slot: TimeSlot) -> ChangeResult: ...
    def edit_title(self, task_id: TaskId, title: str) -> ChangeResult: ...
    def reschedule(self, task_id: TaskId, slot: TimeSlot) -> ChangeResult: ...
    def set_done(self, task_id: TaskId, done: bool) -> ChangeResult: ...
    def delete_task(self, task_id: TaskId) -> ChangeResult: ...
    def clear_completed(self) -> ChangeResult: ...
    def undo(self) -> ChangeResult: ...
    def move_task(self, task_id: TaskId, to_index: int) -> ChangeResult: ...
    def set_day_start(self, day_start: time) -> ChangeResult: ...
```

#### Construction and startup
**Pre-conditions:** `clock` returns naive datetimes; `new_id` returns unique ids.
**Post-conditions:** the constructor calls `store.load()` exactly once and **never calls
`store.save`**. `plan` is the loaded plan; if `load()` returned `None`, `plan == Plan()` (empty,
day start 09:00). If `load()` raised `StoreCorruptError`, `plan == Plan()`, `startup_error` is that
exception, and nothing was written. Otherwise `startup_error is None`. The undo slot starts empty
(undo is per session, never persisted).
**Failure modes:** none raised for corrupt data (captured in `startup_error`). Any other exception
from the store propagates.

| # | Name | Given | When | Then |
|---|---|---|---|---|
| 1 | `service_starts_empty_when_nothing_saved` | store.load → `None` | construct | `plan.tasks == ()`, `plan.day_start == time(9,0)`, `startup_error is None` |
| 2 | `service_starts_with_saved_tasks_in_order_and_day_start` | store.load → plan [A,B,C], day start 08:30 | construct | `plan` equals it |
| 3 | `service_starts_empty_on_corrupt_store_without_saving` | store.load raises `StoreCorruptError` | construct | empty plan; `startup_error` set; `store.save` never called |
| 4 | `service_does_not_save_during_construction` | any store | construct | zero `save` calls |
| 5 | `service_new_session_has_no_undo` | tasks saved, a delete was done in a previous service instance | construct new service; `undo()` | `can_undo` false; result `changed=False`; task not restored |

#### Common command contract (applies to every command below)
- **Pre-conditions:** as per the corresponding `Plan` operation.
- **Domain failures:** the underlying `DomainError` is raised unchanged; `plan`, the undo slot, and
  the store are untouched (no save attempted).
- **Success:** `plan` is replaced by the new plan; then, **iff the new plan != the previous plan**,
  `store.save(new_plan)` is called exactly once, synchronously, before the method returns
  (auto-save; no separate Save action). `ChangeResult.changed` is `new != old`.
- **Save failure:** if `store.save` raises `StoreWriteError`, the exception is **not** propagated:
  `plan` keeps the change in memory, `ChangeResult.save_error` carries the error, `changed` is
  true. The next successful change saves the whole current plan (so it persists the earlier
  unsaved change too). Any other exception from the store propagates.
- `ChangeResult.plan` is the service's plan after the call. `task_id` is set only by `add_task`.

#### `add_task(title, slot)`
Id from `new_id()`; `Plan.add`. **Failure modes:** `EmptyTitleError`, `DuplicateTaskIdError`.

| # | Name | Given | When | Then |
|---|---|---|---|---|
| 1 | `service_add_task_appends_and_saves` | empty plan, clock 14:20 | `add_task("Buy milk", 15:00–15:30)` | plan has 1 task, not done; `result.task_id` is its id; `save` called once with the new plan |
| 2 | `service_add_task_blank_title_raises_and_does_not_save` | any | `add_task("  ", slot)` | `EmptyTitleError`; plan unchanged; no save |
| 3 | `service_add_past_task_is_reported_overdue` | clock 14:20; add 08:00–08:30 | `overdue_ids()` | contains the new task id |
| 4 | `service_add_task_after_day_start_change_still_prefills_next_hour` | clock 14:20, `set_day_start(08:00)` done | `default_slot()` | 15:00–15:30 |

#### `edit_title`, `reschedule`, `set_done`
Delegate to `Plan.edit_title / reschedule / set_done`. **Failure modes:** `TaskNotFoundError`,
`EmptyTitleError` (edit_title).

| # | Name | Given | When | Then |
|---|---|---|---|---|
| 1 | `service_edit_title_saves_new_title` | task "Buy milk" | `edit_title(id, "Buy oat milk")` | plan title "Buy oat milk"; one save |
| 2 | `service_edit_title_blank_keeps_original_and_does_not_save` | task "Buy milk" | `edit_title(id, " ")` | raises `EmptyTitleError`; title "Buy milk"; no save |
| 3 | `service_reschedule_saves_and_leaves_others` | A, B | `reschedule(A, new slot)` | A new times; B same; one save |
| 4 | `service_set_done_saves` | open task | `set_done(id, True)` | done; one save |
| 5 | `service_set_done_same_value_does_not_save` | done task | `set_done(id, True)` | `changed=False`; no save |
| 6 | `service_uncomplete_makes_past_task_overdue_again` | done task ended 10:00, clock 12:00 | `set_done(id, False)` | `is_overdue(id)` true |

#### `delete_task(task_id)`, `clear_completed()`, `undo()`
- `delete_task`: `Plan.delete`; the returned `RemovedTasks` **replaces** the undo slot.
- `clear_completed`: `Plan.clear_completed`; if it returned `None` the call is a no-op
  (`changed=False`, no save, **undo slot untouched**); otherwise `RemovedTasks` replaces the slot
  (one slot entry, so one undo restores all).
- `undo`: if the slot is empty returns `changed=False` (no save, no error). Otherwise
  `Plan.restore(slot)`, clears the slot, saves. Exactly one level: a second `undo` after a restore
  does nothing.
- The slot is changed *only* by delete, clear completed (replace), and undo (clear). Add, edit,
  reschedule, done-toggle, move, and day-start change **do not** clear it.
- `can_undo` is true iff the slot is non-empty; `can_clear_completed` is true iff any task is done.
**Failure modes:** `TaskNotFoundError` (delete); `DuplicateTaskIdError` (undo, defensive; slot kept).

| # | Name | Given | When | Then |
|---|---|---|---|---|
| 1 | `service_delete_removes_task_and_saves` | [A, B, C] | `delete_task(B)` | plan [A, C], times unchanged; one save; `can_undo` true |
| 2 | `service_undo_restores_deleted_task_at_previous_position` | [A, B, C]; delete B | `undo()` | plan [A, B, C] with B's title/times/done; saved |
| 3 | `service_undo_only_restores_last_delete` | [X, Y, Z]; delete X, then delete Y | `undo()`; `undo()` | after first: Y restored (plan [Y, Z]); after second: `changed=False`, X not restored |
| 4 | `service_undo_with_nothing_deleted_does_nothing` | fresh service | `undo()` | `changed=False`; no save; plan equal |
| 5 | `service_undo_after_delete_then_add_inserts_at_old_index` | [A, B]; delete A; add D | `undo()` | plan [A, B, D] |
| 6 | `service_undo_after_move_restores_with_old_times` | [A,B,C]; delete C; move B to 0 | `undo()` | C reinserted at index 2 with its original times (not re-chained) |
| 7 | `service_clear_completed_removes_done_and_saves` | [A open, B done, C open] | `clear_completed()` | plan [A, C] unchanged times; one save |
| 8 | `service_undo_after_clear_completed_restores_all_cleared` | [A, B done, C, D done]; clear | `undo()` | [A, B, C, D] |
| 9 | `service_clear_completed_with_nothing_done_is_noop` | [A, B] open | `clear_completed()` | `changed=False`; no save; undo slot unchanged |
| 10 | `service_can_clear_completed_false_when_none_done` | all open | property | `False`; true once one is done |
| 11 | `service_second_delete_replaces_undo_slot_after_clear` | clear completed, then delete Q | `undo()` | only Q restored |
| 12 | `service_undo_twice_after_single_delete_restores_once` | delete X | `undo()`, `undo()` | second returns `changed=False` |

#### `move_task(task_id, to_index)` and `set_day_start(day_start)`
Delegate to `Plan.move` / `Plan.set_day_start`; save iff the plan changed (so moving to its own
position, or setting the same day start, saves nothing). **Failure modes:** `TaskNotFoundError`,
`IndexOutOfRangeError`; `InvalidDayStartError`.

| # | Name | Given | When | Then |
|---|---|---|---|---|
| 1 | `service_move_task_rechains_and_saves` | A 09–10, B 10–11:30, C 14–14:30 | `move_task(C, 1)` | A, C 10:00–10:30, B 10:30–12:00; one save |
| 2 | `service_move_task_to_same_index_does_not_save` | any | `move_task(B, 1)` for B at 1 | `changed=False`; no save |
| 3 | `service_set_day_start_saves_new_day_start_and_rechains` | day start 09:00; A Fri 10–11, B Fri 11–12 | `set_day_start(08:00)` | A 08–09, B 09–10; saved with `day_start 08:00` |
| 4 | `service_set_day_start_on_empty_list_saves_day_start` | empty plan | `set_day_start(07:00)` | `day_start 07:00`, no tasks; one save |
| 5 | `service_day_start_survives_restart` | `set_day_start(08:00)` | new service on same store | `plan.day_start == 08:00` |

#### Auto-save and save failures

| # | Name | Given | When | Then |
|---|---|---|---|---|
| 1 | `service_saves_after_every_kind_of_change` | recording store | add, edit, reschedule, done, undone, move, delete, clear, undo, set_day_start (each effective) | `save` called once per command with the resulting plan |
| 2 | `service_restart_after_kill_shows_last_change` | file-backed store | any command, then discard the service without any shutdown call; new service on same store | new `plan` equals the last `plan` |
| 3 | `service_keeps_change_in_memory_when_save_fails` | store.save raises `StoreWriteError` | `add_task("X", slot)` | no exception; `plan` contains X; `result.save_error` is that error; `changed` true |
| 4 | `service_next_successful_save_persists_earlier_unsaved_change` | save failed for add X; then store works | `set_done(A, True)` | saved plan contains both X and A done; `save_error is None` |
| 5 | `service_non_write_store_errors_propagate` | store.save raises `RuntimeError` | command | `RuntimeError` propagates |
| 6 | `service_restart_preserves_order_titles_times_done_flags` | 3 tasks, one done, reordered | new service on same store | `plan` equal |

#### Queries: `now`, `default_slot`, `is_overdue`, `overdue_ids`
- `now()` returns `clock()`. `default_slot()` = `default_slot(clock())`.
- `is_overdue(task_id)` = `domain.is_overdue(plan.get(task_id), clock())`; raises `TaskNotFoundError`.
- `overdue_ids()` = ids of all tasks overdue at `clock()`. Pure reads: no save, no state change.
- `NaiveDatetimeRequiredError` propagates if the clock returns an aware datetime.

| # | Name | Given | When | Then |
|---|---|---|---|---|
| 1 | `service_default_slot_uses_injected_clock` | clock → 14:20 | `default_slot()` | 15:00–15:30 |
| 2 | `service_overdue_ids_reflect_clock_advancing` | open task ends 14:30; clock 14:29:59 then 14:30:01 | `overdue_ids()` twice | empty, then contains the id |
| 3 | `service_overdue_ids_exclude_done_tasks` | done task ended in past | `overdue_ids()` | empty |
| 4 | `service_is_overdue_unknown_id_raises` | any | `is_overdue("zz")` | `TaskNotFoundError` |

---

### Composition root: `todo_qt.cli`

```python
DATA_DIR_ENV_VAR: str = "TODO_QT_DATA_DIR"
type UiRunner = Callable[[PlanService], int]


def resolve_data_dir(environ: Mapping[str, str], default_dir: Path) -> Path: ...


def main(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    run_ui: UiRunner | None = None,
) -> int: ...
```

#### `resolve_data_dir(environ, default_dir) -> Path` [Could: `TODO_QT_DATA_DIR`]
**Post-conditions:** if `environ` has `TODO_QT_DATA_DIR` with a non-empty value, returns that path
(user home `~` expanded, made absolute against the current directory); otherwise returns
`default_dir`. Pure; touches no filesystem. (What `default_dir` is, is a Phase 3 decision.)
**Failure modes:** none.

| # | Name | Given | When | Then |
|---|---|---|---|---|
| 1 | `resolve_data_dir_uses_env_override` | env `{TODO_QT_DATA_DIR: "/tmp/x"}` | resolve | `Path("/tmp/x")` |
| 2 | `resolve_data_dir_falls_back_to_default_when_unset` | env `{}` | resolve | `default_dir` |
| 3 | `resolve_data_dir_treats_empty_value_as_unset` | env `{TODO_QT_DATA_DIR: ""}` | resolve | `default_dir` |
| 4 | `main_reads_and_saves_in_override_dir` | env override → `tmp_path`, fake `run_ui` that adds a task | `main([], environ=…, run_ui=…)` | task data exists only under `tmp_path`; default dir untouched |

#### `main(argv=None, *, environ=None, run_ui=None) -> int`
Entry point of `todo-qt` (`todo_qt.cli:main`; a no-argument call `main()` must work).
**Pre-conditions:** `argv` defaults to `sys.argv[1:]`; `environ` defaults to `os.environ`; `run_ui`
defaults to the Qt application runner (Phase 3). `run_ui` exists so tests can run `main` without Qt.
**Post-conditions (wiring):** resolves the data dir; builds the store for it; builds the system clock
(naive local time) and a unique-id factory; constructs one `PlanService`; calls
`run_ui(service)` once and returns its result (the event-loop exit code, `0` on a normal close).
`main` itself never saves. The UI is responsible for showing `service.startup_error`.
**Failure modes (returns, does not raise):**
- Returns `2` and prints a usage message to stderr when `argv` is non-empty (the app accepts no arguments).
- Returns `1` and prints a message to stderr when the data directory cannot be created/used
  at all for the store (e.g. path is a file). A corrupt data *file* is **not** fatal (see
  `startup_error`; the app starts empty).
- Makes no network connections.

| # | Name | Given | When | Then |
|---|---|---|---|---|
| 1 | `main_launches_ui_with_empty_service_when_no_saved_data` | empty `tmp_path` dir via env; fake `run_ui` recording the service | `main([], …)` | `run_ui` called once; service plan empty with day start 09:00; returns the fake's `0` |
| 2 | `main_launches_ui_with_saved_tasks` | `tmp_path` contains data saved earlier | `main` | service plan equals saved plan |
| 3 | `main_with_corrupt_data_still_launches_and_preserves_file` | corrupt data file in dir | `main` | `run_ui` called; `service.startup_error` set; file bytes unchanged after `main` returns (no changes made) |
| 4 | `main_rejects_unexpected_arguments` | argv `["--bogus"]` | `main` | returns `2`; `run_ui` not called |
| 5 | `main_returns_ui_exit_code` | fake `run_ui` returns 7 | `main` | returns `7` |
| 6 | `main_fails_when_data_dir_unusable` | env path points at an existing regular file | `main` | returns `1`; `run_ui` not called |

---

### UI contract (`todo_qt.ui`) — user-visible behavior

No class or widget is specified. The UI is a thin layer over `PlanService`: it holds no task
rules, reads state only from `service.plan` / `overdue_ids()`, and every mutation goes through the
service. Dialogs must not block headless tests (errors appear as inline messages or via an
injectable notifier). Strings below are the exact user-visible messages.

| Element / action | Behavior |
|---|---|
| Window at launch | Shows the task list in saved order (empty list when none), the day start time, and an "Add task" control. Each row shows title, start, end (date and time), done state. |
| Startup error | If `service.startup_error` is set, the user is shown: `Your saved tasks could not be read ({path}). Starting with an empty list; the file was left untouched.` |
| Add form open | Fields: title (empty), start, end. Pre-filled from `service.default_slot()` (14:20 → today 15:00 / 15:30). Pre-fill is computed each time the form opens. |
| Add confirm | Title is checked first, then the slot. Blank title: nothing added, message `A title is required.` Slot with end not after start (`EndNotAfterStartError`): nothing added, message `The end must be after the start.` Valid: `service.add_task`; task at bottom, not done. A past slot is accepted and shown overdue. The form stays open with the user's input after an error. |
| Edit title | Starting an edit shows the current title. Confirm with blank: rejected, message `A title is required.`, original kept. Confirm valid: `service.edit_title`. |
| Reschedule | Edit start/end; end not after start: rejected with `The end must be after the start.`, original times kept. Valid: `service.reschedule`; no other row changes. |
| Toggle done | Checking marks done: row struck through, never shown as overdue. Unchecking: shown normally, as overdue if end is in the past. Row stays in position. |
| Delete | Removes the row (`service.delete_task`); others unchanged. |
| Undo | Menu/button "Undo" and shortcut Ctrl+Z (Cmd+Z on macOS) call `service.undo()`. Enabled iff `service.can_undo`; if triggered with nothing to undo, nothing changes and no error is shown. |
| Clear completed | Button "Clear completed" calls `service.clear_completed()`; **disabled** iff `not service.can_clear_completed`, re-evaluated after every change. |
| Drag to reorder | Dropping a row at visual position `p` calls `service.move_task(id, p)` where `p` is the 0-based final index; list refreshes from `service.plan` (rows show the re-chained times). Dropping at its own position changes nothing. Only internal reorder is supported (no drops between rows copy/duplicate). |
| Change day start | A time-of-day control shows `plan.day_start`; changing it calls `service.set_day_start`; displayed list refreshes to the re-chained times. Does not affect the add-form pre-fill. |
| Overdue display | Open tasks in `service.overdue_ids()` are visually highlighted (distinct from normal and from done). Recomputed on every list refresh and by a repeating timer with an interval of **at most 30 s**, with no user action, so a task whose end has passed is highlighted within 60 s. |
| Save failure | When a `ChangeResult.save_error` is not `None`, the user is shown: `Could not save your changes ({reason}). The change is kept in the list but may be lost if you close the app.` The app keeps running and the list shows the change. |
| [Could] Enter in add form | With a non-blank title, Enter confirms the form exactly as the confirm control does. |
| [Could] Delete key | With a task selected, Delete (Backspace on macOS) calls `service.delete_task` (undoable). With no selection nothing happens. |

Behavioral examples (UI tests drive the real UI against a fake store and fixed clock):

| # | Name | Given | When | Then |
|---|---|---|---|---|
| 1 | `ui_shows_empty_list_and_add_control_when_no_saved_tasks` | empty store | open window | zero rows; add control present |
| 2 | `ui_shows_saved_tasks_in_order_with_day_start` | store with [A,B,C], day start 08:30 | open window | rows A,B,C with saved times; day start shows 08:30 |
| 3 | `ui_add_form_is_prefilled_with_next_full_hour` | clock 14:20 | open add form | start 15:00 today, end 15:30 today |
| 4 | `ui_add_valid_task_appears_at_bottom` | add form, title "Buy milk" | confirm | last row "Buy milk", not done |
| 5 | `ui_add_blank_title_shows_title_required` | add form, title "  " | confirm | no row added; message `A title is required.` |
| 6 | `ui_add_end_not_after_start_shows_end_after_start_message` | add form, end == start | confirm | no row added; message `The end must be after the start.` |
| 7 | `ui_add_past_task_is_highlighted_overdue` | clock 14:20; slot 08:00–08:30 | confirm | row added, overdue highlight on |
| 8 | `ui_edit_title_blank_keeps_original` | row "Buy milk" | edit to "  " | row still "Buy milk"; message `A title is required.` |
| 9 | `ui_reschedule_end_not_after_start_keeps_original_times` | row 09:00–10:00 | reschedule end 08:00 | times unchanged; message shown |
| 10 | `ui_toggle_done_strikes_through_and_clears_overdue` | overdue open row | check done | struck through; no overdue highlight; same position |
| 11 | `ui_toggle_undone_restores_overdue_highlight` | done row ended in past | uncheck | not struck through; overdue highlight on |
| 12 | `ui_drag_task_between_a_and_b_rechains_times` | A 09–10, B 10–11:30, C 14–14:30 | drag C to position 2 (index 1) | rows A 09–10, C 10–10:30, B 10:30–12 |
| 13 | `ui_change_day_start_rechains_displayed_times` | day start 09:00; A Fri 10–11, B Fri 11–12 | set day start 08:00 | rows A 08–09, B 09–10; control shows 08:00 |
| 14 | `ui_ctrl_z_restores_last_deleted_task` | deleted B | press Ctrl+Z | B back at its position |
| 15 | `ui_undo_with_nothing_deleted_changes_nothing` | fresh window | trigger undo | list unchanged; no message |
| 16 | `ui_clear_completed_disabled_when_nothing_done` | all open | inspect control | disabled; enabled once a task is done |
| 17 | `ui_clear_completed_removes_done_rows_and_ctrl_z_restores_them` | [A, B done, C] | clear completed, then Ctrl+Z | [A, C] then [A, B, C] |
| 18 | `ui_overdue_highlight_appears_without_user_action` | open task ends 14:30, clock 14:29 | advance clock to 14:31 and let the refresh timer fire (≤ 30 s) | row now highlighted overdue |
| 19 | `ui_save_failure_message_shown_and_change_kept` | store.save raises `StoreWriteError("disk full")` | add a task | message contains "could not save"; row present |
| 20 | `ui_corrupt_store_message_shown_and_list_empty` | store.load raises `StoreCorruptError` | open window | startup message shown; zero rows |
| 21 | `ui_enter_in_add_form_confirms_task` [Could] | form with title "X" | press Enter | task added |
| 22 | `ui_delete_key_deletes_selected_task_and_is_undoable` [Could] | row selected | press Delete, then Ctrl+Z | row removed, then restored |

---

## Data Models / Schemas

### Typed signatures (verified with `mypy` strict; stub at `/tmp/spec_stubs/task_list_spec.pyi`)

```python
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, time, timedelta
from pathlib import Path
from typing import NewType, Protocol

# ---- todo_qt.domain
TaskId = NewType("TaskId", str)
DEFAULT_DAY_START: time = time(9, 0)
DEFAULT_SLOT_DURATION: timedelta = timedelta(minutes=30)


class DomainError(Exception): ...


class EmptyTitleError(DomainError): ...


class InvalidTimeSlotError(DomainError): ...


class EndNotAfterStartError(InvalidTimeSlotError): ...


class InvalidDayStartError(DomainError): ...


class NaiveDatetimeRequiredError(DomainError, ValueError): ...


class TaskNotFoundError(DomainError):
    task_id: TaskId


class DuplicateTaskIdError(DomainError):
    task_id: TaskId


class IndexOutOfRangeError(DomainError, IndexError):
    index: int
    size: int


def normalize_title(raw: str) -> str: ...


@dataclass(frozen=True, slots=True)
class TimeSlot:
    start: datetime
    end: datetime

    def __post_init__(self) -> None: ...
    @property
    def duration(self) -> timedelta: ...


@dataclass(frozen=True, slots=True)
class Task:
    id: TaskId
    title: str
    slot: TimeSlot
    done: bool = False

    def __post_init__(self) -> None: ...


@dataclass(frozen=True, slots=True)
class RemovedEntry:
    index: int  # index in the plan before removal
    task: Task


@dataclass(frozen=True, slots=True)
class RemovedTasks:
    entries: tuple[RemovedEntry, ...]  # non-empty, strictly ascending index, index >= 0

    def __post_init__(self) -> None: ...  # raises ValueError if the invariant is violated


@dataclass(frozen=True, slots=True)
class Plan:
    tasks: tuple[Task, ...] = ()
    day_start: time = DEFAULT_DAY_START

    def __post_init__(self) -> None: ...
    def index_of(self, task_id: TaskId) -> int: ...
    def get(self, task_id: TaskId) -> Task: ...
    def add(self, task_id: TaskId, title: str, slot: TimeSlot) -> Plan: ...
    def edit_title(self, task_id: TaskId, title: str) -> Plan: ...
    def reschedule(self, task_id: TaskId, slot: TimeSlot) -> Plan: ...
    def set_done(self, task_id: TaskId, done: bool) -> Plan: ...
    def delete(self, task_id: TaskId) -> tuple[Plan, RemovedTasks]: ...
    def clear_completed(self) -> tuple[Plan, RemovedTasks | None]: ...
    def restore(self, removed: RemovedTasks) -> Plan: ...
    def move(self, task_id: TaskId, to_index: int) -> Plan: ...
    def set_day_start(self, day_start: time) -> Plan: ...


def default_slot(now: datetime) -> TimeSlot: ...
def is_overdue(task: Task, now: datetime) -> bool: ...


# ---- todo_qt.services
type PlanSnapshot = Plan
type Clock = Callable[[], datetime]
type IdFactory = Callable[[], TaskId]
# SCHEMA_VERSION (= 1) is a storage-format detail owned by the PlanStore implementation
# (placed in todo_qt.persistence by ADR-0003), not part of the services API.


class StoreError(Exception):
    path: Path
    reason: str


class StoreCorruptError(StoreError): ...


class StoreWriteError(StoreError): ...


class PlanStore(Protocol):
    def load(self) -> PlanSnapshot | None: ...
    def save(self, snapshot: PlanSnapshot) -> None: ...


@dataclass(frozen=True, slots=True)
class ChangeResult:
    plan: Plan
    changed: bool
    save_error: StoreWriteError | None = None
    task_id: TaskId | None = None


class PlanService: ...  # members as listed in the PlanService section


# ---- todo_qt.cli
DATA_DIR_ENV_VAR: str = "TODO_QT_DATA_DIR"
type UiRunner = Callable[[PlanService], int]


def resolve_data_dir(environ: Mapping[str, str], default_dir: Path) -> Path: ...
def main(
    argv: Sequence[str] | None = None,
    *,
    environ: Mapping[str, str] | None = None,
    run_ui: UiRunner | None = None,
) -> int: ...
```

Constructor-validity rule on `RemovedTasks`: it is built only by `Plan.delete` / `clear_completed`;
direct construction with empty, non-ascending, or negative indexes raises `ValueError`.

### Persisted schema (logical, format-independent) — `SCHEMA_VERSION = 1`

| Field | Type | Rules |
|---|---|---|
| `schema_version` | integer | required; must equal `1` on load, otherwise `StoreCorruptError` |
| `day_start` | time of day, `HH:MM` | required; minute precision |
| `tasks` | ordered array of task records | required (may be empty); array order = list order |
| `tasks[].id` | string | required; non-empty; unique within the file |
| `tasks[].title` | string | required; non-blank |
| `tasks[].start` | local date-time, minute precision, no zone (`YYYY-MM-DDTHH:MM`) | required |
| `tasks[].end` | local date-time, same format | required; strictly after `start` |
| `tasks[].done` | boolean | required |

Unknown extra fields at version 1 are ignored on load. The undo slot is never persisted. How this
maps to bytes (JSON, SQLite, ...) and where the file lives is decided in Phase 3.

## Non-Functional Requirements
- **Latency:** with 500 tasks, window usable < 2 s after launch (including `store.load()` and
  first render); each add, edit, reschedule, move, delete, and undo — list update plus
  `store.save` — completes in < 200 ms on a typical laptop. `Plan` operations are O(n) in the
  number of tasks.
- **Overdue refresh:** overdue state is re-evaluated at least every 30 s while the window is open
  (guarantees the 60 s requirement).
- **Data safety:** `save` is atomic (previous or new snapshot survives a crash/power loss; never a
  partial file). Unreadable data is never overwritten or destroyed by startup or by later saves
  (see `PlanStore.save` preservation rule).
- **Concurrency:** single user, single process, single thread; the service is not thread-safe and
  saves synchronously. Two simultaneous app instances on one data dir are unsupported (undefined).
- **Security:** data stored only locally in the user's own data directory, directory mode `0o700`
  and file mode `0o600` on POSIX; no network connections of any kind; no secrets involved.
- **Determinism / testability:** the clock, the id factory, and the data location are injected;
  nothing in `domain` or `services` reads the wall clock, environment, or global state.
- **Compatibility:** Python >= 3.14; Linux and macOS; ADR-0001 layering (`domain` imports no other
  layer and no Qt; `services` imports only `domain`; Qt only in `ui`; `cli` imports all).
- **Quality gates:** fully typed under strict mypy; the above interfaces are testable without Qt
  except the UI contract.

## Traceability (acceptance criterion -> interface -> examples)

| Criterion (requirements.md) | Pri | Interfaces | Examples |
|---|---|---|---|
| Launch with no saved tasks: empty window + add | Must | `PlanStore.load`, `PlanService.__init__`, `main`, UI launch | `store_load_returns_none_when_nothing_saved`, `service_starts_empty_when_nothing_saved`, `main_launches_ui_with_empty_service_when_no_saved_data`, `ui_shows_empty_list_and_add_control_when_no_saved_tasks` |
| Launch restores tasks, order, day start | Must | `PlanStore.load/save`, `PlanService.__init__` | `store_roundtrip_preserves_order_titles_times_done_and_day_start`, `service_starts_with_saved_tasks_in_order_and_day_start`, `service_restart_preserves_order_titles_times_done_flags`, `main_launches_ui_with_saved_tasks`, `ui_shows_saved_tasks_in_order_with_day_start` |
| Add pre-fill 14:20 -> 15:00/15:30 | Must | `default_slot`, `PlanService.default_slot`, UI add form | `default_slot_rounds_up_to_next_full_hour`, `default_slot_at_exact_hour_uses_following_hour`, `default_slot_rolls_over_midnight`, `service_default_slot_uses_injected_clock`, `ui_add_form_is_prefilled_with_next_full_hour` |
| Add valid task at bottom, not done | Must | `Plan.add`, `PlanService.add_task` | `add_appends_task_at_bottom_not_done`, `service_add_task_appends_and_saves`, `ui_add_valid_task_appears_at_bottom` |
| Add blank title rejected + message | Must | `normalize_title`, `Plan.add`, `add_task`, UI | `normalize_title_rejects_whitespace_only`, `add_rejects_whitespace_only_title`, `service_add_task_blank_title_raises_and_does_not_save`, `ui_add_blank_title_shows_title_required` |
| Add end not after start rejected + message | Must | `TimeSlot`, UI | `time_slot_rejects_end_equal_to_start`, `time_slot_rejects_end_before_start`, `ui_add_end_not_after_start_shows_end_after_start_message` |
| Add past slot -> overdue | Must | `Plan.add`, `is_overdue`, `overdue_ids`, UI | `add_accepts_slot_entirely_in_past`, `service_add_past_task_is_reported_overdue`, `ui_add_past_task_is_highlighted_overdue` |
| Edit title keeps position/times/done | Must | `Plan.edit_title`, `edit_title` | `edit_title_keeps_position_times_and_done_flag`, `service_edit_title_saves_new_title` |
| Edit blank title rejected | Must | `Plan.edit_title`, `edit_title`, UI | `edit_title_rejects_blank_title_and_keeps_original`, `service_edit_title_blank_keeps_original_and_does_not_save`, `ui_edit_title_blank_keeps_original` |
| Reschedule changes only that task | Must | `Plan.reschedule`, `reschedule` | `reschedule_changes_only_target_task_times`, `reschedule_may_create_overlap`, `service_reschedule_saves_and_leaves_others` |
| Reschedule invalid rejected | Must | `TimeSlot`, UI | `reschedule_with_end_not_after_start_is_rejected_at_slot_construction`, `ui_reschedule_end_not_after_start_keeps_original_times` |
| Mark done: stays, struck through, not overdue | Must | `Plan.set_done`, `set_done`, `is_overdue`, UI | `set_done_marks_task_done_in_place`, `is_overdue_false_for_done_task`, `service_set_done_saves`, `ui_toggle_done_strikes_through_and_clears_overdue` |
| Mark undone: normal, overdue if past | Must | same | `set_done_false_reopens_task`, `is_overdue_returns_after_uncomplete`, `service_uncomplete_makes_past_task_overdue_again`, `ui_toggle_undone_restores_overdue_highlight` |
| Drag C between A and B (cascade) | Must | `Plan.move`, `move_task`, UI drag | `move_into_middle_rechains_tail`, `service_move_task_rechains_and_saves`, `ui_drag_task_between_a_and_b_rechains_times` |
| Drag a non-first task to position i: tail re-chains, above unchanged | Must | `Plan.move` | `move_keeps_tasks_above_destination_unchanged`, `move_first_task_to_end_rechains_from_new_first`, `move_first_task_down_snaps_new_first_to_day_start`, `move_non_first_task_down_leaves_tasks_above_untouched`, `move_preserves_durations_titles_and_ids`, `move_to_own_position_is_noop` |
| Drag first task down: new first task snaps to day start on its own date | Must | `Plan.move` | `move_first_task_down_snaps_new_first_to_day_start`, `move_first_task_down_uses_new_first_tasks_own_date`, `move_first_task_to_end_rechains_from_new_first` |
| Drag to top: day start on old first task's date | Must | `Plan.move` | `move_to_top_starts_at_day_start_on_old_first_tasks_date`, `move_to_top_uses_date_of_previous_first_task_not_moved_task` |
| Cascade re-chains done tasks | Must | `Plan.move` | `move_rechains_done_task_and_keeps_done_flag` |
| Cascade past midnight | Must | `Plan.move` | `move_cascade_crosses_midnight`, `time_slot_spans_midnight` |
| Day start default 09:00 | Must | `Plan()`, `DEFAULT_DAY_START` | `default_day_start_is_nine_oclock`, `service_starts_empty_when_nothing_saved` |
| Day start change persists | Must | `set_day_start`, `PlanStore` | `service_set_day_start_saves_new_day_start_and_rechains`, `service_day_start_survives_restart`, `ui_change_day_start_rechains_displayed_times` |
| Day start change re-chains | Must | `Plan.set_day_start` | `set_day_start_rechains_from_first_task`, `set_day_start_rechains_done_tasks_too`, `set_day_start_rechain_crosses_midnight` |
| Day start on empty list | Must | `Plan.set_day_start` | `set_day_start_on_empty_plan_only_changes_day_start`, `service_set_day_start_on_empty_list_saves_day_start` |
| Day start doesn't affect pre-fill | Must | `default_slot` | `default_slot_ignores_day_start`, `service_add_task_after_day_start_change_still_prefills_next_hour` |
| Delete: others unchanged | Must | `Plan.delete`, `delete_task` | `delete_removes_task_without_touching_others`, `service_delete_removes_task_and_saves` |
| Undo restores at previous position | Must | `Plan.restore`, `undo` | `restore_reinserts_deleted_task_at_previous_index`, `restore_keeps_done_flag_and_times`, `service_undo_restores_deleted_task_at_previous_position`, `ui_ctrl_z_restores_last_deleted_task` |
| Undo only last delete | Must | `undo` | `service_undo_only_restores_last_delete`, `service_undo_twice_after_single_delete_restores_once` |
| Undo with nothing deleted | Must | `undo` | `service_undo_with_nothing_deleted_does_nothing`, `ui_undo_with_nothing_deleted_changes_nothing` |
| Undo is per session | Must | `PlanService.__init__` | `service_new_session_has_no_undo` |
| Clear completed removes done | Must | `Plan.clear_completed`, `clear_completed` | `clear_completed_removes_only_done_tasks`, `service_clear_completed_removes_done_and_saves` |
| Undo clear completed (one delete) | Should | `Plan.restore`, `undo` | `restore_reinserts_cleared_tasks_at_previous_positions`, `service_undo_after_clear_completed_restores_all_cleared`, `ui_clear_completed_removes_done_rows_and_ctrl_z_restores_them` |
| Clear completed disabled when none done | Must | `can_clear_completed`, UI | `clear_completed_with_nothing_done_returns_none`, `service_can_clear_completed_false_when_none_done`, `service_clear_completed_with_nothing_done_is_noop`, `ui_clear_completed_disabled_when_nothing_done` |
| Overdue highlight | Must | `is_overdue`, `overdue_ids`, UI | `is_overdue_true_for_open_task_ended_before_now`, `is_overdue_false_at_exact_end`, `is_overdue_false_for_future_task`, `service_overdue_ids_exclude_done_tasks` |
| Overdue refresh within 60 s | Should | `overdue_ids`, UI timer | `service_overdue_ids_reflect_clock_advancing`, `ui_overdue_highlight_appears_without_user_action` |
| Auto-save on every change | Must | `PlanService` commands, `PlanStore.save` | `service_saves_after_every_kind_of_change`, `service_restart_after_kill_shows_last_change`, `store_save_is_atomic_previous_state_survives_failed_write` |
| Corrupt/unreadable data | Must | `PlanStore.load`, `startup_error`, UI | `store_load_corrupt_data_raises_and_leaves_file_untouched`, `store_load_rejects_unknown_schema_version`, `store_load_rejects_end_not_after_start`, `service_starts_empty_on_corrupt_store_without_saving`, `store_save_after_corrupt_load_preserves_unreadable_content`, `main_with_corrupt_data_still_launches_and_preserves_file`, `ui_corrupt_store_message_shown_and_list_empty` |
| Save failure -> told, change kept | Must | `StoreWriteError`, `ChangeResult.save_error`, UI | `store_save_failure_raises_store_write_error`, `service_keeps_change_in_memory_when_save_fails`, `service_next_successful_save_persists_earlier_unsaved_change`, `ui_save_failure_message_shown_and_change_kept` |
| `TODO_QT_DATA_DIR` | Could | `resolve_data_dir`, `main` | `resolve_data_dir_uses_env_override`, `resolve_data_dir_falls_back_to_default_when_unset`, `resolve_data_dir_treats_empty_value_as_unset`, `main_reads_and_saves_in_override_dir` |
| Enter confirms add form | Could | UI | `ui_enter_in_add_form_confirms_task` |
| Delete key deletes selected | Could | UI, `delete_task` | `ui_delete_key_deletes_selected_task_and_is_undoable` |
| Constraint: user-only permissions | NFR | `PlanStore.save` | `store_files_are_user_only` |

## Out of Scope
- System-tray icon, notifications, and reminders — the next feature, `task-reminders`.
- Running in the background after the window is closed.
- Multiple lists, projects, categories, tags, or priorities.
- Recurring tasks.
- Undo or redo of anything other than the last delete or Clear completed; multi-level undo.
- Undo across app restarts.
- A "sort by start" action, or automatic sorting by time.
- A different day start time per date or weekday; there is one day start for every day.
- Detecting or preventing overlapping tasks (rescheduling may create overlaps; only reordering
  re-chains times).
- Search, filtering, or hiding done tasks.
- Sync, cloud storage, import, or export.
- Windows support.
- Changing time zones while the app runs; times are local wall-clock times.
