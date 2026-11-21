#!/usr/bin/env python3
"""Menu bar app for global stock market countdowns."""

from __future__ import annotations

import fcntl
import subprocess
import sys
import threading
import traceback
from datetime import datetime
from pathlib import Path

import AppKit
import rumps

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
import market_hours  # noqa: E402

LOCK_PATH = Path.home() / "Library/Application Support/Market Hours/.lock"
LOG_PATH = Path.home() / "Library/Logs/market-hours.log"
BUNDLE_ID = "com.manish.market-hours"
ICON_PATH = _ROOT / "menubar_icon.png"


def _log(message: str) -> None:
    try:
        LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as handle:
            handle.write(f"{datetime.now().isoformat()} {message}\n")
    except OSError:
        pass


def ensure_accessory_policy() -> None:
    """Menu bar (LSUIElement) apps must be .accessory or the status item may not appear."""
    app = AppKit.NSApplication.sharedApplication()
    app.setActivationPolicy_(AppKit.NSApplicationActivationPolicyAccessory)


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
        rumps.alert("Market Hours is already running", "Check the menu bar for the MKT icon.")
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
        app_kwargs: dict[str, object] = {"title": "MKT", "quit_button": None}
        if ICON_PATH.is_file():
            app_kwargs["icon"] = str(ICON_PATH)
        super().__init__("Market Hours", **app_kwargs)
        try:
            self.sessions = market_hours.load_market_sessions()
        except Exception as exc:  # noqa: BLE001
            rumps.alert("Market Hours failed to start", str(exc))
            raise
        _log(f"started; sessions={len(self.sessions)} icon={ICON_PATH.is_file()}")
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


def main() -> None:
    _log("launch")
    ensure_accessory_policy()
    acquire_single_instance()
    MarketHoursApp().run()


if __name__ == "__main__":
    main()
