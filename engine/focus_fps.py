"""Explicit opt-in and recovery through Deadlock's own cfg execution."""

from pathlib import Path
import re

from manager_core import Refused, read_json, safe, save, vdf_get

RECORD = "focus-fps.json"
CFG = {
    "enable": "spectator_hud_focus_on.cfg",
    "restore": "spectator_hud_focus_restore.cfg",
}


def active_setting_file():
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as key:
            steam, _ = winreg.QueryValueEx(key, "SteamPath")
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam\ActiveProcess") as key:
            account, _ = winreg.QueryValueEx(key, "ActiveUser")
    except OSError as error:
        raise Refused("Steamを開き、使用するアカウントを選択してください。") from error
    if not isinstance(steam, str) or not Path(steam).is_absolute() or type(account) is not int or not 0 < account < 2**32:
        raise Refused("Steamを開き、使用するアカウントを選択してください。")
    return safe(Path(steam) / "userdata" / str(account) / "1422450" / "local" / "cfg" / "machine_convars.vcfg")


def saved_value(path):
    try:
        if not path.is_file() or path.stat().st_size > 1024 * 1024:
            raise ValueError()
        text = path.read_text(encoding="utf-8-sig")
        value = vdf_get(text, ["config", "convars", "engine_no_focus_sleep"])
        if value is None or not re.fullmatch(r"[0-9]{1,10}", value) or int(value) >= 2**31:
            raise ValueError()
        return int(value)
    except (ValueError, OSError, UnicodeError) as error:
        raise Refused("Deadlockの現在のFPS設定を確認できません。設定の変更を中止しました。") from error


def cfg_data(value):
    return f"engine_no_focus_sleep {value}\n".encode("ascii")


class FocusFps:
    def __init__(self, home, game):
        self.record = safe(home / RECORD)
        self.game = safe(game)

    def read_record(self, profile):
        if not self.record.exists():
            return None
        try:
            data = read_json(self.record)
            if (
                data["schema"] == 1
                and data["game"] == str(self.game)
                and data["profile"] == str(profile)
                and type(data["before"]) is int
                and 0 < data["before"] < 2**31
                and data["staged"] in (None, *CFG)
            ):
                return data
        except (ValueError, OSError, KeyError, TypeError):
            pass
        raise Refused("FPS設定の復元記録とSteamアカウントまたはゲームの場所が一致しません。")

    def _remove_staged(self, record):
        mode = record["staged"]
        if mode is None:
            return
        cfg = safe(self.game / "cfg" / CFG[mode])
        if cfg.exists():
            if not cfg.is_file() or cfg.stat().st_size > 64 or cfg.read_bytes() != cfg_data(0 if mode == "enable" else record["before"]):
                raise Refused("専用cfgに別の内容があります。上書きや削除を中止しました。")
            cfg.unlink()

    def _reconcile(self, record, current):
        self._remove_staged(record)
        if current == 0:
            if record["staged"] is not None:
                record["staged"] = None
                save(self.record, record)
            return "pending"
        self.record.unlink()
        return "restored" if current == record["before"] else "different"

    def reconcile(self):
        if not self.record.exists():
            return "none"
        profile = active_setting_file()
        record = self.read_record(profile)
        return self._reconcile(record, saved_value(profile))

    def prepare(self, mode):
        profile = active_setting_file()
        current = saved_value(profile)
        record = self.read_record(profile)
        outcome = self._reconcile(record, current) if record is not None else "none"
        if mode == "restore" and outcome != "pending":
            return (), outcome
        if mode == "enable" and current == 0 and outcome == "none":
            return (), "already"
        old_record = record if outcome == "pending" else None
        record = old_record or {"schema": 1, "game": str(self.game), "profile": str(profile), "before": current}
        cfg = safe(self.game / "cfg" / CFG[mode])
        if cfg.exists():
            raise Refused("専用cfgと同じ名前のファイルがあります。既存ファイルは変更していません。")
        if not cfg.parent.is_dir():
            raise Refused("Deadlockのcfgフォルダーを確認できません。")
        value = 0 if mode == "enable" else record["before"]
        save(self.record, {**record, "staged": mode})
        try:
            with cfg.open("xb") as stream:
                stream.write(cfg_data(value))
        except FileExistsError as error:
            if old_record is None:
                self.record.unlink()
            else:
                save(self.record, old_record)
            raise Refused("専用cfgと同じ名前のファイルがあります。既存ファイルは変更していません。") from error
        return ("+exec", CFG[mode]), mode
