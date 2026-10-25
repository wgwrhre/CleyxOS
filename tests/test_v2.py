"""Regression and safety tests for the v2 command expansion."""

from __future__ import annotations

import json
import hashlib
import io
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import Mock
from unittest.mock import patch

from prompt_toolkit.document import Document

from core import advanced_files, apps, productivity
from core.commands import COMMANDS, CommandProcessor
from core.extended_commands import handles
from core.i18n import command_description, translate_message
from core.network import download, validate_url
from core.shell import CleyxCompleter
from core import system


class RegistrationAndCompletionTests(unittest.TestCase):
    def test_all_extended_command_families_are_registered(self) -> None:
        for name in ("whoami", "top", "tree", "download", "todo", "matrix", "cleyx"):
            with self.subTest(command=name):
                self.assertIn(name, COMMANDS)
                self.assertTrue(handles(name))

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
            with patch("core.apps.ensure_app_dir"), patch("core.apps.APPS_FILE", root / "apps.json"):
                apps.add_app("sample", str(target))
                matches = apps.find_apps("sam")
                self.assertEqual(matches[0]["name"], "sample")
                self.assertEqual(matches[0]["source"], "registered")


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
