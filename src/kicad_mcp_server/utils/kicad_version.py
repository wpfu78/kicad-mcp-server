"""KiCad installation detection and version utilities."""

import re
import sys
from pathlib import Path

_cached_install: tuple[Path, str] | None = None


def _parse_version(version_str: str) -> tuple[int, ...]:
    """Parse version string like '10.0' into tuple for sorting."""
    try:
        return tuple(int(x) for x in version_str.split("."))
    except (ValueError, AttributeError):
        return (0,)


def _install_roots_from_interpreter() -> list[Path]:
    """Candidate KiCad install roots implied by the running interpreter.

    KiCad's bundled Python lives at ``<install>/bin/python(.exe)``, so the
    install root is two levels up. Inside a venv ``sys.executable`` points at
    the venv instead, so also consult ``sys._base_executable`` and the base
    prefix. Duplicates are fine; callers only test each for ``share/kicad``.
    """
    roots: list[Path] = []

    executables = [
        getattr(sys, "_base_executable", None),
        getattr(sys, "executable", None),
    ]
    for executable in executables:
        if executable:
            roots.append(Path(executable).resolve().parent.parent)

    prefixes = [
        getattr(sys, "base_prefix", None),
        getattr(sys, "prefix", None),
    ]
    for prefix in prefixes:
        if prefix:
            prefix_path = Path(prefix).resolve()
            roots.append(prefix_path)
            roots.append(prefix_path.parent)

    return roots


def find_kicad_install() -> tuple[Path, str] | None:
    """Find the installed KiCad directory and version string.

    Scans known install locations, preferring the newest version.

    Returns:
        (install_path, version_string) or None if not found
    """
    global _cached_install
    if _cached_install is not None:
        return _cached_install

    # Windows: C:/Program Files/KiCad/{version}/
    win_base = Path("C:/Program Files/KiCad")
    if win_base.is_dir():
        try:
            version_dirs = sorted(
                [d for d in win_base.iterdir() if d.is_dir()],
                key=lambda d: _parse_version(d.name),
                reverse=True,
            )
            for vd in version_dirs:
                if (vd / "share" / "kicad").is_dir():
                    _cached_install = (vd, vd.name)
                    return _cached_install
        except OSError:
            pass

    # macOS: single app bundle
    mac_base = Path("/Applications/KiCad/KiCad.app/Contents/SharedSupport")
    if mac_base.is_dir():
        _cached_install = (mac_base, "macos")
        return _cached_install

    # Linux: standard paths
    for linux_base in [
        Path("/usr/share/kicad"),
        Path("/usr/local/share/kicad"),
    ]:
        if linux_base.is_dir():
            _cached_install = (linux_base, "linux")
            return _cached_install

    # Fallback: infer the install root from the running interpreter. The MCP
    # server is normally launched from KiCad's bundled Python, whose executable
    # lives at <install>/bin/python(.exe). That covers portable installs (for
    # example D:/Program Files) that are not under C:/Program Files/KiCad.
    for install_root in _install_roots_from_interpreter():
        if (install_root / "share" / "kicad").is_dir():
            _cached_install = (install_root, "windows")
            return _cached_install

    return None


def get_kicad_symbol_dir() -> Path | None:
    """Get the KiCad symbol library directory (.kicad_sym files)."""
    kicad = find_kicad_install()
    if kicad:
        install_path, version_marker = kicad
        # find_kicad_install() returns different path shapes per platform:
        # Windows returns the top-level "<...>/KiCad/<version>" dir, with
        # symbols nested under "share/kicad/symbols". Linux/macOS instead
        # already return the "share/kicad" (or SharedSupport) directory
        # itself, so appending "share/kicad" again pointed at a path that
        # never exists there.
        if version_marker in ("linux", "macos"):
            sym_dir = install_path / "symbols"
        else:
            sym_dir = install_path / "share" / "kicad" / "symbols"
        if sym_dir.is_dir():
            return sym_dir
    return None


def get_pcb_version() -> str:
    """Get the correct PCB file version string for the installed KiCad.

    Reads from a template PCB file if available, falls back to '20240130'.
    """
    kicad = find_kicad_install()
    if kicad:
        install_path, _version = kicad
        for template_name in ["Arduino_Mega", "EuroCard160mmX100mm"]:
            template_pcb = (
                install_path / "share" / "kicad" / "template" / template_name / f"{template_name}.kicad_pcb"
            )
            if template_pcb.exists():
                try:
                    content = template_pcb.read_text(encoding="utf-8", errors="replace")
                    m = re.search(r"\(kicad_pcb\s+\(version\s+(\d+)\)", content)
                    if m:
                        return m.group(1)
                except OSError:
                    pass
    return "20240130"
