#!/usr/bin/env python3
"""Open the local literature library and install its user-level shell command."""

from __future__ import annotations

import argparse
import errno
import json
import os
import shlex
import shutil
import sys
import tempfile
import threading
import webbrowser
from pathlib import Path
from urllib.error import URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, build_opener

import literature_db
import library_web

MARKER = "NASA ADS managed adslib launcher"
PATH_START = "# >>> NASA ADS adslib PATH >>>"
PATH_END = "# <<< NASA ADS adslib PATH <<<"


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def running_library(port: int, library_dir: Path) -> dict | None:
    """Recognize a loopback library without proxies or redirects."""
    if not port:
        return None
    try:
        opener = build_opener(ProxyHandler({}), NoRedirect())
        with opener.open(f"http://127.0.0.1:{port}/api/stats", timeout=3) as response:
            if not response.headers.get("Server", "").startswith("NASA-ADS-Library"):
                return None
            payload = json.loads(response.read(1024 * 1024))
        if isinstance(payload, dict) and isinstance(payload.get("library_dir"), str):
            if Path(payload["library_dir"]).resolve() == library_dir.resolve():
                return payload
    except (OSError, URLError, ValueError):
        pass
    return None


def open_browser(url: str, stdout) -> None:
    try:
        opened = webbrowser.open(url, new=2)
    except (OSError, webbrowser.Error):
        opened = False
    if not opened:
        stdout.write(f"Open this address in your browser: {url}\n")
        stdout.flush()


def launch(library_dir: Path, port: int, *, browser: bool, stdout) -> int:
    """Reuse the matching service or host a new read-only library until Ctrl+C."""
    if not 0 <= port <= 65535:
        raise ValueError("Port must be between 0 and 65535.")
    library_dir = library_dir.expanduser().resolve()
    existing = running_library(port, library_dir)
    server = None
    if existing is None:
        try:
            server = library_web.make_server(library_dir, port)
        except OSError as exc:
            if exc.errno != errno.EADDRINUSE and getattr(exc, "winerror", None) not in {
                10048,
                10013,
            }:
                raise
            # Another invocation may have completed its startup during the probe.
            existing = running_library(port, library_dir)
            if existing is None:
                server = library_web.make_server(library_dir, 0)
    active_port = server.server_port if server else port
    url = f"http://127.0.0.1:{active_port}"
    stdout.write(f"NASA ADS library: {url}\nLibrary: {library_dir}\n")
    if server is None:
        stdout.write("Using the running library service.\n")
        stdout.flush()
        if browser:
            open_browser(url, stdout)
        return 0
    stdout.write("Keep this terminal open. Press Ctrl+C to stop the library service.\n")
    stdout.flush()
    try:
        if browser:
            # The socket is already bound; serving stays on the interruptible main thread.
            threading.Thread(
                target=open_browser, args=(url, stdout), daemon=True
            ).start()
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def atomic_write(path: Path, content: str, *, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise ValueError(
            f"Choose a regular file for the launcher or PATH configuration: {path}"
        )
    data = content.encode("utf-8")
    if path.exists() and path.read_bytes() == data:
        if executable:
            path.chmod(path.stat().st_mode | 0o111)
        return
    mode = path.stat().st_mode if path.exists() else 0o644
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
        os.chmod(temporary, mode | (0o111 if executable else 0))
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def path_contains(path_value: str, directory: Path, *, windows: bool) -> bool:
    expected = str(directory.resolve())
    for item in path_value.split(";" if windows else os.pathsep):
        if item.strip():
            candidate = str(
                Path(os.path.expandvars(item.strip().strip('"'))).expanduser().resolve()
            )
            if (candidate.casefold() if windows else candidate) == (
                expected.casefold() if windows else expected
            ):
                return True
    return False


def windows_user_path(directory: Path) -> bool:
    import winreg

    with winreg.CreateKeyEx(
        winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_READ | winreg.KEY_WRITE
    ) as key:
        try:
            current, kind = winreg.QueryValueEx(key, "Path")
        except FileNotFoundError:
            current, kind = "", winreg.REG_EXPAND_SZ
        if path_contains(current, directory, windows=True):
            return False
        updated = (
            current
            + ("" if not current or current.endswith(";") else ";")
            + str(directory)
        )
        winreg.SetValueEx(key, "Path", 0, kind, updated)
    # Notify future terminals; current shells keep their existing environment.
    try:
        import ctypes

        ctypes.windll.user32.SendMessageTimeoutW(
            0xFFFF, 0x001A, 0, ctypes.c_wchar_p("Environment"), 0x0002, 2000, None
        )
    except (AttributeError, OSError):
        pass
    return True


def posix_user_path(directory: Path, environ) -> list[str]:
    if path_contains(environ.get("PATH", ""), directory, windows=False):
        return []
    user_dir = Path(environ.get("HOME") or Path.home()).expanduser()
    shell = Path(environ.get("SHELL", "/bin/sh")).name
    if shell == "zsh":
        profiles = [Path(environ.get("ZDOTDIR") or user_dir) / ".zshrc"]
    elif shell == "bash":
        login = next(
            (
                user_dir / name
                for name in (".bash_profile", ".bash_login", ".profile")
                if (user_dir / name).is_file()
            ),
            user_dir / ".profile",
        )
        profiles = [user_dir / ".bashrc", login]
    elif shell in {"sh", "dash", "ksh"}:
        profiles = [user_dir / ".profile"]
    else:
        raise ValueError(
            f"Add {directory} to your shell PATH, then run the installer again. Supported automatic setup: bash, zsh, sh, dash, ksh."
        )
    block = (
        f'{PATH_START}\nexport PATH={shlex.quote(str(directory))}:"$PATH"\n{PATH_END}\n'
    )
    changed = []
    for profile in profiles:
        original = profile.read_bytes().decode("utf-8") if profile.exists() else ""
        if PATH_START in original or PATH_END in original:
            if original.count(PATH_START) != 1 or original.count(PATH_END) != 1:
                raise ValueError(
                    f"Repair the incomplete NASA ADS PATH block in {profile}."
                )
            start, end = (
                original.index(PATH_START),
                original.index(PATH_END) + len(PATH_END),
            )
            if end < start:
                raise ValueError(f"Repair the NASA ADS PATH block in {profile}.")
            updated = original[:start] + block.rstrip("\n") + original[end:]
        else:
            updated = (
                original
                + ("\n" if original and not original.endswith("\n") else "")
                + "\n"
                + block
            )
        if updated != original:
            atomic_write(profile, updated)
            changed.append(str(profile))
    return changed


def install(
    *, environ, stdout, bin_dir: Path | None = None, update_path: bool = True
) -> int:
    windows = os.name == "nt"
    script = Path(__file__).resolve()
    if bin_dir is None:
        if windows:
            local = Path(environ.get("LOCALAPPDATA") or Path.home() / "AppData/Local")
            bin_dir = local / "nasa-ads/bin"
        else:
            bin_dir = Path(environ.get("HOME") or Path.home()) / ".local/bin"
    bin_dir = bin_dir.expanduser().resolve()
    target = bin_dir / ("adslib.cmd" if windows else "adslib")
    if target.exists() and MARKER not in target.read_text(encoding="utf-8")[:256]:
        raise ValueError(
            f"An existing command owns {target}. Choose another --bin-dir."
        )
    existing = shutil.which("adslib", path=environ.get("PATH", ""))
    if existing and Path(existing).resolve() != target.resolve():
        raise ValueError(
            f"An existing adslib command is on PATH: {existing}. Keep one active launcher location."
        )
    if windows:
        def quote(value):
            return '"' + str(value).replace("%", "%%") + '"'

        # Decode Unicode installation paths as UTF-8 and restore the caller's
        # console code page and command exit status after Python returns.
        content = (
            f"@echo off\r\nrem {MARKER}\r\n"
            "setlocal EnableExtensions DisableDelayedExpansion\r\n"
            'set "_NASA_ADS_CP="\r\n'
            'for /f "tokens=2 delims=:" %%G in (\'chcp\') do set "_NASA_ADS_CP=%%G"\r\n'
            "chcp 65001 >nul\r\n"
            f"{quote(sys.executable)} -X utf8 {quote(script)} %*\r\n"
            'set "_NASA_ADS_EXIT=%ERRORLEVEL%"\r\n'
            "if defined _NASA_ADS_CP chcp %_NASA_ADS_CP% >nul\r\n"
            "exit /b %_NASA_ADS_EXIT%\r\n"
        )
    else:
        content = f'#!/bin/sh\n# {MARKER}\nexec {shlex.quote(sys.executable)} -X utf8 {shlex.quote(str(script))} "$@"\n'
    atomic_write(target, content, executable=not windows)
    changed = []
    if update_path:
        if windows:
            if windows_user_path(bin_dir):
                changed.append("Windows user PATH")
        else:
            changed = posix_user_path(bin_dir, environ)
    stdout.write(f"Installed adslib: {target}\nSkill launcher: {script}\n")
    if changed:
        stdout.write("PATH updated: " + ", ".join(changed) + "\n")
    if update_path:
        stdout.write("Open a new terminal and run: adslib\n")
    else:
        stdout.write(f"PATH setup skipped. Run the launcher at: {target}\n")
    return 0


def run(argv=None, *, environ=None, stdout=None, stderr=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--version", action="version", version=f"adslib {literature_db.VERSION}"
    )
    parser.add_argument(
        "--library-dir",
        help="personal library directory; defaults to NASA_ADS_LITERATURE_DIR or the user library",
    )
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="print the URL and serve without opening a browser",
    )
    subparsers = parser.add_subparsers(dest="command")
    installer = subparsers.add_parser(
        "install", help="register the adslib command for this user"
    )
    installer.add_argument("--bin-dir", type=Path, help="custom user command directory")
    installer.add_argument(
        "--no-path",
        action="store_true",
        help="write the launcher and keep shell PATH settings unchanged",
    )
    args = parser.parse_args(argv)
    environ = environ if environ is not None else os.environ
    stdout, stderr = stdout or sys.stdout, stderr or sys.stderr
    try:
        if args.command == "install":
            return install(
                environ=environ,
                stdout=stdout,
                bin_dir=args.bin_dir,
                update_path=not args.no_path,
            )
        library_dir = (
            Path(args.library_dir)
            if args.library_dir
            else literature_db.default_library_dir(environ)
        )
        return launch(library_dir, args.port, browser=not args.no_open, stdout=stdout)
    except (OSError, ValueError, literature_db.LiteratureError) as exc:
        stderr.write(f"error: {exc}\n")
        return 1


if __name__ == "__main__":
    literature_db.ads_api.configure_stdio()
    raise SystemExit(run())
