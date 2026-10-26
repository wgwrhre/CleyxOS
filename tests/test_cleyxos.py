"""Focused tests for safety-critical calculator and filesystem behavior."""

from __future__ import annotations

import tempfile
import unittest
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

from core import apps
from core.commands import CommandProcessor, _evaluate
from core.filesystem import copy_path, create_file, delete_path, make_directory, read_text, resolve_path
from core.shell import Shell


class CalculatorTests(unittest.TestCase):
    def test_arithmetic_and_allowlisted_functions(self) -> None:
        self.assertEqual(_evaluate("2 + 3 * 4"), 14)
        self.assertAlmostEqual(_evaluate("sqrt(81) + sin(pi / 2)"), 10)

    def test_rejects_python_execution_constructs(self) -> None:
        for expression in ("__import__('os').getcwd()", "1 if True else 0", "open('x')"):
            with self.subTest(expression=expression), self.assertRaises(ValueError):
                _evaluate(expression)

    def test_rejects_unbounded_exponents_and_syntax_errors(self) -> None:
        with self.assertRaises(ValueError):
            _evaluate("2 ** 1000")
        with self.assertRaises(ValueError):
            _evaluate("2 +")


class FilesystemTests(unittest.TestCase):
    def test_file_and_directory_operations(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = resolve_path(root, "sample")
            make_directory(folder)
            source = resolve_path(root, "sample/note.txt")
            create_file(source)
            source.write_text("CleyxOS", encoding="utf-8")
            self.assertEqual(read_text(source), "CleyxOS")
            destination = resolve_path(root, "copy.txt")
            copy_path(source, destination)
            self.assertEqual(read_text(destination), "CleyxOS")
            delete_path(destination)
            self.assertFalse(destination.exists())


class UserFeatureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.processor = CommandProcessor(SimpleNamespace(cwd=Path.cwd()))

    @patch("core.shell.PromptSession")
    @patch("core.shell.ensure_app_dir")
    def test_history_does_not_search_replace_current_input(self, _ensure_dir, prompt_session):
        with patch("core.shell.FileHistory"):
            Shell()
        self.assertIs(prompt_session.call_args.kwargs["enable_history_search"], False)

    @patch("core.commands.set_language")
    def test_language_setting_accepts_supported_code(self, set_language_mock) -> None:
        self.assertTrue(self.processor.cmd_language(["tr"]))
        set_language_mock.assert_called_once_with("tr")

    @patch("core.commands.webbrowser.open", return_value=True)
    def test_open_defaults_to_https(self, browser_open) -> None:
        self.assertTrue(self.processor.cmd_open(["example.com"]))
        browser_open.assert_called_once_with("https://example.com", new=2)

    @patch("core.commands.webbrowser.open")
    def test_open_rejects_malformed_url(self, browser_open) -> None:
        with self.assertRaises(ValueError):
            self.processor.cmd_open(["http://"])
        browser_open.assert_not_called()

    @patch("core.apps._discover_windows_apps", return_value=[
        {"name": "Spotify", "path": "C:/Apps/Spotify.lnk", "source": "Start Menu"},
        {"name": "Spotify", "path": "C:/Apps/Spotify.exe", "source": "Windows installed-app registry"},
    ])
    @patch("core.apps._discover_standard_install_apps", return_value=[])
    @patch("core.apps._discover_path_apps", return_value=[])
    @patch("core.apps.list_apps", return_value={})
    def test_app_search_matches_names_and_deduplicates(self, _registered, _path_apps, _install_apps, _discovered) -> None:
        matches = apps.find_apps("spot")
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["name"], "Spotify")
        self.assertEqual(matches[0]["_score"], "1")


if __name__ == "__main__":
    unittest.main()