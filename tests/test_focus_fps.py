import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "engine"))

from focus_fps import CFG, RECORD, FocusFps, cfg_data
from manager_core import Manager, Refused, save


class FocusFpsTests(TestCase):
    def setUp(self):
        directory = TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        folder = Path(directory.name)
        self.game = folder / "game" / "citadel"
        self.cfg = self.game / "cfg"
        self.cfg.mkdir(parents=True)
        (self.game / "gameinfo.gi").touch()
        exe = self.game.parent / "bin" / "win64" / "deadlock.exe"
        exe.parent.mkdir(parents=True)
        exe.touch()
        self.home = folder / "home"
        self.home.mkdir()
        self.setting = folder / "machine_convars.vcfg"
        self.write_saved("37")
        self.state = self.home / RECORD
        self.session = FocusFps(self.home, self.game)
        patcher = patch("focus_fps.active_setting_file", return_value=self.setting)
        self.profile = patcher.start()
        self.addCleanup(patcher.stop)

    def write_saved(self, value, extra=""):
        self.setting.write_text(
            '"config" { "convars" { "engine_no_focus_sleep" "' + value + '" ' + extra + " } }",
            encoding="utf-8",
        )

    def enable(self):
        self.assertEqual(self.session.prepare("enable"), (("+exec", CFG["enable"]), "enable"))

    def test_existing_value_and_other_settings_never_written(self):
        before = self.setting.read_bytes()
        self.enable()
        self.assertEqual((self.cfg / CFG["enable"]).read_bytes(), cfg_data(0))
        self.assertEqual(self.setting.read_bytes(), before)
        self.assertEqual(json.loads(self.state.read_text())["before"], 37)
        self.write_saved("0", '"new_setting" "10"')
        settings_after_game = self.setting.read_bytes()
        self.assertEqual(self.session.prepare("restore"), (("+exec", CFG["restore"]), "restore"))
        self.assertFalse((self.cfg / CFG["enable"]).exists())
        self.assertEqual((self.cfg / CFG["restore"]).read_bytes(), cfg_data(37))
        self.assertEqual(self.setting.read_bytes(), settings_after_game)
        self.write_saved("37", '"new_setting" "10"')
        self.assertEqual(self.session.reconcile(), "restored")
        self.assertFalse(self.state.exists())
        self.assertFalse((self.cfg / CFG["restore"]).exists())

    def test_autoexec_and_collision_are_kept(self):
        autoexec = self.cfg / "autoexec.cfg"
        autoexec.write_bytes(b"echo existing autoexec\n")
        foreign = self.cfg / CFG["enable"]
        foreign.write_bytes(cfg_data(0))
        with self.assertRaises(Refused):
            self.session.prepare("enable")
        self.assertEqual(autoexec.read_bytes(), b"echo existing autoexec\n")
        self.assertEqual(foreign.read_bytes(), cfg_data(0))
        self.assertFalse(self.state.exists())

    def test_owned_cfg_changed_by_user_is_not_removed(self):
        self.enable()
        foreign = self.cfg / CFG["enable"]
        foreign.write_bytes(b"echo replaced\n")
        self.write_saved("0")
        with self.assertRaises(Refused):
            self.session.prepare("restore")
        self.assertEqual(foreign.read_bytes(), b"echo replaced\n")
        self.assertTrue(self.state.exists())

    def test_restore_retry_after_manager_quits_unexpectedly(self):
        self.enable()
        self.write_saved("0")
        reopened = FocusFps(self.home, self.game)
        self.assertEqual(reopened.reconcile(), "pending")
        self.assertEqual(reopened.prepare("restore"), (("+exec", CFG["restore"]), "restore"))
        self.assertEqual(reopened.reconcile(), "pending")
        self.assertTrue(self.state.exists())

    def test_respects_manual_setting_changes(self):
        self.enable()
        self.write_saved("9")
        self.assertEqual(self.session.prepare("restore"), ((), "different"))
        self.assertIn(b'"9"', self.setting.read_bytes())
        self.assertFalse(self.state.exists())

    def test_zero_owned_by_user_is_left_alone(self):
        self.write_saved("0")
        self.assertEqual(self.session.prepare("enable"), ((), "already"))
        self.assertEqual(self.session.prepare("restore"), ((), "none"))
        self.assertFalse(self.state.exists())

    def test_refuses_other_account(self):
        self.enable()
        self.profile.return_value = self.setting.with_name("other_profile.vcfg")
        self.profile.return_value.write_text(self.setting.read_text(encoding="utf-8"), encoding="utf-8")
        with self.assertRaises(Refused):
            self.session.prepare("restore")
        self.assertTrue(self.state.exists())

    def test_unrecognized_setting_does_not_create_cfg(self):
        for value, extra in (("bad", ""), ("-5", ""), ("37", '"engine_no_focus_sleep" "0"')):
            with self.subTest(value=value, extra=extra):
                self.write_saved(value, extra)
                with self.assertRaises(Refused):
                    self.session.prepare("enable")
        self.assertFalse(self.state.exists())
        self.assertFalse((self.cfg / CFG["enable"]).exists())

    def test_normal_launch_is_unchanged_and_explicit_restore_can_launch(self):
        manager = Manager(self.home, self.home, busy=lambda: [])
        save(manager.config_file, {"game": str(self.game), "log": str(self.home / "game.log"), "enabled": False})
        with patch("manager_core.subprocess.Popen") as popen:
            manager.launch()
            self.assertNotIn("+exec", popen.call_args.args[0])
            self.profile.assert_not_called()
            self.assertEqual(manager.launch("restore")["focus"], "none")
            self.assertEqual(popen.call_count, 1)
            with self.assertRaises(Refused):
                manager.launch("enable")
            self.enable()
            self.write_saved("0")
            manager.launch("restore")
            self.assertEqual(popen.call_args.args[0][-2:], ["+exec", CFG["restore"]])

    def test_no_changes_while_game_is_running(self):
        manager = Manager(self.home, self.home, busy=lambda: ["deadlock.exe"])
        with self.assertRaises(Refused):
            manager.launch("enable")
        self.profile.assert_not_called()
