# 0006. GUI test stack: pytest-qt with the offscreen Qt platform
Status: Accepted
Date: 2026-10-09

## Context
CI runs `pytest -n auto --cov` on ubuntu-latest without a display, with branch coverage gated at
85%. The UI contract has 22 behavioral examples (22 UI tests) that must run against the real
widgets with a fake store and fixed clock, without blocking modal dialogs.

## Decision
- Add **`pytest-qt>=4.5`** to the `dev` dependency group (MIT). Select the binding explicitly with
  `qt_api = "pyside6"` under `[tool.pytest.ini_options]`.
- `tests/conftest.py` sets `os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")` at import time,
  before any Qt import, so every test and every xdist worker process runs headless on any machine.
- `-n auto` stays: xdist workers are separate processes and pytest-qt's session-scoped `qapp`
  fixture creates one `QApplication` per process. Tests never use fixed file paths or ports;
  data goes to `tmp_path`.
- CI `test` job gains one step before pytest installing the Qt runtime libraries:
  `sudo apt-get update && sudo apt-get install -y --no-install-recommends libegl1 libgl1
  libxkbcommon0 libdbus-1-3 libfontconfig1 libglib2.0-0t64`. (In the 2026-10-09 spike all of these
  were already present on the dev VM and no other library was missing from `ldd` on
  `libQt6Core/Gui/Widgets` and `libqoffscreen.so`; the list is the conservative set for a bare
  ubuntu-latest image.)
- UI code never opens a blocking dialog: messages go to an inline label through an injectable
  notifier, and add / edit use an inline form widget, not `QDialog.exec()`.
- Coverage stays >= 85% by keeping the UI thin (see architecture.md): all rules live in `domain` /
  `services`; message mapping and command handling live in Qt-free `ui` modules covered by fast
  tests; widget code is exercised through `qtbot` tests that call the model and widgets directly
  (for example `model.dropMimeData(...)` instead of simulating mouse drags).

## Consequences
- One new dev dependency in `uv.lock`.
- Tests that need Qt require the system libraries above; a developer without them can still run
  the domain / services / persistence / cli tests by path, because those tests do not import Qt.
- No macOS CI yet (open question in requirements); the offscreen platform is also available on macOS.

## Alternatives considered
- **Xvfb / `xvfb-run` in CI:** needs extra packages and a wrapper command; offscreen is built into Qt.
- **Hand-written `QApplication` fixtures:** pytest-qt already provides `qapp`, `qtbot`, signal
  waiting, and widget cleanup.
- **Mocking Qt:** would not test the actual widgets and would not count toward meaningful coverage.
