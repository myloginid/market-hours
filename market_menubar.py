#!/usr/bin/env python3
"""Menu bar app for global stock market countdowns."""

from __future__ import annotations

import fcntl
import platform
import subprocess
import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path

import AppKit
import rumps
from rumps.events import before_start

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
import market_hours  # noqa: E402

LOCK_PATH = Path.home() / "Library/Application Support/Market Hours/.lock"
LOG_PATH = Path.home() / "Library/Logs/market-hours.log"
BUNDLE_ID = "com.myloginid.market-hours"
ICON_PATH = _ROOT / "menubar_icon.png"
MENU_BAR_HELP_PATH = Path.home() / "Library/Application Support/Market Hours/menu-bar-settings-shown"


def _log(message: str) -> None:
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(f"{datetime.now().isoformat()} {message}\n")
    except OSError:
        pass


STATUS_ITEM_AUTOSAVE = "com.myloginid.market-hours.status"


def _macos_major() -> int:
    try:
        return int(platform.mac_ver()[0].split(".", maxsplit=1)[0])
    except ValueError:
        return 0


def _status_item_on_menu_bar(button: object) -> bool:
    try:
        window = button.window()  # type: ignore[attr-defined]
        if window is None:
            return False
        screen = window.screen()
        if screen is None:
            return False
        frame = window.frame()
        visible = screen.visibleFrame()
        menu_bar_bottom = visible.origin.y + visible.size.height
        item_top = frame.origin.y + frame.size.height
        return abs(item_top - menu_bar_bottom) < 60
    except Exception:  # noqa: BLE001
        return False


def open_menu_bar_settings() -> None:
    for url in (
        "x-apple.systempreferences:com.apple.MenuBar-Settings.extension",
        "x-apple.systempreferences:com.apple.ControlCenter-Settings.extension",
    ):
        if subprocess.run(["open", url], check=False, capture_output=True).returncode == 0:
            return


def _maybe_show_menu_bar_onboarding() -> None:
    if _macos_major() < 26:
        return
    try:
        MENU_BAR_HELP_PATH.parent.mkdir(parents=True, exist_ok=True)
        if MENU_BAR_HELP_PATH.exists():
            return
        MENU_BAR_HELP_PATH.write_text(datetime.now().isoformat(), encoding="utf-8")
    except OSError:
        return
    open_menu_bar_settings()
    rumps.alert(
        "Where to find Market Hours",
        "This is not the Dock (bar at the bottom).\n\n"
        "1. System Settings → Menu Bar → Allow in the Menu Bar → Market Hours ON.\n"
        "2. Look at the top-right of the screen (next to the clock) for MKT.\n\n"
        "If you only see it in Settings, the allow-list was off — turn it ON and reopen the app.",
    )


@before_start.register
def _pin_status_item_at_launch() -> None:
    """macOS 26: stable autosave name + visible flag after rumps creates the status item."""
    from rumps.rumps import App as _RumpsApp

    inst = getattr(_RumpsApp, "*app_instance", None)
    if inst is None:
        return
    try:
        item = inst._nsapp.nsstatusitem
        item.setAutosaveName_(STATUS_ITEM_AUTOSAVE)
        item.setVisible_(True)
        item.setImage_(None)
        title = inst._title or "MKT"
        item.setTitle_(title)
        btn = item.button()
        if btn is not None:
            btn.setImagePosition_(AppKit.NSNoImage)
            btn.setTitle_(title)
            btn.setFont_(AppKit.NSFont.boldSystemFontOfSize_(13.0))
        policy = AppKit.NSApplication.sharedApplication().activationPolicy()
        _log(f"status item pinned title={title!r} activation_policy={policy}")
        _maybe_show_menu_bar_onboarding()
        rumps.Timer(inst._menubar_allowlist_hint, 3).start()
    except Exception as exc:  # noqa: BLE001
        _log(f"pin status item: {exc}\n{traceback.format_exc()}")


def open_notification_settings() -> None:
    urls = [
        f"x-apple.systempreferences:com.apple.Notifications-Settings.extension?{BUNDLE_ID}",
        "x-apple.systempreferences:com.apple.Notifications-Settings.extension",
        "x-apple.systempreferences:com.apple.preference.notifications",
    ]
    for url in urls:
        result = subprocess.run(["open", url], check=False, capture_output=True)
        if result.returncode == 0:
            return


def notification_access_status() -> str:
    try:
        import UserNotifications as UN

        status_holder: dict[str, int | None] = {"value": None}
        done = threading.Event()

        def handle_settings(settings: object) -> None:
            status_holder["value"] = int(settings.authorizationStatus())  # type: ignore[attr-defined]
            done.set()

        UN.UNUserNotificationCenter.currentNotificationCenter().getNotificationSettingsWithCompletionHandler_(
            handle_settings
        )
        done.wait(timeout=5)
        value = status_holder["value"]
        if value is None:
            return "unknown"

        mapping = {
            int(UN.UNAuthorizationStatusNotDetermined): "not_determined",
            int(UN.UNAuthorizationStatusDenied): "denied",
            int(UN.UNAuthorizationStatusAuthorized): "authorized",
            int(UN.UNAuthorizationStatusProvisional): "authorized",
            int(UN.UNAuthorizationStatusEphemeral): "authorized",
        }
        return mapping.get(value, "unknown")
    except Exception:  # noqa: BLE001
        return "unknown"


def request_notification_access(*, prompt_if_needed: bool = True) -> bool:
    try:
        import UserNotifications as UN

        result: dict[str, bool | None] = {"granted": None}
        done = threading.Event()

        def auth_handler(granted: bool, error: object | None) -> None:
            result["granted"] = bool(granted) and error is None
            done.set()

        def settings_handler(settings: object) -> None:
            status = settings.authorizationStatus()  # type: ignore[attr-defined]
            if status == UN.UNAuthorizationStatusAuthorized:
                result["granted"] = True
                done.set()
                return
            if status == UN.UNAuthorizationStatusNotDetermined:
                options = (
                    UN.UNAuthorizationOptionAlert
                    | UN.UNAuthorizationOptionSound
                    | UN.UNAuthorizationOptionBadge
                )
                UN.UNUserNotificationCenter.currentNotificationCenter().requestAuthorizationWithOptions_completionHandler_(
                    options,
                    auth_handler,
                )
                return
            result["granted"] = False
            done.set()

        UN.UNUserNotificationCenter.currentNotificationCenter().getNotificationSettingsWithCompletionHandler_(
            settings_handler
        )
        done.wait(timeout=15)
        granted = bool(result["granted"])

        if prompt_if_needed and not granted:
            rumps.alert(
                "Enable notifications for Market Hours",
                "Turn on Alerts in System Settings → Notifications → Market Hours, "
                "then choose Allow Notifications and Alerts.",
            )
            open_notification_settings()
        return granted
    except Exception:  # noqa: BLE001
        if prompt_if_needed:
            rumps.alert(
                "Enable notifications for Market Hours",
                "Open System Settings → Notifications → Market Hours and allow alerts.",
            )
            open_notification_settings()
        return False


def send_notification(title: str, subtitle: str, body: str) -> None:
    try:
        import UserNotifications as UN

        content = UN.UNMutableNotificationContent.alloc().init()
        content.setTitle_(title)
        content.setSubtitle_(subtitle)
        content.setBody_(body)
        content.setSound_(UN.UNNotificationSound.defaultSound())
        trigger = UN.UNTimeIntervalNotificationTrigger.triggerWithTimeInterval_repeats_(0.1, False)
        request_id = f"market-hours-{datetime.now().timestamp()}"
        request = UN.UNNotificationRequest.requestWithIdentifier_content_trigger_(
            request_id,
            content,
            trigger,
        )
        UN.UNUserNotificationCenter.currentNotificationCenter().addNotificationRequest_withCompletionHandler_(
            request,
            lambda _e: None,
        )
    except Exception:  # noqa: BLE001
        rumps.notification(title, subtitle, body)


def acquire_single_instance() -> None:
    LOCK_PATH.parent.mkdir(parents=True, exist_ok=True)
    lock_file = LOCK_PATH.open("w")
    try:
        fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        rumps.alert(
            "Market Hours is already running",
            "Look for MKT on the right side of the menu bar.\n\n"
            "If you do not see it: System Settings → Menu Bar → turn Market Hours ON, "
            "then quit this duplicate (Activity Monitor → Market Hours) and open the app once.",
        )
        raise SystemExit(0) from exc
    lock_file.write(str(Path(__file__).resolve()))
    lock_file.flush()

def _color(red: float, green: float, blue: float) -> object:
    return AppKit.NSColor.colorWithCalibratedRed_green_blue_alpha_(red, green, blue, 1.0)


# Dark row backgrounds + bright text for dark-mode menus (macOS forces light menu text).
TONE_STYLES: dict[str, tuple[object, object]] = {
    "green": (_color(0.05, 0.42, 0.12), _color(1.0, 1.0, 0.82)),
    "light_green": (_color(0.08, 0.34, 0.08), AppKit.NSColor.yellowColor()),
    "orange": (_color(0.62, 0.28, 0.0), AppKit.NSColor.whiteColor()),
    "red": (_color(0.52, 0.04, 0.04), AppKit.NSColor.yellowColor()),
}

MENU_FONT = AppKit.NSFont.boldSystemFontOfSize_(15.0)


def menu_item_attributes(tone: str) -> dict:
    background, foreground = TONE_STYLES[tone]
    return {
        AppKit.NSBackgroundColorAttributeName: background,
        AppKit.NSForegroundColorAttributeName: foreground,
        AppKit.NSFontAttributeName: MENU_FONT,
    }


class MarketHoursApp(rumps.App):
    def __init__(self) -> None:
        # Text-only status item — small menu-bar PNGs often render invisible on Tahoe.
        super().__init__("Market Hours", title="MKT", icon=None, quit_button=None)
        try:
            self.sessions = market_hours.load_market_sessions()
        except Exception as exc:  # noqa: BLE001
            rumps.alert("Market Hours failed to start", str(exc))
            raise
        _log(f"started; sessions={len(self.sessions)} menubar=text")
        self.market_items: list[rumps.MenuItem] = []
        self.notified: set[str] = set()
        self._build_menu()
        self.timer = rumps.Timer(self.refresh, 1)
        self.timer.start()
        self.refresh(None)
        self.title = self.title or "MKT"

    def _build_menu(self) -> None:
        self.menu.clear()
        for _ in market_hours.all_market_statuses(self.sessions, now=datetime.now().astimezone()):
            item = rumps.MenuItem("loading…")
            item.set_callback(None)
            self.market_items.append(item)
            self.menu.add(item)
        self.menu.add(rumps.separator)
        self.menu.add(rumps.MenuItem("Enable Notifications", callback=self.enable_notifications))
        self.menu.add(rumps.MenuItem("Send Test Alert", callback=self.send_test_alert))
        self.menu.add(rumps.separator)
        self.menu.add(rumps.MenuItem("Quit", callback=rumps.quit_application))

    @rumps.clicked("Enable Notifications")
    def enable_notifications(self, _sender: object) -> None:
        if request_notification_access(prompt_if_needed=True):
            rumps.notification("Market Hours", "Notifications enabled", "You will get 30-minute market alerts.")
        else:
            open_notification_settings()

    @rumps.clicked("Send Test Alert")
    def send_test_alert(self, _sender: object) -> None:
        if notification_access_status() != "authorized":
            request_notification_access(prompt_if_needed=True)
            return
        send_notification("Market Hours test", "Notifications are working", "🇺🇸 30-minute alerts are enabled")

    def refresh(self, _sender: object | None) -> None:
        try:
            now = datetime.now().astimezone()
            statuses = market_hours.all_market_statuses(self.sessions, now=now)
            open_count = sum(1 for status in statuses if status.state == "OPEN")

            for item, status in zip(self.market_items, statuses, strict=True):
                remaining = status.event_at - now
                tone = market_hours.status_tone(status, remaining)
                text = market_hours.format_menu_line(status, now=now)
                try:
                    padded = f"   {text}   "
                    title = AppKit.NSAttributedString.alloc().initWithString_attributes_(
                        padded,
                        menu_item_attributes(tone),
                    )
                    item._menuitem.setAttributedTitle_(title)  # noqa: SLF001
                except Exception:  # noqa: BLE001
                    item.title = text

            self.title = "MKT" if open_count == 0 else f"MKT {open_count}"
            self._check_notifications(statuses, now)
        except Exception as exc:  # noqa: BLE001
            _log(f"refresh error: {exc}\n{traceback.format_exc()}")

    def _check_notifications(
        self,
        statuses: list[market_hours.MarketStatus],
        now: datetime,
    ) -> None:
        for status in statuses:
            remaining = status.event_at - now
            if not market_hours.should_send_notification(remaining):
                continue
            key = market_hours.notification_key(status)
            if key in self.notified:
                continue
            self.notified.add(key)
            title, subtitle = market_hours.notification_message(status)
            send_notification(title, subtitle, status.event_at.strftime("%a %H:%M %Z"))

    def _menubar_allowlist_hint(self, sender: rumps.Timer | None) -> None:
        try:
            if sender is not None:
                sender.stop()
            btn = self._nsapp.nsstatusitem.button()
            if btn is None:
                return
            on_bar = _status_item_on_menu_bar(btn)
            if not on_bar:
                _log("status item not on menu bar (Tahoe allow-list or wrong display)")
                open_menu_bar_settings()
                rumps.alert(
                    "Allow Market Hours on the menu bar",
                    "Market Hours is running but MKT is not on the top menu bar.\n\n"
                    "System Settings → Menu Bar → Allow in the Menu Bar → "
                    "turn Market Hours ON.\n\n"
                    "Use the screen where the clock/Wi‑Fi live, then quit and reopen the app.",
                )
            else:
                _log("menubar item on screen menu bar")
        except Exception as exc:  # noqa: BLE001
            _log(f"menubar hint: {exc}")

def main() -> None:
    _log("launch")
    acquire_single_instance()
    MarketHoursApp().run()


if __name__ == "__main__":
    main()
