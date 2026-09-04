# Phase 2 — GUI Plan (Bel Pelajaran)

> **Purpose.** This document is a complete, self-contained plan to add a
> cross-platform desktop GUI (Windows + Linux) on top of the existing headless
> engine — **and to fully migrate audio to Qt Multimedia**. It assumes **no prior
> session context**; a human *or* an AI coding agent should be able to read this
> and implement it end-to-end.
>
> **Status of the project today (updated 2026-09-04).** Phase 0 and Phase 1 are
> **done and tested**. Phase 2 **Steps 0–6 are implemented**, and the planned
> Step 9 polish is also substantially complete. The GUI can create/open/edit/save
> schedules, run the bell, preview sounds, control volume, show a live countdown,
> minimize/close to tray, and guard destructive actions. Schedule TOML now owns
> its sound-directory setting (`sound_dir`): an empty value uses bundled
> `assets/`; a non-empty value must be absolute. Missing paths/files no longer
> destroy or reject loaded `file` values; filesystem checks happen immediately
> before Start and before editing a row. The suite currently has **53 passing
> tests**. Step 7 remains optional; **Step 8 (packaging and clean-machine
> validation) is the next required step**.

---

## 0. Orientation (read this first)

### 0.1 What this app is
An automatic school bell (`bel sekolah`). It plays mp3 sound files at scheduled
times, six days a week (Senin–Sabtu). It exists because the physical bell broke.
The #1 problem being solved by the GUI: **right now only one person can use it,
because the schedule is configured by hand-editing TOML text files.** The GUI's
job is to let a non-technical teacher manage the schedule and run the bell.

### 0.2 If you are an AI agent / new developer
Run these to orient before coding:
```bash
cd bel-pelajaran-py
uv sync                                   # sets up Python 3.12 venv
cat README.md                             # overall structure + commands
sed -n '1,140p' app/scheduler.py          # the engine you will drive
sed -n '1,110p' app/config.py             # load + validate schedule
sed -n '1,100p' app/models.py             # Bell / Timetable dataclasses
sed -n '1,110p' app/audio.py              # AudioBackend + QtMultimediaBackend
sed -n '1,90p'  app/paths.py              # resource resolution (dev + frozen exe)
uv run pytest                             # must be green before you start
uv run bel check configs/konfig.toml      # smoke: validates the real schedule
```
All UI strings are **Indonesian** (keep that). Code identifiers are English.

### 0.3 Tech stack (target after Phase 2)
| Concern | Choice | Why |
|---|---|---|
| Language / env | Python 3.12, **uv** | `requires-python = ">=3.11,<3.14"`; `.python-version=3.12` |
| UI toolkit | **PySide6** (Qt6) | native Win+Linux, great widgets, PyInstaller hooks, LGPL |
| Audio | **Qt Multimedia** (`QMediaPlayer`+`QAudioOutput`) | single Qt stack, native async (non-blocking), more capable. mp3 via OS codecs (WMF on Win, GStreamer on Linux). See §3.2 for the codec caveat + mandatory self-test. |
| Scheduler | `schedule` lib (engine-internal) | already working; fine for MVP (APScheduler is a *separate* future task) |
| Config | `tomllib` (stdlib, read) + `tomli_w` (write, new in Phase 2) | |
| Packaging | PyInstaller | groundwork already in `app/paths.py` (`sys._MEIPASS`) |
| **Removed in Phase 2** | ~~pygame~~ | replaced wholesale by Qt Multimedia (see §3.2) |

---

## 1. The contract you are building on (current public API)

These are the **stable surfaces** the GUI imports. Sections marked **[CHANGES]**
are modified in Phase 2; the rest stays as-is.

### `app/models.py`  **[CHANGED — schedule-specific sound directory]**
```python
DAYS: tuple[str, ...]              # ("senin","selasa","rabu","kamis","jumat","sabtu")
WEEKDAY_TOKEN: dict[str,str]       # "senin"->"monday", ...
DAY_LABEL: dict[str,str]           # "senin"->"Senin", "jumat"->"Jum'at"

@dataclass(frozen=True)
class Bell:
    jam: str     # "HH:MM" 24-hour
    file: str    # bare filename inside configured sound dir (default: assets/)

@dataclass
class Timetable:
    days: dict[str, list[Bell]] = field(default_factory=dict)
    sound_dir: str = ""  # absolute path; empty selects bundled assets/
    # iterates (day, bells) in canonical DAYS order
    def bells_for(self, day: str) -> list[Bell]
    @property
    def total(self) -> int
    def all_bells(self) -> Iterator[tuple[str, Bell]]
```

### `app/config.py`  **[CHANGED — structural/filesystem validation split]**
```python
def load_timetable(path: str | Path) -> Timetable          # reads TOML
def parse_timetable(data: dict) -> Timetable               # from already-parsed dict
def validate_timetable(timetable: Timetable) -> ValidationResult  # no filesystem access
def resolve_sound_dir(timetable: Timetable) -> Path                # empty -> assets/
def validate_sound_files(timetable: Timetable) -> ValidationResult # before Start
def is_valid_time(s: str) -> bool

@dataclass class ValidationError:  day:str; message:str; jam:str|None=None; file:str|None=None
@dataclass class ValidationResult: errors: list[ValidationError]
    @property
    def ok(self) -> bool
```
Current TOML schema:
```toml
# Empty selects bundled assets/. A non-empty value must be an absolute path.
sound_dir = ""
# sound_dir = "D:/Bel Sekolah/suara"       # Windows example
# sound_dir = "/opt/bel-sekolah/suara"    # Linux example

[[senin]]
jam = "07:00"
file = "1.mp3"  # remains a bare filename
```

Decisions:
- `sound_dir` belongs to each schedule file; it is **not** a global/per-user
  `QSettings` value.
- `validate_timetable()` checks time/duplicate/schema values without filesystem
  access. This lets a stale schedule open without losing its `file` values.
- `validate_sound_files()` checks the directory and referenced files immediately
  before Start. The GUI also checks the selected row immediately before editing.
- Missing/relative directories produce a dismissible error notice while the
  table remains editable. The sound delegate preserves a missing filename in
  its dropdown so the teacher can repair either the path or filename.
- Saving emits `sound_dir = ""` for the default, otherwise an absolute path.

Days omitted from the TOML configuration remain empty. The GUI tracks
explicitly defined days so saving does not add omitted days.

### `app/audio.py`  **[CHANGES — rewritten in Phase 2]**
It now provides `AudioBackend` (Protocol), **`QtMultimediaBackend`**, and
`NullBackend`. `PygameBackend` and the pygame dependency are deleted. The
Protocol is preserved:
```python
class AudioBackend(Protocol):                 # runtime_checkable
    def play(self, path: Path) -> bool
    def stop(self) -> None
    def is_playing(self) -> bool
    def set_volume(self, value: float) -> None
```
> **Contract nuance under Qt Multimedia:** `play()` is *asynchronous* — it returns
> `True` to mean "playback requested", not "playback succeeded". Decode/runtime
> errors arrive later via `QMediaPlayer.errorOccurred`, which the backend forwards
> to the scheduler's `on_error` callback (§4.3). Do not treat a `True` return as a
> guarantee the bell will sound; the startup self-test (§3.2) is what validates that.

### `app/scheduler.py`  **[CHANGES — small additions in Phase 2]**
```python
class BellScheduler:
    def __init__(self, timetable, backend, *,
                 on_fire=None, on_error=None, sound_dir=None) -> None
    def arm(self) -> int                      # returns #bells armed; safe per-bell
    def tick(self) -> None                    # NEW: one scheduler step, for QTimer-driven use (§4.2)
    def run(self, interval: float = 1.0)      # BLOCKING loop — retained ONLY for headless NullBackend tests
    def stop(self)                            # signals a blocking run() to exit
    def next_bell_today(self) -> tuple[str, Bell] | None
```
`_fire(day, bell)` resolves `bell.file` below the scheduler's optional
`sound_dir`, then invokes the backend and guarded callbacks. Qt apps use `arm()` + a `QTimer` calling `tick()`
(§4.2); the blocking `run()` is kept only so Qt-free unit tests / `--dry-run`
still work with `NullBackend`.

### `app/paths.py`  (updated — platform-standard user directories)
```python
def is_frozen() -> bool
def app_root() -> Path        # _MEIPASS when frozen, else project root
def assets_dir() -> Path      # app_root()/"assets"
def configs_dir() -> Path     # app_root()/"configs"
def asset(filename: str) -> Path
def config_dir() -> Path      # XDG_CONFIG_HOME / APPDATA / macOS Application Support
def data_dir() -> Path        # XDG_DATA_HOME / LOCALAPPDATA / macOS Application Support
def state_dir() -> Path       # XDG_STATE_HOME / LOCALAPPDATA / macOS Logs
def schedules_dir() -> Path   # config_dir()/schedules
def logs_dir() -> Path
def user_data_dir() -> Path   # compatibility alias for config_dir()
```

---

## 2. Goals & non-goals

### Current delivery status
| Area | Status |
|---|---|
| Engine hardening / layer separation | ✅ Complete |
| Qt Multimedia migration + CLI Qt loop | ✅ Complete |
| GUI view/edit/save/start/stop | ✅ Complete |
| Live status, countdown, last-fired highlight | ✅ Complete |
| Sound preview, shared volume, startup self-test | ✅ Complete |
| Schedule-specific absolute `sound_dir` | ✅ Complete |
| SVG app/tray icons and minimize-to-tray | ✅ Complete |
| Unsaved-change/stop confirmations; dismissible notices | ✅ Complete |
| Multi-config switcher / exam selector | ⏭ Optional, not implemented |
| PyInstaller build automation and clean-machine matrix | ⏳ Next required work |

### MVP goals (must ship)
1. **Open & view** a schedule (`configs/*.toml`) as an editable table.
2. **Edit** bells: add / edit / delete. Pick time (time widget) and **sound from a
   dropdown of the configured sound folder's `*.mp3` files** (default:
   `assets/`; no typing filenames — this is the whole point).
3. **Save** the edited schedule back to TOML (round-trip).
4. **Start / Stop** the bell engine from the GUI; show clear Running/Stopped state.
5. **Live status**: "next bell today" + countdown, "last fired" indicator.
6. **Test a sound** (play button) and a **volume** slider.
7. **Audio runs entirely on Qt Multimedia** (pygame removed) on Windows + Linux.

### Non-goals for Phase 2 (explicitly defer)
- Persisting schedules in a database (TOML files remain the source of truth).
- Multi-user / network / remote control.
- Running as an OS service / autostart (separate task; GUI can *launch* the
  engine in-process, that's enough).
- Replacing the `schedule` library (APScheduler swap is its own task).
- Mobile / web.
- Keeping pygame as a runtime fallback. (The migration is **full**; see §3.2 for
  the documented escape hatch if a deployment target truly can't decode mp3.)

### Stretch goals (nice-to-have, time permitting)
- ⏳ "Add sound" button: copy a new mp3 into the configured sound directory.
- ⏳ Multi-config switcher ("Jadwal aktif" dropdown → exam mode by loading
  `konfig_ujian.toml`).
- ✅ System-tray icon with start/stop/restore/quit; minimize and close hide to tray.
- ⏳ Log tail viewer.

---

## 3. Framework decisions

### 3.1 UI toolkit: use **PySide6**
**Decision: PySide6 (Qt for Python).**

| Option | Verdict |
|---|---|
| **PySide6** ✅ | Mature, native-looking on Win+Linux, excellent PyInstaller hooks (auto-bundles Qt plugins), `QTableView`/`QTimeEdit`/file dialogs built-in, signal/slot maps cleanly onto engine callbacks. LGPL — fine for this. |
| Flet | Prettier, but packaging to a robust offline exe is riskier (bundled Flutter engine, hook maturity). Not worth the risk for a school PC. |
| Tkinter | Zero-dependency + tiny exe, but dated look and weaker table widgets. Acceptable fallback only if exe size is critical. |

Add it as an **optional extra** so people who only want the headless `bel --dry-run`
/ `check` path don't *have* to pull Qt — but note: real audio now needs Qt (§3.2),
so `bel start` (with sound) requires the `gui`/`qt` extra installed:
```toml
# pyproject.toml
[project.optional-dependencies]
qt = ["PySide6>=6.7,<7", "tomli_w>=1,<2"]   # Qt Multimedia ships inside PySide6
gui = ["PySide6>=6.7,<7", "tomli_w>=1,<2"]
[dependency-groups]
dev = ["pytest>=8", "pyinstaller>=6", "PySide6>=6.7,<7", "tomli_w>=1,<2"]
```
Install for dev: `uv sync --extra qt` (or `--all-extras`).

> **pygame is removed from `[project.dependencies]` in Step 0.** The CLI modules
> that need audio import PySide6 lazily (inside the command), so `bel check` /
> `bel sounds` / `--dry-run` still run without Qt installed.

### 3.2 Audio: FULL migration to Qt Multimedia

**Decision: Qt Multimedia (`QMediaPlayer` + `QAudioOutput`) becomes the *only*
audio backend. pygame is removed entirely.** This applies to the GUI **and** the
headless CLI (they share the audio backend).

```python
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
from PySide6.QtCore import QUrl
player = QMediaPlayer()
out = QAudioOutput(); player.setAudioOutput(out)
player.setSource(QUrl.fromLocalFile(str(path)))   # local mp3
out.setVolume(0.8)
player.play()                                      # async, non-blocking
# state: player.playbackState() == QMediaPlayer.PlaybackState.PlayingState
# errors: player.errorOccurred.connect(lambda code, msg: ...)
```

**Why Qt Multimedia over pygame:** one multimedia stack (no SDL), native async
playback, more capable (seek/position/duration/metadata, ready for future video
or streaming), and it already matches the chosen UI toolkit. The maintainer
accepts the codec caveat below for the single-school, uniform-PC deployment.

**The codec/backend caveat (be honest about it).** Qt Multimedia backend choice
varies with Qt version, platform, and packaging. The current Linux development
environment (PySide6 6.11) reports Qt's **FFmpeg** multimedia backend. Other Qt
builds can use native Windows/macOS frameworks or GStreamer on Linux. Therefore,
do not encode a deployment assumption such as “all Linux hosts have GStreamer”
or “PyInstaller always includes every decoder.” The executable must prove audio
on the actual target image.

| Target | Expected backend | Required decision |
|---|---|---|
| Windows | Qt FFmpeg and/or Windows native media backend | Verify the frozen build on a clean Windows PC. |
| Linux | Qt FFmpeg in the current dev build; GStreamer is possible in other builds | Verify backend plugins and MP3 playback on the school image. |
| macOS | Not a Phase 2 target | No release validation currently required. |

**Why the residual risk is acceptable:** the school runs a uniform PC image, so
codec availability can be validated once per deployed image. The mandatory
self-test remains the source of truth regardless of which backend Qt selects.

**Mandatory mitigation — startup audio self-test (fail LOUDLY).** The dangerous
property of `QMediaPlayer` on a missing-codec machine is that it does **not**
crash — it emits `errorOccurred` and plays *nothing*. So on startup (and after
packaging) the app **must** attempt to play a short clip and, on failure, surface
a big red, dismissible banner/dialog or non-zero CLI exit: *"Audio tidak dapat
memutar mp3 — periksa perangkat audio dan plugin codec."* This converts a silent Monday-morning catastrophe
into a visible, fixable error. Sketch in §7.4. Test once on each target OS image.

> **Documented escape hatch (NOT a Phase 2 deliverable):** if a specific
> deployment target ever fails the self-test and cannot be fixed, the deleted
> `PygameBackend` (zero-host-deps, bundled libmpg123) still exists in git history
> and can be revived as an optional backend behind the unchanged `AudioBackend`
> Protocol. Do not build this preemptively — full migration is the decision.

**Consequence #1 — the CLI needs Qt too.** Because Qt Multimedia is the only
backend, the headless `bel start` must create a `QCoreApplication` and run a Qt
event loop to drive `QMediaPlayer` (§4.2). `--dry-run` (`NullBackend`) stays
Qt-free for CI/tests. This is accepted under full migration.

**Consequence #2 — thread affinity drives the new threading model.** See §4.2.

---

## 4. Architecture

### 4.1 Module layout
```
app/
  audio.py                # REWRITTEN: AudioBackend Protocol + QtMultimediaBackend + NullBackend
  scheduler.py            # +on_fire/on_error, +tick()   (small additions)
  gui/
    __init__.py
    __main__.py            # `python -m app.gui`  -> launches the app
    qt_app.py              # shared QApplication/QCoreApplication factory + SIGINT handler
    controller.py          # BellController(QObject): owns scheduler, QTimer, status signals
    main_window.py         # QMainWindow: layout, menus, status bar
    schedule_table.py      # QAbstractTableModel over one day's bells + editor delegates
    sound_picker.py        # combo + preview button + volume slider
    settings.py            # sound-folder dialog + MP3 discovery helpers
    audio_selftest.py      # startup mp3 self-test (§3.2) — LOUD on failure
    toml_io.py             # TOML write + explicit-day preservation helpers
  ...models/config/paths/cli...
assets/
  app_icon.svg             # application/window icon
  tray_icon.svg            # system-tray icon
run_gui.py                 # top-level launcher for PyInstaller (mirrors run.py)
```
Add a console script:
```toml
[project.scripts]
bel = "app.cli:main"
bel-gui = "app.gui.__main__:main"
```

### 4.2 Event-loop & threading model (critical — read carefully)

**Single-threaded.** Everything runs on the **Qt main thread**. There is **no
scheduler worker thread** (the old Phase-0 design used one because pygame's play
blocked; Qt Multimedia is non-blocking, so the worker thread is no longer needed).

- The Qt event loop (`QApplication.exec()` for GUI, `QCoreApplication.exec()` for
  headless CLI) is the main loop.
- A `QTimer(interval=1000ms)` on the main thread calls `engine.tick()`, which
  runs `schedule.run_pending()` → `_fire(day, bell)` → `backend.play(path)`
  (`QMediaPlayer`, all on the main thread). Non-blocking, so the event loop never
  stalls and a long clip can't delay the next bell.
- Because `QMediaPlayer` has **thread affinity** (must be used on the thread it
  was created in), constructing it and calling `play()` on the main thread is the
  *correct* usage — no cross-thread marshalling, no "never touch widgets from a
  worker thread" rule.

```
  ┌─────────────────────── Qt main thread ───────────────────────┐
  │  QApplication.exec()  (event loop)                            │
  │     │                                                         │
  │     ├── QTimer(1s) ──► engine.tick() ──► run_pending()        │
  │     │                                        └─ _fire(day,bell)│
  │     │                                              └─ backend.play()  (QMediaPlayer)
  │     ├── BellController.on_fire ──► update UI (same thread)    │
  │     └── widgets, menus, file dialogs, self-test               │
  └───────────────────────────────────────────────────────────────┘
```

**Why the old `run()`/`start_in_thread()` is retained:** only so Qt-free unit
tests and `bel start --dry-run` (`NullBackend`) keep working without a Qt event
loop. Qt apps ignore it and use `arm()` + `tick()` + the event loop. The GUI also
retains one shared Qt audio backend across preview and scheduler use; Stop halts
playback/jobs but does not recreate the multimedia stack unnecessarily.

### 4.3 Small engine additions (Step 0)
The controller wants to know *which bell fired* and *when a job errors*, and Qt
apps drive the loop via `tick()`. Add three things to `BellScheduler` (the only
engine changes):

```python
# app/scheduler.py — extend __init__
class BellScheduler:
    def __init__(self, timetable, backend, *,
                 on_fire: Callable[[str, Bell], None] | None = None,
                 on_error: Callable[[str, Bell, BaseException], None] | None = None) -> None:
        ...
        self._on_fire = on_fire
        self._on_error = on_error

    def tick(self) -> None:
        """Advance the scheduler one step. For QTimer-driven use (Qt main thread)."""
        try:
            sched_lib.run_pending()
        except Exception:
            log.exception("error pada run_pending (dilanjutkan)")
```
In `_fire()`:
```python
def _fire(self, day, bell):
    try:
        path = asset(bell.file)
        log.info(">>> BELL [%s %s] %s", day, bell.jam, bell.file)
        if not self.backend.play(path):
            log.error("bell tidak terputar: %s %s (%s)", day, bell.jam, bell.file)
        if self._on_fire:
            try: self._on_fire(day, bell)
            except Exception: log.exception("on_fire callback error")
    except Exception as exc:
        log.exception("error tak terduga saat membunyikan bell: %s", exc)
        if self._on_error:
            try: self._on_error(day, bell, exc)
            except Exception: pass
```
Keep it fully exception-guarded (a bad callback must never stop the day).
Add `tests/test_scheduler.py`: a dummy backend + `on_fire` fires; `tick()` calls
`run_pending`.

---

## 5. Key risks & mitigations

| Risk | Mitigation |
|---|---|
| **`QMediaPlayer` thread affinity → crash if used off the main thread** | Use the single-thread QTimer model (§4.2). Construct `QMediaPlayer` and call `play()` **only** on the Qt main thread. The Spike (Step 2) proves this. |
| **Qt Multimedia silent failure on missing Linux GStreamer codecs** | Mandatory **startup self-test** (§3.2, §7.4) that fails LOUDLY. Test once on the school's actual Linux image. (Escape hatch: revive `PygameBackend` from git — §3.2, not built by default.) |
| **CLI needs a Qt event loop now** | `cmd_start` builds a `QCoreApplication` + `QTimer`→`tick()` + a SIGINT→`quit()` handler (§7.3). `--dry-run` stays Qt-free. |
| **SIGINT (Ctrl+C) doesn't quit a Qt event loop by default** | Install `signal.signal(SIGINT, lambda *_: app.quit())` **and** keep a short heartbeat `QTimer` (~200ms) so Python signal handlers actually run (needed especially on Windows). |
| **Saving TOML drops comments / reformats** | Use `tomli_w`; document that saving normalizes the file. If comment-preservation is later required, swap to `tomlkit` — out of MVP scope. |
| **Windows `--add-data` separator is `;` not `:`** | The build script picks by `os.name` (§8). |
| **`schedule` fires by wall-clock weekday** | Already handled (`WEEKDAY_TOKEN`). `next_bell_today()` already uses `datetime.weekday()`. Nothing to do. |
| **Frozen exe missing Qt multimedia plugins / silent on Linux** | `--collect-submodules PySide6` (and ensure `PySide6/Qt/plugins/multimedia` is collected). The self-test is the safety net on the frozen Linux build. |
| **Qt Multimedia API churn around 6.2** | Verify the exact `QMediaPlayer`/`QAudioOutput` API against the installed PySide6 version (`player.playbackState()`, `errorOccurred(code,msg)`); don't trust memory. |

---

## 6. Implementation steps (do in order; each is independently verifiable)

Each step ends with **Done when:** acceptance criteria.

### Step 0 — Prerequisites, engine hooks, Qt audio backend
- **Remove pygame** from `[project.dependencies]`; add the `qt`/`gui` extras
  (§3.1). `uv sync --extra qt`.
- Add `on_fire`/`on_error` + `tick()` to `BellScheduler` (§4.3).
- **Rewrite `app/audio.py`:** keep `AudioBackend` Protocol + `NullBackend`; delete
  `PygameBackend`; add `QtMultimediaBackend` (sketch §7.2). Wire
  `player.errorOccurred` → an `on_error` callable passed to the backend.
- Add `app/gui/audio_selftest.py` (`self_test_audio(...)`, sketch §7.4).
- Add `save_timetable()` to `app/gui/toml_io.py` (only writes defined days).
- **Done when:** `uv run pytest` green (existing 17 + new scheduler-callback
  tests); `import app.audio` imports Qt lazily so non-audio CLI still works
  without PySide6 installed.

### Step 1 — Migrate the CLI to Qt audio (de-risk BEFORE the GUI)
- Rewrite `cmd_test_sound` and `cmd_start` to use `QCoreApplication` +
  `QTimer`→`tick()` + `QtMultimediaBackend` + SIGINT handler (sketch §7.3).
  `--dry-run` keeps using `NullBackend` and may stay Qt-free.
- Run the startup self-test at the top of `cmd_start`; exit non-zero with a clear
  message if mp3 can't decode.
- **Done when:** `uv run bel test-sound 1.mp3` plays via `QMediaPlayer`;
  `uv run bel start configs/example.toml` (with a bell ~20s out) rings through
  Qt Multimedia and Ctrl+C exits cleanly — on **both Windows and Linux**. This
  proves the Qt-audio model headlessly before any GUI code.

### Step 2 — Spike: minimal window + engine (de-risk the GUI integration)
- `app/gui/qt_app.py`: shared `get_qapp()` factory + SIGINT wiring.
- `app/gui/main_window.py`: a `QMainWindow` with one "Start" button + a label.
- `app/gui/controller.py`: `BellController(QObject)` — owns the engine + a
  `QTimer(1000)` calling `engine.tick()`; emits `status`/`next_bell`/`fired`/
  `error` signals; Start/Stop create/stop the engine. (sketch §7.1)
- Load `configs/example.toml` hardcoded for the spike.
- **Done when:** window opens, Start arms + ticks the engine on the main thread,
  a bell scheduled ~20s ahead plays via Qt Multimedia, Stop ends cleanly, no
  crash, no Qt threading warnings — on both OSes.

### Step 3 — Read-only schedule view
- Day selector (tabs or combo for `DAYS`) + a `QTableView`.
- `app/gui/schedule_table.py`: `QAbstractTableModel` over the selected day's
  `list[Bell]` (columns: Jam, Suara). Switching day repopulates the model.
- "Open…" loads any `configs/*.toml` via `load_timetable()`; show validation
  errors (from `validate_timetable`) in a dialog if `not result.ok`.
- **Done when:** `konfig.toml` loads and all bells show, per day, correctly.

### Step 4 — Editing + Save
- Add/Edit/Delete bell rows. Time via `QTimeEdit` (HH:mm); sound via the
  sound-picker combo. Edits mutate the working `Timetable`; the model emits
  `dataChanged`/`layoutChanged`.
- "Save" writes via `save_timetable()`; "Save As…" picks a new filename under
  `schedules_dir()` (or `configs/`). Warn that comments are dropped.
- Re-validate before Save; block + show errors if invalid.
- **Done when:** a teacher can build a full week schedule from scratch and the
  saved file passes `uv run bel check <file>` (round-trip proven).

### Step 5 — Live status
- Status bar: Running ●/○, "Bell berikutnya: Selasa 09:40 → istirahat.mp3
  (dalam 4 mnt)", "Terakhir berbunyi: …".
- `on_fire` → flash the matching row / status.
- **Done when:** with `example.toml` running, the next-bell countdown ticks down
  and updates when a bell fires.

### Step 6 — Sound picker, test, volume
- `app/gui/sound_picker.py`: combo from the persistent configured sound folder
  (default `assets/`), with a ▶ "Putar" button using the shared
  `QtMultimediaBackend`.
- Volume `QSlider` (0.0–1.0) → `backend.set_volume()` (on `QAudioOutput`).
- (Stretch) "Tambah suara…" → file dialog → copy mp3 into `assets/`, refresh.
- **Done when:** any sound can be previewed without starting the scheduler;
  volume changes are audible.

### Step 7 — (Stretch) Multi-config / exam mode
- "Jadwal aktif" dropdown listing `configs/*.toml`. Selecting loads + (if running)
  stops→re-arms the new timetable. Exam mode = selecting `konfig_ujian.toml`.
- **Done when:** switching config re-arms without restarting the app.

### Step 8 — Packaging (PyInstaller + PySide6 + Qt Multimedia)
- `scripts/build_exe.py` (cross-platform) or documented commands (§8).
- Produce a **folder** dist (`--onedir`, recommended) and optionally `--onefile`.
- **Test the produced binary on a clean Windows machine and on the target Linux
  image** — and confirm the startup self-test passes there.
- **Done when:** double-clicking the exe (no Python/Qt installed) opens the GUI,
  loads bundled `configs/`+`assets/`, passes the audio self-test, plays sound,
  and Start/Stop works.

### Step 9 — Polish
- App/tray SVG icons, window title `Bel Pembelajaran`, sensible min size.
- Confirmation on Stop while running; unsaved-changes guard on new/open/quit.
- Error toasts for backend-init failure (fall back to `NullBackend` + warn, as CLI does).
- System tray: minimize/close hides the window while the scheduler keeps running;
  use **Aplikasi → Keluar Sepenuhnya** (or the tray menu) to terminate.

---

## 7. Code sketches for the integration-critical pieces

> Verify every `QMediaPlayer`/`QAudioOutput` call against the installed PySide6
> version before trusting these sketches (Qt Multimedia API moved around 6.2).

### 7.1 `app/gui/controller.py` (single-thread QTimer model)
> **Superseded by implementation.** This sketch predates the shipped code and
> is kept only to explain the model. The real controller additionally:
> keeps **one shared backend** across preview and scheduler (`_ensure_backend()`,
> created lazily, not per-Start), exposes `use_timetable()`, `set_sound_dir()`,
> `preview_sound()`, `shutdown()`, tracks `last_error`, and runs
> `validate_sound_files()` before arming (Start is refused with the error list
> when sounds are missing). Trust `app/gui/controller.py` over this sketch.
```python
from __future__ import annotations
from pathlib import Path
from PySide6.QtCore import QObject, Signal, QTimer
from app.audio import AudioBackend, NullBackend, QtMultimediaBackend
from app.config import load_timetable, validate_timetable
from app.models import Timetable, DAY_LABEL
from app.scheduler import BellScheduler

class BellController(QObject):
    status          = Signal(str)
    next_bell       = Signal(str, str, str)   # day_label, "HH:MM", filename ("" if none)
    fired           = Signal(str, str, str)   # day_label, jam, filename
    error           = Signal(str)
    running_changed = Signal(bool)

    def __init__(self) -> None:
        super().__init__()
        self.timetable: Timetable | None = None
        self.scheduler: BellScheduler | None = None
        self.backend: AudioBackend = NullBackend()
        self._volume = 1.0
        self._timer = QTimer(self); self._timer.setInterval(1000)
        self._timer.timeout.connect(self._on_tick)

    def load(self, path: str | Path) -> bool:
        try:
            tt = load_timetable(path)
        except Exception as exc:
            self.error.emit(f"Gagal membaca konfig: {exc}"); return False
        res = validate_timetable(tt)
        if not res.ok:
            self.error.emit("; ".join(f"[{e.day}] {e.message}" for e in res.errors)); return False
        was_running = self.scheduler is not None
        if was_running: self.stop()
        self.timetable = tt
        self.status.emit(f"Dimuat: {Path(path).name} ({tt.total} bell)")
        if was_running: self.start()
        else: self._emit_next()
        return True

    def start(self) -> None:
        if not self.timetable or self.scheduler: return
        try:
            self.backend = QtMultimediaBackend(volume=self._volume,
                on_error=lambda msg: self.error.emit(f"Audio error: {msg}"))
        except Exception as exc:
            self.error.emit(f"Audio gagal init ({exc}); mode senyap."); self.backend = NullBackend()
        self.scheduler = BellScheduler(
            self.timetable, self.backend,
            on_fire=lambda d, b: self.fired.emit(DAY_LABEL[d], b.jam, b.file),
            on_error=lambda d, b, e: self.error.emit(f"Error bell {d} {b.jam}: {e}"),
        )
        self.scheduler.arm()
        self.scheduler.tick()              # immediate first tick
        self._timer.start()
        self.running_changed.emit(True); self._on_tick()

    def stop(self) -> None:
        if self.scheduler:
            self.scheduler.stop(); self.backend.stop(); self.scheduler = None
        self._timer.stop(); self.running_changed.emit(False)
        self.status.emit("Berhenti.")

    def set_volume(self, v: float) -> None:
        self._volume = v; self.backend.set_volume(v)

    # ---- all of this runs on the Qt main thread ---------------------------
    def _on_tick(self) -> None:
        if self.scheduler:
            self.scheduler.tick()
            self.status.emit("Berjalan" + (" (memutar…)" if self.backend.is_playing() else ""))
        self._emit_next()

    def _emit_next(self) -> None:
        if self.timetable and self.scheduler:
            nb = self.scheduler.next_bell_today()
            if nb: d, b = nb; self.next_bell.emit(DAY_LABEL[d], b.jam, b.file); return
        self.next_bell.emit("", "", "")
```

### 7.2 `app/audio.py` — `QtMultimediaBackend` (replaces PygameBackend)
```python
import logging
from pathlib import Path
from typing import Callable, Protocol, runtime_checkable

log = logging.getLogger(__name__)

@runtime_checkable
class AudioBackend(Protocol):
    def play(self, path: Path) -> bool: ...
    def stop(self) -> None: ...
    def is_playing(self) -> bool: ...
    def set_volume(self, value: float) -> None: ...

class NullBackend:                                  # unchanged: dry-run / tests
    def play(self, path): log.info("[null] akan memutar %s", path.name); return True
    def stop(self): pass
    def is_playing(self): return False
    def set_volume(self, value): pass

class QtMultimediaBackend:
    """Plays via QMediaPlayer. MUST be constructed and used on the Qt main thread."""
    def __init__(self, volume: float = 1.0,
                 on_error: Callable[[str], None] | None = None) -> None:
        from PySide6.QtCore import QUrl                        # imported lazily
        from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
        self._QUrl = QUrl
        self._player = QMediaPlayer()
        self._out = QAudioOutput()
        self._player.setAudioOutput(self._out)
        self._Playing = QMediaPlayer.PlaybackState.PlayingState
        if on_error:
            # errorOccurred(ErrorCode err, const QString &errorString)
            self._player.errorOccurred.connect(lambda _code, msg: on_error(msg))
        self.set_volume(volume)

    def play(self, path: Path) -> bool:           # async: True == "requested"
        try:
            self._player.setSource(self._QUrl.fromLocalFile(str(path)))
            self._player.play()
            log.info("memutar: %s", path.name); return True
        except Exception as exc:
            log.error("gagal memutar %s: %s", path, exc); return False

    def stop(self) -> None:
        try: self._player.stop()
        except Exception: pass

    def is_playing(self) -> bool:
        try: return self._player.playbackState() == self._Playing
        except Exception: return False

    def set_volume(self, value: float) -> None:
        try: self._out.setVolume(max(0.0, min(1.0, float(value))))
        except Exception: pass
```

### 7.3 CLI Qt loop — `cmd_start` headless path
```python
def cmd_start(args) -> int:
    ...
    from PySide6.QtCore import QCoreApplication, QTimer
    import signal
    app = QCoreApplication.instance() or QCoreApplication(sys.argv)

    if args.dry_run:
        backend = NullBackend()                    # Qt-free path
    else:
        from app.audio import QtMultimediaBackend
        ok, msg = self_test_audio_factory(backend_cls=QtMultimediaBackend,
                                          sample=asset(sorted(...)[0]))
        if not ok:
            print(f"Audio gagal memutar mp3: {msg} — periksa codec/GStreamer.", file=sys.stderr)
            return 3
        backend = QtMultimediaBackend(volume=args.volume,
                   on_error=lambda m: print(f"audio: {m}", file=sys.stderr))

    engine = BellScheduler(timetable, backend, on_fire=..., on_error=...)
    engine.arm(); engine.tick()
    timer = QTimer(); timer.setInterval(1000); timer.timeout.connect(engine.tick); timer.start()
    signal.signal(signal.SIGINT, lambda *_: app.quit())   # Ctrl+C -> quit
    heartbeat = QTimer(); heartbeat.setInterval(200)      # let Python run signal handlers
    heartbeat.timeout.connect(lambda: None); heartbeat.start()
    app.exec()
    engine.stop(); backend.stop()
    return 0
```

### 7.4 Startup audio self-test — `app/gui/audio_selftest.py`
```python
from pathlib import Path

def self_test_audio(make_backend, sample: Path, timeout_ms: int = 3000) -> tuple[bool, str]:
    """Try to play `sample` via a freshly built backend; return (ok, message).

    Blocks on a nested QEventLoop until EndOfMedia (ok), errorOccurred (fail),
    or timeout (fail). MUST run on the Qt main thread."""
    from PySide6.QtCore import QEventLoop, QTimer
    from PySide6.QtMultimedia import QMediaPlayer
    result = {"ok": False, "msg": ""}
    backend = make_backend(on_error=lambda m: (result.update(ok=False, msg=m)))
    player: QMediaPlayer = backend._player
    loop = QEventLoop()
    def on_status(s):
        if s == QMediaPlayer.MediaStatus.EndOfMedia:
            result.update(ok=True, msg="ok"); loop.quit()
    player.mediaStatusChanged.connect(on_status)
    player.errorOccurred.connect(lambda _c, m: (result.update(ok=False, msg=m), loop.quit()))
    QTimer.singleShot(timeout_ms, lambda: (result.update(msg=result["msg"] or "timeout"), loop.quit()))
    backend.play(sample)
    loop.exec()
    backend.stop()
    return result["ok"], result["msg"] or "tidak ada respons"
```

### 7.5 `app/gui/schedule_table.py` (model for one day) — unchanged shape
```python
from PySide6.QtCore import Qt, QAbstractTableModel, QModelIndex
from app.models import Bell

class BellsModel(QAbstractTableModel):
    HEADERS = ["Jam", "Suara"]
    def __init__(self, bells: list[Bell] | None = None):
        super().__init__(); self._rows: list[Bell] = list(bells or [])
    def rowCount(self, p=QModelIndex()): return len(self._rows)
    def columnCount(self, p=QModelIndex()): return 2
    def headerData(self, sec, orient, role=Qt.DisplayRole):
        return self.HEADERS[sec] if role==Qt.DisplayRole and orient==Qt.Horizontal else None
    def data(self, idx, role=Qt.DisplayRole):
        if not idx.isValid() or role!=Qt.DisplayRole: return None
        b = self._rows[idx.row()]
        return b.jam if idx.column()==0 else b.file
    # editing: flags()=Editable; setData() rebuilds the frozen Bell + emits dataChanged
```
Delegate for column 0 = `QTimeEdit`; column 1 = the sound combo.

### 7.6 `app/gui/__main__.py`
```python
import sys
from PySide6.QtWidgets import QApplication
from app.gui.main_window import MainWindow

def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("Bel Pembelajaran")
    win = MainWindow()
    win.show()
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())
```
Run during dev: `uv run python -m app.gui`  (or `uv run bel-gui`).

---

## 8. Packaging to EXE (PyInstaller + PySide6 + Qt Multimedia)

`app/paths.py` already handles `sys._MEIPASS`, so bundled `assets/` and `configs/`
resolve automatically. PySide6 brings its own PyInstaller hook (covers Qt plugins).

Cross-platform build (`scripts/build_exe.py`):
```python
import subprocess, sys, os
sep = ";" if os.name == "nt" else ":"
cmd = [
    sys.executable, "-m", "PyInstaller", "--noconfirm",
    "--name", "bel-gui",
    "--windowed",                                  # no console (use --console in dev for logs)
    f"--add-data=assets{sep}assets",
    f"--add-data=configs{sep}configs",
    "--hidden-import=PySide6",
    "--hidden-import=PySide6.QtMultimedia",
    "--collect-submodules=PySide6",
    "run_gui.py",                                  # top-level launcher -> app.gui.__main__:main
]
subprocess.check_call(cmd)
```
- Output: `dist/bel-gui/` (folder — recommended). Add `--onefile` for a single file.
- **Linux frozen build caveat:** the exe links the *host's* GStreamer (PyInstaller
  can't bundle it). The startup self-test is therefore *especially* important on
  the frozen Linux build — confirm it passes on the target image.
- **Test on a clean Windows machine** (no Python/Qt): double-click, open a bundled
  config, confirm the self-test passes and a bell plays.
- If the self-test fails only in the frozen build: verify `PySide6/Qt/plugins/
  multimedia` is collected and that `assets/` is inside the dist folder.

---

## 9. Testing strategy

- **Unit (pytest, Qt-free where possible):**
  - `save_timetable` round-trips with `load_timetable` (load → save → reload → equal).
  - `BellScheduler.on_fire`/`on_error` fire; `tick()` advances via `run_pending`
    (use `NullBackend` — no Qt needed).
  - Keep the existing 17 tests green.
- **Audio self-test:** runs at startup (CLI and GUI). Mockable in tests by
  injecting a fake backend; gate live-audio tests behind a marker
  (`@pytest.mark.audio`) so CI without a sound device can skip them.
- **Manual smoke matrix** (every milestone):
  | | Linux | Windows |
  |---|---|---|
  | `uv run bel test-sound` (Qt) | ☐ | ☐ |
  | `uv run bel start` rings on time | ☐ | ☐ |
  | Ctrl+C / Stop clean (no hang) | ☐ | ☐ |
  | `uv run bel-gui` (dev) | ☐ | ☐ |
  | Load + edit + Save round-trip | ☐ | ☐ |
  | Startup audio self-test passes | ☐ | ☐ |
  | Frozen exe (no Python/Qt) | ☐ | ☐ |
- **Threading sanity:** with a 100 ms `QTimer`, Start/Stop 20× rapidly; assert no
  crash and no Qt warnings (`QWidget: Cannot create … without a screen`,
  `QThread: Destroyed while thread is still running`).

---

## 10. Definition of Done (Phase 2)
1. **Audio runs entirely on Qt Multimedia; pygame is removed** from deps and code.
2. A teacher can install the app (or run the exe) and, **without editing any text
   file**, build a weekly schedule, save it, and start the bell.
3. The GUI shows running state, next bell, and last-fired; Stop is clean.
4. The startup audio self-test passes (or fails loudly) on the target Windows and
   Linux images; mp3 plays via `QMediaPlayer` on both.
5. Headless `bel check`/`sounds`/`--dry-run` work; `bel start` uses Qt audio.
6. `uv run pytest` green; round-trip + scheduler-callback tests added.

---

## 11. Explicitly out of scope (do not do in Phase 2)
- DB persistence, multi-user, networking.
- Autostart as OS service / survive reboot (separate task).
- APScheduler migration (separate task; `schedule` lib is fine for MVP).
- Keeping/shipping pygame as a fallback. (Full migration. Escape hatch only in
  git history — §3.2.)
- Mobile/web UI.

## 12. Open questions to confirm with the maintainer before/during impl
1. **Confirm the school's Linux image has GStreamer mp3 codecs** — run the startup
   self-test once on an actual school PC. (This single check resolves the whole
   codec-risk question for the uniform fleet.)
2. ~~Save edited schedules into `configs/` (repo) or `user_data_dir()` (per-user)?~~
   **Decided & implemented:** "Simpan Sebagai…" defaults to
   `schedules_dir()`; "Open…" starts in `configs/`; shipped `configs/`
   stay read-only examples.
3. Is losing TOML comments on Save acceptable? (Assumed yes.)
4. Should the GUI be able to install itself to autostart? (Defer.)
