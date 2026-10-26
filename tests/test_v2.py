"""Regression and safety tests for the v2 command expansion."""

from __future__ import annotations

import json
import hashlib
import io
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
from unittest.mock import patch

from prompt_toolkit.document import Document

from core import advanced_files, apps, file_tools, games, media, productivity, workspaces
from core.commands import COMMANDS, CommandProcessor
from core.extended_commands import handles as handles_v2
from core.i18n import command_description, translate_message
from core.network import download, validate_url
from core.shell import CleyxCompleter
from core import system


class RegistrationAndCompletionTests(unittest.TestCase):
    def test_all_extended_command_families_are_registered(self) -> None:
        for name in ("whoami", "top", "tree", "download", "todo", "matrix", "cleyx"):
            with self.subTest(command=name):
                self.assertIn(name, COMMANDS)
                self.assertTrue(handles_v2(name))

    def test_prefix_and_subcommand_completion(self) -> None:
        completer = CleyxCompleter()
        n_commands = {item.text for item in completer.get_completions(Document("n"), None)}
        self.assertIn("netstat", n_commands)
        self.assertIn("note", n_commands)
        to_commands = {item.text for item in completer.get_completions(Document("to"), None)}
        self.assertIn("todo", to_commands)
        self.assertIn("top", to_commands)
        self.assertIn("touch", to_commands)
        todo_commands = {item.text for item in completer.get_completions(Document("todo "), None)}
        self.assertEqual(todo_commands, {"add", "list", "done", "remove", "clear"})

    def test_localized_help_and_usage(self) -> None:
        with patch("core.i18n.get_config", return_value={"language": "tr"}):
            self.assertEqual(command_description("whoami", "Who am I"), "Geçerli Windows kullanıcı adını göster")
            self.assertEqual(translate_message("Usage: hash <file>"), "Kullanım: hash <dosya>")

    def test_root_command_parser_dispatches_v2_system_commands(self) -> None:
        shell = type("FakeShell", (), {"cwd": Path.cwd(), "restart_requested": False})()
        processor = CommandProcessor(shell)
        self.assertTrue(processor.execute("whoami"))
        self.assertTrue(processor.execute("hostname"))
        self.assertTrue(processor.execute("unknown-cmd"))


class PersistenceTests(unittest.TestCase):
    def test_config_language_and_prompt_persist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch("core.config.APP_DIR", root), patch("core.config.CONFIG_FILE", root / "config.json"), patch("core.config.APPS_FILE", root / "apps.json"):
                from core.config import get_config, set_language, set_prompt
                set_language("tr")
                set_prompt("cleyx:{cwd}$")
                self.assertEqual(get_config()["language"], "tr")
                self.assertEqual(get_config()["prompt"], "cleyx:{cwd}$")

    def test_todo_note_and_alias_storage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch("core.config.APP_DIR", root), patch("core.productivity.TODO_FILE", root / "todos.json"), \
                 patch("core.productivity.NOTES_FILE", root / "notes.json"), patch("core.productivity.ALIASES_FILE", root / "aliases.json"):
                task = productivity.todo_add("test task")
                productivity.todo_done(int(task["id"]))
                self.assertTrue(productivity.todo_list()[0]["done"])
                note = productivity.note_add("a searchable note")
                self.assertEqual(productivity.note_search("SEARCHABLE")[0]["id"], note["id"])
                productivity.alias_add("ll", "ls")
                self.assertEqual(productivity.aliases()["ll"], "ls")
                with self.assertRaises(ValueError):
                    productivity.alias_add("bad", "python -c print(1)")
                with self.assertRaises(ValueError):
                    productivity.alias_add("ls", "pwd")

    def test_alias_recursion_is_stopped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            alias_path = Path(tmp) / "aliases.json"
            alias_path.write_text(json.dumps({"first": "second", "second": "first"}), encoding="utf-8")
            with patch("core.productivity.ALIASES_FILE", alias_path):
                processor = CommandProcessor(object())
                self.assertTrue(processor.execute("first"))


class FileSafetyTests(unittest.TestCase):
    def test_hash_grep_wc_and_find(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "Example.TXT"
            target.write_text("Alpha beta\nalpha gamma", encoding="utf-8")
            self.assertEqual(advanced_files.sha256_file(target), hashlib.sha256(target.read_bytes()).hexdigest())
            self.assertEqual(advanced_files.grep_file(target, "ALPHA"), [(1, "Alpha beta"), (2, "alpha gamma")])
            self.assertEqual(advanced_files.word_character_counts(target), (2, 4, 22))
            self.assertEqual(advanced_files.find_matches(root, "example"), [target])

    def test_zip_extract_backup_and_restore(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source"
            source.mkdir()
            (source / "data.txt").write_text("hello", encoding="utf-8")
            archive = root / "backup.zip"
            productivity.backup(source, archive)
            destination = root / "restored"
            paths = productivity.restore_backup(archive, destination)
            self.assertEqual((destination / "source" / "data.txt").read_text(encoding="utf-8"), "hello")
            self.assertEqual(len(paths), 1)

    def test_zip_traversal_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "bad.zip"
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.writestr("../escape.txt", "bad")
            with self.assertRaises(ValueError):
                advanced_files.extract_zip(archive, root / "out")
            self.assertFalse((root / "escape.txt").exists())

    def test_zip_does_not_overwrite_without_explicit_consent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "data.zip"
            with zipfile.ZipFile(archive, "w") as bundle:
                bundle.writestr("file.txt", "new")
            destination = root / "out"
            destination.mkdir()
            (destination / "file.txt").write_text("old", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                advanced_files.extract_zip(archive, destination)
            self.assertEqual((destination / "file.txt").read_text(encoding="utf-8"), "old")

    def test_download_requires_https(self) -> None:
        with self.assertRaises(ValueError):
            validate_url("http://example.com/file", https_only=True)
        self.assertEqual(validate_url("example.com/file", https_only=True), "https://example.com/file")

    @patch("core.network.requests.get")
    def test_download_refuses_existing_destination_and_preserves_part(self, get_mock) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            destination = root / "result.bin"
            destination.write_bytes(b"keep")
            with self.assertRaises(FileExistsError):
                download("https://example.com/result.bin", destination)
            partial = root / "new.bin.part"
            partial.write_bytes(b"partial-user-data")
            with self.assertRaises(FileExistsError):
                download("https://example.com/result.bin", root / "new.bin")
            get_mock.assert_not_called()


class ApplicationTests(unittest.TestCase):
    def test_registered_python_script_compatibility(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            target = root / "sample.py"
            target.write_text("print('ok')", encoding="utf-8")
            with patch("core.apps.ensure_app_dir"), patch("core.apps.APPS_FILE", root / "apps.json"), \
                 patch("core.apps.discover_apps", return_value=[]):
                apps.add_app("sample", str(target))
                matches = apps.find_apps("sam")
                self.assertEqual(matches[0]["name"], "sample")
                self.assertEqual(matches[0]["source"], "registered")


class DesktopIntegrationTests(unittest.TestCase):
    def test_every_root_command_has_a_dispatch_route(self) -> None:
        from core import v3_commands
        routed = {"app", "config", "language"}
        routed.update(name for name in COMMANDS if " " not in name and hasattr(CommandProcessor, f"cmd_{name}"))
        routed.update(name for name in COMMANDS if " " not in name and handles_v2(name))
        routed.update(name for name in COMMANDS if " " not in name and v3_commands.handles(name))
        expected = {name for name in COMMANDS if " " not in name}
        self.assertEqual(expected - routed, set())

    def test_unexpected_command_exception_does_not_end_shell(self) -> None:
        processor = CommandProcessor(SimpleNamespace())
        with patch("core.commands.v3_commands.dispatch", side_effect=UnicodeDecodeError("utf-8", b"\x81", 0, 1, "bad byte")), \
             patch("core.commands.console.print") as output:
            self.assertTrue(processor.execute("doctor"))
            self.assertTrue(processor.execute("version"))
        output.assert_called()

    def test_doctor_reports_one_failed_check_and_continues(self) -> None:
        from core.v3_commands import _documentation
        output = []
        with patch("core.v3_commands.psutil.virtual_memory", side_effect=RuntimeError("unsupported")), \
             patch("core.v3_commands.console.print", side_effect=lambda *args, **kwargs: output.append(str(args[0]))):
            self.assertTrue(_documentation("doctor", []))
        self.assertTrue(any("Available RAM GiB: Unavailable" in item for item in output))
        self.assertTrue(any("CPU cores:" in item for item in output))

    def test_doctor_reports_virtual_environment_status(self) -> None:
        from core.v3_commands import _documentation
        output = []
        with patch("core.v3_commands.console.print", side_effect=lambda *args, **kwargs: output.append(str(args[0]))):
            self.assertTrue(_documentation("doctor", []))
        virtual_env = next(item for item in output if item.startswith("Virtual environment:"))
        self.assertIn(virtual_env, {"Virtual environment: True", "Virtual environment: False"})

    def test_workspace_and_workshop_both_autocomplete(self) -> None:
        completer = CleyxCompleter()
        for prefix in ("workspace ", "workshop "):
            with self.subTest(prefix=prefix):
                found = {item.text for item in completer.get_completions(Document(prefix), None)}
                self.assertIn("create", found)
                self.assertIn("run", found)

    def test_subprocess_invalid_utf8_is_replaced_not_raised(self) -> None:
        result = subprocess.run(
            [sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'prefix\\x81suffix')"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", check=True,
        )
        self.assertEqual(result.stdout, "prefix\ufffdsuffix")

    def test_windows_subprocess_discovery_handles_missing_decoded_output(self) -> None:
        empty = SimpleNamespace(returncode=0, stdout=None, stderr=None)
        with patch("core.apps.subprocess.run", return_value=empty) as run:
            self.assertEqual(apps._discover_appsfolder_apps(), [])
            self.assertEqual(run.call_args.kwargs["encoding"], "utf-8")
            self.assertEqual(run.call_args.kwargs["errors"], "replace")
        with patch("core.system.subprocess.run", return_value=empty):
            self.assertEqual(system._gpu_name(), "Unavailable")
            self.assertEqual(system.gpu_names(), [])

    def test_ping_handles_missing_decoded_output(self) -> None:
        processor = CommandProcessor(SimpleNamespace())
        empty = SimpleNamespace(returncode=1, stdout=None, stderr=None)
        with patch("core.commands.socket.getaddrinfo"), patch("core.commands.subprocess.run", return_value=empty) as run:
            self.assertTrue(processor.execute("ping example.com"))
        self.assertEqual(run.call_args.kwargs["encoding"], "utf-8")
        self.assertEqual(run.call_args.kwargs["errors"], "replace")

    def test_every_registered_root_command_is_autocompleted(self) -> None:
        completer = CleyxCompleter()
        suggestions = {item.text for item in completer.get_completions(Document(""), None)}
        expected = {name for name in COMMANDS if " " not in name}
        self.assertLessEqual(expected, suggestions)

    def test_every_registered_subcommand_is_autocompleted(self) -> None:
        completer = CleyxCompleter()
        subcommands = [name.split(maxsplit=1) for name in COMMANDS if " " in name]
        for parent, child in subcommands:
            with self.subTest(parent=parent, child=child):
                suggestions = {item.text for item in completer.get_completions(Document(parent + " "), None)}
                self.assertIn(child.split()[0], suggestions)

    @patch("core.shell.run_in_terminal")
    def test_reminder_output_uses_prompt_toolkit_terminal_handoff(self, run_in_terminal_mock) -> None:
        from core.shell import Shell
        with patch("core.shell.ensure_app_dir"), patch("core.shell.FileHistory"), \
             patch("core.shell.PromptSession") as prompt_session:
            shell = Shell(cwd=Path.cwd())
        loop = Mock()
        loop.call_soon_threadsafe.side_effect = lambda callback: callback()
        prompt_session.return_value.app = SimpleNamespace(is_running=True, loop=loop)
        shell.session = prompt_session.return_value
        shell._notify_reminder("test")
        run_in_terminal_mock.assert_called_once()

    def test_v3_help_descriptions_are_localized(self) -> None:
        with patch("core.i18n.get_config", return_value={"language": "tr"}):
            untranslated = [name for name, description in COMMANDS.items()
                            if command_description(name, description) == description]
        self.assertEqual(untranslated, [])

    def test_launch_confirmation_is_localized(self) -> None:
        with patch("core.i18n.get_config", return_value={"language": "tr"}):
            message = translate_message("Launch application 'Discord' from Start Menu? [y/N]: ")
        self.assertIn("başlatılsın mı?", message)

    def test_version_comparison(self) -> None:
        from core.v3_commands import _version_tuple
        self.assertGreater(_version_tuple("v3.1.0"), _version_tuple("3.0.9"))
        self.assertEqual(_version_tuple("3.0"), (3, 0, 0, 0))

    def test_app_discovery_cache_and_fuzzy_alias(self) -> None:
        apps.invalidate_discovery_cache()
        candidate = {"name": "Visual Studio Code", "path": "C:/Apps/Code.exe", "source": "Start Menu"}
        with patch("core.apps._discover_windows_apps", return_value=[candidate]) as scan, \
             patch("core.apps._discover_standard_install_apps", return_value=[]), \
             patch("core.apps.list_apps", return_value={}):
            self.assertEqual(apps.discover_apps()[0]["name"], "Visual Studio Code")
            apps.discover_apps()
            scan.assert_called_once()
            self.assertEqual(apps.find_apps("vscode")[0]["name"], "Visual Studio Code")
            apps.discover_apps(refresh=True)
            self.assertEqual(scan.call_count, 2)
        apps.invalidate_discovery_cache()

    def test_game_search_supports_spaced_fuzzy_query(self) -> None:
        with patch("core.games.discover_games", return_value=[{"name": "ULTRAKILL", "path": "C:/Games/ULTRAKILL", "source": "Steam"}]):
            matches = games.search_games("ultra kill")
        self.assertEqual(matches[0]["name"], "ULTRAKILL")

    def test_steam_manifest_detection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "Steam"
            manifests = root / "steamapps"
            common = manifests / "common" / "Example Game"
            common.mkdir(parents=True)
            (manifests / "appmanifest_123.acf").write_text(
                '"AppState" { "appid" "123" "name" "Example Game" "installdir" "Example Game" }',
                encoding="utf-8",
            )
            with patch("core.games._steam_roots", return_value=[root]):
                detected = games._steam_games()
        self.assertEqual(detected[0]["name"], "Example Game")
        self.assertEqual(detected[0]["appid"], "123")
        self.assertEqual(detected[0]["launcher"], "steam")

    @patch("core.apps.os.startfile")
    def test_packaged_app_launch_uses_appsfolder_protocol(self, startfile):
        with patch("core.apps.os.name", "nt"):
            apps.launch_app("Calculator", [], resolved={
                "name": "Calculator", "path": "appsfolder:Microsoft.WindowsCalculator_8wekyb3d8bbwe!App",
            })
        startfile.assert_called_once_with("shell:AppsFolder\\Microsoft.WindowsCalculator_8wekyb3d8bbwe!App")

    def test_media_search_supports_unicode_names(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            video = root / "家庭の映像.MP4"
            video.write_bytes(b"sample")
            with patch("core.media.get_config", return_value={"video_folders": [str(root)]}):
                self.assertEqual(media.find_media("家庭", "video"), [video])

    def test_workspace_data_only_persistence_and_url_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch("core.workspaces.ensure_app_dir"), patch("core.workspaces.WORKSPACES_FILE", root / "workspaces.json"):
                workspaces.create("coding")
                workspaces.add_step("coding", "app", "vscode", cwd=root)
                workspaces.add_step("coding", "url", "https://example.com", cwd=root)
                self.assertEqual(workspaces.get("coding"), [
                    {"type": "app", "value": "vscode"},
                    {"type": "url", "value": "https://example.com"},
                ])
                with self.assertRaises(ValueError):
                    workspaces.add_step("coding", "url", "javascript:alert(1)", cwd=root)

    def test_autocomplete_uses_cached_app_and_workspace_names(self) -> None:
        completer = CleyxCompleter()
        with patch("core.apps.cached_apps", return_value=[{"name": "Discord"}, {"name": "Visual Studio Code"}]), \
             patch("core.games.cached_games", return_value=[{"name": "ULTRAKILL"}]), \
             patch("core.apps.discover_apps", side_effect=AssertionError("autocomplete must not scan")), \
             patch("core.games.discover_games", side_effect=AssertionError("autocomplete must not scan")), \
             patch("core.workspaces.list_workspaces", return_value={"coding": []}):
            apps_result = {item.text for item in completer.get_completions(Document("launch dis"), None)}
            workspace_result = {item.text for item in completer.get_completions(Document("workspace run cod"), None)}
            multiword = list(completer.get_completions(Document("launch visual"), None))
            workspace_app = {item.text for item in completer.get_completions(Document("workspace addapp coding dis"), None)}
            game_result = {item.text for item in completer.get_completions(Document("play ultra"), None)}
            settings = {item.text for item in completer.get_completions(Document("settings "), None)}
        self.assertIn("Discord", apps_result)
        self.assertIn("coding", workspace_result)
        self.assertEqual(multiword[0].text, "Visual Studio Code")
        self.assertEqual(multiword[0].start_position, -6)
        self.assertIn("Discord", workspace_app)
        self.assertIn("ULTRAKILL", game_result)
        self.assertIn("sound", settings)

    @patch("core.v3_commands.application_services.launch_application")
    @patch("core.v3_commands.application_services.confirm_launch", return_value=False)
    @patch("core.v3_commands.apps.find_apps", return_value=[{
        "name": "Discord", "path": "C:/Apps/Discord.exe", "source": "Start Menu", "_score": "0",
    }])
    def test_application_launch_requires_confirmation(self, find_apps, confirm, launch):
        from core.v3_commands import dispatch
        self.assertTrue(dispatch(object(), "launch", ["discord"]))
        confirm.assert_called_once()
        launch.assert_not_called()

    def test_measurement_conversion(self) -> None:
        from core.v3_commands import _convert
        self.assertEqual(_convert("5", "km", "m"), "5 km = 5000 m")
        self.assertEqual(_convert("0", "c", "f"), "0°C = 32°F")

    def test_cleanup_only_removes_temp_root_direct_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp) / "temp"
            temp_root.mkdir()
            safe = temp_root / "old.tmp"
            outside = Path(tmp) / "outside.tmp"
            safe.write_text("safe", encoding="utf-8")
            outside.write_text("outside", encoding="utf-8")
            with patch("core.file_tools.tempfile.gettempdir", return_value=str(temp_root)):
                self.assertEqual(file_tools.remove_cleanup_candidates([safe, outside]), 1)
            self.assertFalse(safe.exists())
            self.assertTrue(outside.exists())

    @patch("core.v3_commands._confirm_windows", return_value=True)
    @patch("core.v3_commands.windows_controls.power_action")
    def test_shutdown_command_is_confirmation_gated(self, power_action, _confirm):
        from core.v3_commands import dispatch
        self.assertTrue(dispatch(object(), "shutdown", []))
        power_action.assert_called_once_with("shutdown")


class SafetyAndProductivityTests(unittest.TestCase):
    def test_env_masks_sensitive_key_names(self) -> None:
        with patch.dict(os.environ, {"APP_TOKEN": "secret-value", "NORMAL_SETTING": "visible"}, clear=True):
            values = dict(system.safe_environment())
        self.assertEqual(values["APP_TOKEN"], "<masked>")
        self.assertEqual(values["NORMAL_SETTING"], "visible")

    def test_duration_parser_and_limits(self) -> None:
        self.assertEqual(productivity.parse_duration("5m"), 300)
        self.assertEqual(productivity.parse_duration("1h"), 3600)
        for invalid in ("0s", "10x", "999999d"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                productivity.parse_duration(invalid)

    def test_shell_run_exits_without_restarting_windows(self) -> None:
        fake_session = Mock()
        fake_session.prompt.side_effect = ["exit"]
        with patch("core.shell.ensure_app_dir"), patch("core.shell.FileHistory"), \
             patch("core.shell.PromptSession", return_value=fake_session):
            from core.shell import Shell
            shell = Shell(cwd=Path.cwd())
            shell.run()
        self.assertFalse(shell.restart_requested)


if __name__ == "__main__":
    unittest.main()
