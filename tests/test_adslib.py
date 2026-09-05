from __future__ import annotations

import io
import json
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.request import urlopen
from urllib.error import HTTPError
from urllib.request import Request

from test_literature_db import SCRIPTS_DIR
import adslib
import library_web


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="ads library 测试 ")
        self.root = Path(self.temporary.name)
        self.library = self.root / "library"
        self.environment_patch = patch.dict(
            os.environ, {"NASA_ADS_RUNTIME_DIR": str(self.root / "runtime")}
        )
        self.environment_patch.start()
        self.addCleanup(self.environment_patch.stop)

    def tearDown(self):
        self.temporary.cleanup()

    def start_server(self, library):
        server = library_web.make_server(library, 0)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        self.addCleanup(worker.join, 5)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        return server

    def test_existing_matching_server_opens_without_starting_another(self):
        server = self.start_server(self.library)
        server.control_instance = "test-instance"
        directory = adslib.runtime_dir()
        directory.mkdir()
        (directory / "test.json").write_text(
            json.dumps(
                {
                    "instance": "test-instance",
                    "port": server.server_port,
                    "requested_port": server.server_port,
                    "library_dir": str(self.library),
                }
            ),
            encoding="utf-8",
        )
        with (
            patch.object(adslib, "open_browser") as browser,
            patch.object(library_web, "make_server") as create,
        ):
            self.assertEqual(
                adslib.launch(
                    self.library, server.server_port, browser=True, stdout=io.StringIO()
                ),
                0,
            )
        create.assert_not_called()
        self.assertEqual(
            browser.call_args.args[0], f"http://127.0.0.1:{server.server_port}"
        )
        self.assertFalse(self.library.exists())

    def test_occupied_port_with_other_library_chooses_new_port(self):
        occupied = self.start_server(self.root / "another library")
        actual_make_server = library_web.make_server
        ports = []

        def make_server(directory, port):
            server = actual_make_server(directory, port)
            ports.append(server.server_port)
            server.serve_forever = lambda: (_ for _ in ()).throw(KeyboardInterrupt())
            return server

        with patch.object(library_web, "make_server", side_effect=make_server):
            self.assertEqual(
                adslib.launch(
                    self.library,
                    occupied.server_port,
                    browser=False,
                    stdout=io.StringIO(),
                ),
                0,
            )
        self.assertEqual(len(ports), 1)
        self.assertNotEqual(ports[0], occupied.server_port)

    def test_probe_rejects_redirects_and_unrelated_servers(self):
        hits = []
        root = self.library

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                hits.append(self.path)
                self.send_response(302 if len(hits) == 1 else 200)
                if len(hits) == 1:
                    self.send_header(
                        "Location",
                        f"http://127.0.0.1:{self.server.server_port}/destination",
                    )
                self.end_headers()
                self.wfile.write(json.dumps({"library_dir": str(root)}).encode())

            def log_message(self, *args):
                pass

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            self.assertIsNone(adslib.running_library(server.server_port, self.library))
            self.assertEqual(hits, ["/api/stats"])
            self.assertIsNone(adslib.running_library(server.server_port, self.library))
        finally:
            server.shutdown()
            server.server_close()
            worker.join(5)

    def test_fresh_launcher_serves_without_token_or_database(self):
        environment = {
            key: value
            for key, value in os.environ.items()
            if key not in {"ADS_API_TOKEN", "ADS_DEV_KEY"}
        }
        process = subprocess.Popen(
            [
                sys.executable,
                "-X",
                "utf8",
                "-S",
                str(SCRIPTS_DIR / "adslib.py"),
                "--library-dir",
                str(self.library),
                "--port",
                "0",
                "--no-open",
                "serve",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            env=environment,
        )
        lines = queue.Queue()
        threading.Thread(
            target=lambda: lines.put(process.stdout.readline()), daemon=True
        ).start()
        try:
            line = lines.get(timeout=10)
            self.assertTrue(
                line.startswith("NASA ADS library: http://127.0.0.1:"), line
            )
            url = line.strip().split(": ", 1)[1]
            for route in (
                "/",
                "/style.css",
                "/app.js",
                "/api/stats",
                "/api/papers",
                "/api/collections",
            ):
                with urlopen(url + route, timeout=5) as response:
                    self.assertEqual(response.status, 200)
                    if route == "/api/stats":
                        payload = json.load(response)
                        self.assertEqual(payload["counts"]["papers"], 0)
                        self.assertEqual(Path(payload["library_dir"]), self.library)
            self.assertFalse(self.library.exists())
        finally:
            process.terminate()
            process.communicate(timeout=10)

    def test_browser_failure_leaves_a_copyable_url(self):
        output = io.StringIO()
        with patch.object(adslib.webbrowser, "open", return_value=False):
            adslib.open_browser("http://127.0.0.1:8765", output)
        self.assertIn("http://127.0.0.1:8765", output.getvalue())

    def test_owned_wrapper_is_idempotent_and_executable(self):
        bin_dir = self.root / "command bin"
        for _ in range(2):
            self.assertEqual(
                adslib.install(
                    environ={"PATH": ""},
                    stdout=io.StringIO(),
                    bin_dir=bin_dir,
                    update_path=False,
                ),
                0,
            )
        wrapper = bin_dir / ("adslib.cmd" if os.name == "nt" else "adslib")
        result = subprocess.run(
            [str(wrapper), "--version"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            result.stdout.strip(), f"adslib {adslib.literature_db.VERSION}"
        )
        self.assertEqual(len(list(bin_dir.iterdir())), 3 if os.name == "nt" else 1)
        bash = Path("C:/Program Files/Git/bin/bash.exe")
        if os.name == "nt" and bash.is_file():
            result = subprocess.run(
                [
                    str(bash),
                    "--noprofile",
                    "--norc",
                    "-c",
                    'export PATH="$(cygpath -u "$1"):$PATH"; adslib --version',
                    "adslib-test",
                    bin_dir.as_posix(),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=10,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(adslib.literature_db.VERSION, result.stdout)

    def test_foreign_command_is_preserved(self):
        target = self.root / ("adslib.cmd" if os.name == "nt" else "adslib")
        target.write_text("an existing user command", encoding="utf-8")
        with self.assertRaises(ValueError):
            adslib.install(
                environ={"PATH": ""},
                stdout=io.StringIO(),
                bin_dir=self.root,
                update_path=False,
            )
        self.assertEqual(target.read_text(encoding="utf-8"), "an existing user command")

    def test_installed_script_in_unicode_path_and_failure_exit_status(self):
        scripts = self.root / "已安装 skill" / "scripts"
        shutil.copytree(
            SCRIPTS_DIR, scripts, ignore=shutil.ignore_patterns("__pycache__")
        )
        bin_dir = self.root / "启动命令"
        environment = {**os.environ, "PATH": ""}
        install = subprocess.run(
            [
                sys.executable,
                "-X",
                "utf8",
                str(scripts / "adslib.py"),
                "install",
                "--bin-dir",
                str(bin_dir),
                "--no-path",
            ],
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=10,
        )
        self.assertEqual(install.returncode, 0, install.stderr)
        wrapper = bin_dir / ("adslib.cmd" if os.name == "nt" else "adslib")
        for arguments, expected in ((["--version"], 0), (["--invalid-option"], 2)):
            result = subprocess.run(
                [str(wrapper), *arguments],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=10,
            )
            self.assertEqual(result.returncode, expected, result.stderr)
            if expected == 0:
                self.assertIn(adslib.literature_db.VERSION, result.stdout)

    def test_conflicting_path_command_is_preserved(self):
        with patch.object(
            adslib.shutil, "which", return_value=str(self.root / "other/adslib")
        ):
            with self.assertRaises(ValueError):
                adslib.install(
                    environ={},
                    stdout=io.StringIO(),
                    bin_dir=self.root / "bin",
                    update_path=False,
                )
        self.assertFalse((self.root / "bin").exists())

    def test_posix_path_preserves_existing_profile_and_handles_spaces(self):
        profile = self.root / ".bash_profile"
        profile.write_text("# user's settings\nexport EXISTING=yes\n", encoding="utf-8")
        environment = {"HOME": str(self.root), "SHELL": "/bin/bash", "PATH": ""}
        for _ in range(2):
            adslib.posix_user_path(self.root / "command bin", environment)
        for name in (".bash_profile", ".bashrc"):
            content = (self.root / name).read_text(encoding="utf-8")
            self.assertEqual(content.count(adslib.PATH_START), 1)
            self.assertIn('"$PATH"', content)
        self.assertTrue(
            profile.read_text(encoding="utf-8").startswith(
                "# user's settings\nexport EXISTING=yes\n"
            )
        )

    def test_zsh_uses_zdotdir_and_existing_path_needs_no_profile_edit(self):
        directory = self.root / ".local/bin"
        environment = {
            "HOME": str(self.root),
            "ZDOTDIR": str(self.root / "zsh"),
            "SHELL": "/bin/zsh",
            "PATH": str(directory),
        }
        self.assertEqual(adslib.posix_user_path(directory, environment), [])
        self.assertFalse((self.root / "zsh").exists())
        environment["PATH"] = ""
        adslib.posix_user_path(directory, environment)
        self.assertTrue((self.root / "zsh/.zshrc").is_file())

    @unittest.skipUnless(os.name == "nt", "Windows registry interface")
    def test_windows_path_preserves_registry_value_and_is_idempotent(self):
        import winreg

        current = [r"%USERPROFILE%\tools;C:\existing"]
        kind = winreg.REG_EXPAND_SZ

        def save(key, name, reserved, value_kind, value):
            self.assertEqual(value_kind, kind)
            current[0] = value

        with (
            patch.object(winreg, "CreateKeyEx"),
            patch.object(
                winreg, "QueryValueEx", side_effect=lambda *args: (current[0], kind)
            ),
            patch.object(winreg, "SetValueEx", side_effect=save) as setter,
            patch("ctypes.windll.user32.SendMessageTimeoutW"),
        ):
            self.assertTrue(adslib.windows_user_path(self.root / "bin"))
            self.assertFalse(adslib.windows_user_path(self.root / "bin"))
        setter.assert_called_once()
        self.assertTrue(current[0].startswith(r"%USERPROFILE%\tools;C:\existing;"))

    def test_invalid_port_fails_before_starting_a_server(self):
        with patch.object(library_web, "make_server") as create:
            self.assertEqual(adslib.run(["--port", "65536"], stderr=io.StringIO()), 1)
        create.assert_not_called()

    def cli(self, *args, expected=0):
        result = subprocess.run(
            [
                sys.executable,
                "-X",
                "utf8",
                "-S",
                str(SCRIPTS_DIR / "adslib.py"),
                "--library-dir",
                str(self.library),
                *args,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=25,
        )
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result.stdout

    def test_background_lifecycle_and_authenticated_stop(self):
        self.cli("status", "--port", "0", expected=3)
        self.cli("--port", "0", "--no-open")
        try:
            record = adslib.find_service(self.library, 0)
            self.assertIsNotNone(record)
            port = record["port"]
            self.assertIn(str(port), self.cli("status", "--port", "0"))
            self.cli("--port", "0", "start", "--no-open")
            self.assertEqual(len(adslib.managed_services(self.library)), 1)
            for headers in (
                {},
                {"Authorization": "Bearer incorrect"},
                {
                    "Authorization": f"Bearer {record['token']}",
                    "Origin": "http://evil.invalid",
                },
            ):
                request = Request(
                    f"http://127.0.0.1:{port}/api/service/stop",
                    data=b"",
                    headers=headers,
                )
                with self.assertRaises(HTTPError) as rejected:
                    urlopen(request, timeout=3)
                self.assertEqual(rejected.exception.code, 403)
            stats = adslib.running_library(port, self.library)
            self.assertNotIn(record["token"], json.dumps(stats))
            self.cli("restart", "--port", "0", "--no-open")
            replacement = adslib.find_service(self.library, 0)
            self.assertNotEqual(replacement["instance"], record["instance"])
            self.assertFalse(self.library.exists())
        finally:
            self.cli("stop", "--port", "0")
        self.cli("status", "--port", "0", expected=3)
        self.cli("stop", "--port", "0")
        self.assertEqual(list(adslib.runtime_dir().glob("*.json")), [])

    def test_unmanaged_service_is_left_running(self):
        server = self.start_server(self.library)
        self.cli("status", "--port", str(server.server_port), expected=3)
        self.cli("stop", "--port", str(server.server_port))
        self.assertIsNotNone(adslib.running_library(server.server_port, self.library))

    def test_background_collision_remains_discoverable_and_wrong_library_is_safe(self):
        occupied = self.start_server(self.root / "other")
        port = str(occupied.server_port)
        self.cli("start", "--port", port, "--no-open")
        try:
            record = adslib.find_service(self.library, int(port))
            self.assertNotEqual(record["port"], int(port))
            self.cli(
                "stop",
                "--library-dir",
                str(self.root / "unrelated"),
                "--port",
                str(record["port"]),
            )
            self.assertIsNotNone(adslib.find_service(self.library, int(port)))
            self.cli("restart", "--port", port, "--no-open")
            self.assertIsNotNone(adslib.find_service(self.library, int(port)))
        finally:
            self.cli("stop", "--port", port)
        self.assertIsNotNone(adslib.running_library(int(port), self.root / "other"))

    def test_stale_and_malformed_records_are_ignored(self):
        directory = adslib.runtime_dir()
        directory.mkdir()
        (directory / "bad.json").write_text("{", encoding="utf-8")
        (directory / "stale.json").write_text(
            json.dumps({"library_dir": str(self.library), "port": 0}), encoding="utf-8"
        )
        self.assertEqual(adslib.managed_services(self.library), [])

    def test_simultaneous_starts_reuse_one_service(self):
        try:
            with ThreadPoolExecutor(max_workers=3) as pool:
                results = list(
                    pool.map(lambda _: self.cli("start", "--port", "0"), range(3))
                )
            self.assertEqual(len(results), 3)
            self.assertEqual(len(adslib.managed_services(self.library)), 1)
        finally:
            self.cli("stop", "--port", "0")


if __name__ == "__main__":
    unittest.main()
