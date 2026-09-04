"""Bel Pelajaran — school bell scheduling system.

Public layers (Phase 1 decoupling):

    app.config     load + validate a TOML timetable  (config source)
    app.models     Bell / Timetable dataclasses
    app.scheduler  the engine: arm + run, error-safe, non-blocking
    app.audio      AudioBackend protocol + Qt Multimedia implementation
    app.paths      resource resolution that works in dev AND in a frozen exe
    app.cli        the `bel` command-line interface
"""

__version__ = "0.2.0"
