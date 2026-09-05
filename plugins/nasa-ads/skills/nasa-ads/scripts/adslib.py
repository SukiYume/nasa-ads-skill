#!/usr/bin/env python3
"""Open and manage the local literature library. Default: open in the background."""

from __future__ import annotations

import argparse
import contextlib
import errno
import hashlib
import json
import os
import secrets
import shlex
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import webbrowser
from pathlib import Path
from urllib.error import URLError
from urllib.request import HTTPRedirectHandler, ProxyHandler, Request, build_opener

import literature_db
import library_web

MARKER = "NASA ADS managed adslib launcher"
PATH_START = "# >>> NASA ADS adslib PATH >>>"
PATH_END = "# <<< NASA ADS adslib PATH <<<"


@contextlib.contextmanager
def service_lock(library_dir, port):
    """Serialize shell invocations; the serving child never takes this lock."""
    directory = runtime_dir()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    key = hashlib.sha256(
        f"{os.path.normcase(str(library_dir))}:{port}".encode()
    ).hexdigest()
    with (directory / f"{key}.lock").open("a+b") as stream:
        stream.seek(0, os.SEEK_END)
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        deadline = time.monotonic() + 25
        while True:
            stream.seek(0)
            try:
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise ValueError(
                        "Another service operation is in progress; retry shortly."
                    )
                time.sleep(0.1)
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream, fcntl.LOCK_UN)


def runtime_dir() -> Path:
    if os.environ.get("NASA_ADS_RUNTIME_DIR"):
        return Path(os.environ["NASA_ADS_RUNTIME_DIR"]).expanduser().resolve()
    if os.name == "nt":
        base = Path(os.environ.get("LOCALAPPDATA") or Path.home() / "AppData/Local")
    else:
        base = Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local/state")
    return base / "nasa-ads/runtime"


def service_request(port, route, token=None):
    request = Request(f"http://127.0.0.1:{port}{route}")
    if token:
        request.method = "POST"
        request.add_header("Authorization", f"Bearer {token}")
        request.data = b""
    with build_opener(ProxyHandler({}), NoRedirect()).open(
        request, timeout=3
    ) as response:
        return json.loads(response.read(1024 * 1024))


def managed_services(library_dir):
    results = []
    for path in runtime_dir().glob("*.json"):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            if Path(record["library_dir"]).resolve() != library_dir.resolve():
                continue
            port = record["port"]
            if type(port) is not int or not 1 <= port <= 65535:
                continue
            live = service_request(port, "/api/service")
            if (
                live.get("instance") == record["instance"]
                and Path(live["library_dir"]).resolve() == library_dir.resolve()
            ):
                results.append(record)
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            continue
    return results


def find_service(library_dir, port):
    records = managed_services(library_dir)
    exact = [record for record in records if record["port"] == port]
    candidates = exact or [
        record for record in records if record["requested_port"] == port
    ]
    if len(candidates) > 1:
        raise ValueError(
            "Multiple services match; choose an actual --port: "
            + ", ".join(str(record["port"]) for record in candidates)
        )
    if candidates:
        return candidates[0]
    return None


def stop_service(record, stdout):
    # Recheck the instance immediately before sending its private capability.
    if (
        service_request(record["port"], "/api/service").get("instance")
        != record["instance"]
    ):
        raise ValueError("The service instance changed. Run adslib status again.")
    service_request(record["port"], "/api/service/stop", record["token"])
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        try:
            live = service_request(record["port"], "/api/service")
            if live.get("instance") != record["instance"]:
                break
        except (OSError, ValueError):
            break
        time.sleep(0.1)
    else:
        raise ValueError("Shutdown is still pending. Run adslib status again.")
    stdout.write(f"Stopped library service on port {record['port']}.\n")


def start_background(library_dir, port, *, browser, stdout):
    directory = runtime_dir()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    identity = secrets.token_hex(16)
    ready = directory / f"{identity}.ready"
    log = directory / f"{identity}.log"
    command = [
        sys.executable,
        "-X",
        "utf8",
        str(Path(__file__).resolve()),
        "--library-dir",
        str(library_dir),
        "--port",
        str(port),
        "--no-open",
        "--ready-file",
        str(ready),
        "serve",
    ]
    options = (
        {"creationflags": subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS}
        if os.name == "nt"
        else {"start_new_session": True}
    )
    with log.open("wb") as stream:
        process = subprocess.Popen(
            command,
            stdin=subprocess.DEVNULL,
            stdout=stream,
            stderr=stream,
            close_fds=True,
            **options,
        )
    try:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if ready.exists():
                actual = json.loads(ready.read_text(encoding="utf-8"))["port"]
                if running_library(actual, library_dir):
                    url = f"http://127.0.0.1:{actual}"
                    stdout.write(
                        f"NASA ADS library: {url}\nLibrary: {library_dir}\nLog: {log}\n"
                    )
                    stdout.write(
                        f'Stop with: adslib stop --port {actual} --library-dir "{library_dir}"\n'
                    )
                    if browser:
                        open_browser(url, stdout)
                    return 0
            if process.poll() is not None:
                break
            time.sleep(0.1)
        if process.poll() is None:
            process.terminate()  # Only the child created by this invocation.
            process.wait(timeout=5)
        raise ValueError(f"Service startup failed. Read the log: {log}")
    finally:
        ready.unlink(missing_ok=True)


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


def launch(
    library_dir: Path, port: int, *, browser: bool, stdout, ready_file=None
) -> int:
    """Reuse the matching service or host a new read-only library until Ctrl+C."""
    if not 0 <= port <= 65535:
        raise ValueError("Port must be between 0 and 65535.")
    library_dir = library_dir.expanduser().resolve()
    existing = find_service(library_dir, port)
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
            existing = find_service(library_dir, port)
            if existing is None:
                server = library_web.make_server(library_dir, 0)
    active_port = server.server_port if server else existing["port"]
    url = f"http://127.0.0.1:{active_port}"
    stdout.write(f"NASA ADS library: {url}\nLibrary: {library_dir}\n")
    if server is None:
        if ready_file:
            atomic_write(Path(ready_file), json.dumps({"port": active_port}))
        stdout.write("Using the running library service.\n")
        stdout.flush()
        if browser:
            open_browser(url, stdout)
        return 0
    directory = runtime_dir()
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    server.control_token = secrets.token_hex(32)
    server.control_instance = secrets.token_hex(16)
    record_path = directory / f"{server.control_instance}.json"
    record = {
        "instance": server.control_instance,
        "token": server.control_token,
        "port": active_port,
        "requested_port": port,
        "pid": os.getpid(),
        "library_dir": str(library_dir),
        "version": literature_db.VERSION,
    }
    try:
        with record_path.open("x", encoding="utf-8") as stream:
            os.chmod(record_path, 0o600)
            json.dump(record, stream)
        if ready_file:
            atomic_write(Path(ready_file), json.dumps({"port": active_port}))
    except BaseException:
        server.server_close()
        record_path.unlink(missing_ok=True)
        raise
    stdout.write(
        "Keep this terminal open. Press Ctrl+C or use adslib stop to stop the library service.\n"
    )
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
        record_path.unlink(missing_ok=True)
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
        bin_dir = Path(environ.get("HOME") or Path.home()) / ".local/bin"
    bin_dir = bin_dir.expanduser().resolve()
    target = bin_dir / ("adslib.cmd" if windows else "adslib")
    bash_target = bin_dir / "adslib" if windows else None
    if (
        bash_target
        and bash_target.exists()
        and MARKER not in bash_target.read_text(encoding="utf-8")[:256]
    ):
        raise ValueError(
            f"An existing command owns {bash_target}. Choose another --bin-dir."
        )
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
        bootstrap = bin_dir / "adslib-bootstrap.ps1"
        if (
            bootstrap.exists()
            and MARKER not in bootstrap.read_text(encoding="utf-8-sig")[:256]
        ):
            raise ValueError(
                f"An existing file owns {bootstrap}. Choose another --bin-dir."
            )

        def ps_quote(value):
            return "'" + str(value).replace("'", "''") + "'"

        # A BOM preserves Unicode paths in Windows PowerShell 5.1. The ASCII
        # batch entrypoint never changes the caller's console code page.
        atomic_write(
            bootstrap,
            "\ufeff"
            + f"# {MARKER}\n& {ps_quote(sys.executable)} -X utf8 {ps_quote(script)} @args\nexit $LASTEXITCODE\n",
        )
        content = (
            f"@echo off\r\nrem {MARKER}\r\n"
            "setlocal EnableExtensions DisableDelayedExpansion\r\n"
            '"%SystemRoot%\\System32\\WindowsPowerShell\\v1.0\\powershell.exe" -NoLogo -NoProfile -ExecutionPolicy RemoteSigned -File "%~dp0adslib-bootstrap.ps1" %*\r\n'
            "exit /b %ERRORLEVEL%\r\n"
        )
    else:
        content = f'#!/bin/sh\n# {MARKER}\nexec {shlex.quote(sys.executable)} -X utf8 {shlex.quote(str(script))} "$@"\n'
    atomic_write(target, content, executable=not windows)
    if bash_target:
        atomic_write(
            bash_target,
            f'#!/bin/sh\n# {MARKER}\nexec {shlex.quote(Path(sys.executable).as_posix())} -X utf8 {shlex.quote(script.as_posix())} "$@"\n',
            executable=True,
        )
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


def manage_service(args, library_dir, stdout):
    record = find_service(library_dir, args.port)
    if args.command == "status":
        if record:
            stdout.write(
                f"Running: http://127.0.0.1:{record['port']}\nLibrary: {library_dir}\n"
            )
            stdout.write(
                f"Version: {record['version']}\nPID: {record['pid']}\nControl: managed\n"
            )
            return 0
        stdout.write(f"No managed service. Library: {library_dir}\n")
        return 3
    if args.command in {"stop", "restart"}:
        if record:
            stop_service(record, stdout)
        elif args.command == "stop":
            stdout.write("Library service is already stopped.\n")
        if args.command == "stop":
            return 0
        record = None
    if record:
        if args.ready_file:
            atomic_write(Path(args.ready_file), json.dumps({"port": record["port"]}))
        stdout.write(
            f"NASA ADS library: http://127.0.0.1:{record['port']}\nLibrary: {library_dir}\nUsing the running library service.\n"
        )
        if not args.no_open and args.command in {None, "open"}:
            open_browser(f"http://127.0.0.1:{record['port']}", stdout)
        return 0
    if args.command in {None, "start", "open", "restart"}:
        return start_background(
            library_dir,
            args.port,
            browser=not args.no_open and args.command in {None, "open"},
            stdout=stdout,
        )
    return launch(
        library_dir,
        args.port,
        browser=False,
        stdout=stdout,
        ready_file=args.ready_file,
    )


def run(argv=None, *, environ=None, stdout=None, stderr=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    environ = environ if environ is not None else os.environ
    stdout, stderr = stdout or sys.stdout, stderr or sys.stderr
    # Bootstrap registration is documented through the installed Python script.
    # Keep everyday service help focused on opening and managing the library.
    if argv[:1] == ["install"]:
        installer = argparse.ArgumentParser(
            prog="python adslib.py install",
            description="Register the installed script as the user-level adslib command.",
        )
        installer.add_argument(
            "--bin-dir", type=Path, help="custom user command directory"
        )
        installer.add_argument(
            "--no-path", action="store_true", help="preserve shell PATH settings"
        )
        args = installer.parse_args(argv[1:])
        try:
            return install(
                environ=environ,
                stdout=stdout,
                bin_dir=args.bin_dir,
                update_path=not args.no_path,
            )
        except (OSError, ValueError) as exc:
            stderr.write(f"error: {exc}\n")
            return 1
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--version", action="version", version=f"adslib {literature_db.VERSION}"
    )
    parser.add_argument(
        "--library-dir",
        help="personal library directory; defaults to NASA_ADS_LITERATURE_DIR or the user library",
    )
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--ready-file", help=argparse.SUPPRESS)
    parser.add_argument(
        "--no-open",
        action="store_true",
        help="print the URL and serve without opening a browser",
    )
    subparsers = parser.add_subparsers(dest="command")
    for name, help_text in (
        ("start", "start a background service"),
        ("open", "open the library, starting a background service if needed"),
        ("status", "show the matching service status"),
        ("stop", "gracefully stop the matching service"),
        ("restart", "restart the matching service in the background"),
        ("serve", "run in the foreground until Ctrl+C or adslib stop"),
    ):
        command = subparsers.add_parser(name, help=help_text)
        command.add_argument("--library-dir", default=argparse.SUPPRESS)
        command.add_argument("--port", type=int, default=argparse.SUPPRESS)
        command.add_argument(
            "--no-open", action="store_true", default=argparse.SUPPRESS
        )
    args = parser.parse_args(argv)
    try:
        library_dir = (
            Path(args.library_dir)
            if args.library_dir
            else literature_db.default_library_dir(environ)
        )
        library_dir = library_dir.expanduser().resolve()
        if not 0 <= args.port <= 65535:
            raise ValueError("Port must be between 0 and 65535.")
        lock = (
            contextlib.nullcontext()
            if args.command in {"serve", "status"}
            else service_lock(library_dir, args.port)
        )
        with lock:
            return manage_service(args, library_dir, stdout)
    except (OSError, ValueError, literature_db.LiteratureError) as exc:
        stderr.write(f"error: {exc}\n")
        return 1


if __name__ == "__main__":
    literature_db.ads_api.configure_stdio()
    raise SystemExit(run())
