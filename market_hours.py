"""Shared market-hours logic for CLI and menu bar app."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time as dt_time, timedelta
from zoneinfo import ZoneInfo

WEEKDAYS = frozenset({0, 1, 2, 3, 4})  # Mon–Fri
THRESHOLD = timedelta(minutes=30)

MARKET_META: dict[str, tuple[str, int]] = {
    "Asia/Tokyo": ("🇯🇵", 1),
    "Asia/Seoul": ("🇰🇷", 2),
    "Asia/Kolkata": ("🇮🇳", 3),
    "Asia/Hong_Kong": ("🇭🇰", 4),
    "America/New_York": ("🇺🇸", 5),
}

# Regular weekday sessions, in each exchange's local timezone.
MARKET_SCHEDULE: tuple[dict[str, object], ...] = (
    {
        "tz": "Asia/Tokyo",
        "summary": "Tokyo (TSE) — Morning Session",
        "start": (9, 0),
        "end": (11, 30),
    },
    {
        "tz": "Asia/Tokyo",
        "summary": "Tokyo (TSE) — Afternoon Session",
        "start": (12, 30),
        "end": (15, 30),
    },
    {
        "tz": "Asia/Seoul",
        "summary": "Korea (KRX) — Regular Market",
        "start": (9, 0),
        "end": (15, 30),
    },
    {
        "tz": "Asia/Kolkata",
        "summary": "India (NSE) — Regular Market",
        "start": (9, 15),
        "end": (15, 30),
    },
    {
        "tz": "Asia/Hong_Kong",
        "summary": "HKEX — Morning Session",
        "start": (9, 30),
        "end": (12, 0),
    },
    {
        "tz": "Asia/Hong_Kong",
        "summary": "HKEX — Afternoon Session",
        "start": (13, 0),
        "end": (16, 0),
    },
    {
        "tz": "America/New_York",
        "summary": "NYSE & Nasdaq — Regular Market",
        "start": (9, 30),
        "end": (16, 0),
    },
)


@dataclass(frozen=True)
class MarketSession:
    summary: str
    tz: ZoneInfo
    tz_key: str
    start: dt_time
    end: dt_time
    weekdays: frozenset[int]


@dataclass(frozen=True)
class MarketStatus:
    label: str
    order: int
    state: str
    event: str
    event_at: datetime
    session_note: str = ""


def load_market_sessions() -> list[MarketSession]:
    sessions: list[MarketSession] = []
    for entry in MARKET_SCHEDULE:
        tz_key = str(entry["tz"])
        start = entry["start"]
        end = entry["end"]
        assert isinstance(start, tuple) and isinstance(end, tuple)
        sessions.append(
            MarketSession(
                summary=str(entry["summary"]),
                tz=ZoneInfo(tz_key),
                tz_key=tz_key,
                start=dt_time(start[0], start[1]),
                end=dt_time(end[0], end[1]),
                weekdays=entry.get("weekdays", WEEKDAYS),  # type: ignore[arg-type]
            )
        )
    return sessions


def group_markets(sessions: list[MarketSession]) -> dict[str, list[MarketSession]]:
    grouped: dict[str, list[MarketSession]] = {}
    for session in sessions:
        grouped.setdefault(session.tz_key, []).append(session)
    for tz_key in grouped:
        grouped[tz_key].sort(key=lambda s: s.start)
    return grouped


def session_bounds(day: datetime, session: MarketSession) -> tuple[datetime, datetime]:
    start = datetime.combine(day.date(), session.start, tzinfo=session.tz)
    end = datetime.combine(day.date(), session.end, tzinfo=session.tz)
    if end <= start:
        end += timedelta(days=1)
    return start, end


def iter_session_windows(
    sessions: list[MarketSession],
    *,
    now: datetime,
    horizon_days: int = 14,
) -> list[tuple[datetime, datetime, MarketSession]]:
    local_tz = now.tzinfo
    windows: list[tuple[datetime, datetime, MarketSession]] = []
    for offset in range(horizon_days + 1):
        day = (now + timedelta(days=offset)).replace(hour=0, minute=0, second=0, microsecond=0)
        for session in sessions:
            if day.weekday() not in session.weekdays:
                continue
            start, end = session_bounds(day, session)
            windows.append((start.astimezone(local_tz), end.astimezone(local_tz), session))
    windows.sort(key=lambda item: item[0])
    return windows


def same_market_day(left: datetime, right: datetime, tz: ZoneInfo) -> bool:
    return left.astimezone(tz).date() == right.astimezone(tz).date()


def next_session_start_same_day(
    windows: list[tuple[datetime, datetime, MarketSession]],
    after: datetime,
    tz: ZoneInfo,
) -> tuple[datetime, MarketSession] | None:
    after_date = after.astimezone(tz).date()
    for start, _end, session in windows:
        if start <= after:
            continue
        if start.astimezone(tz).date() == after_date:
            return start, session
    return None


def close_event_label(
    session: MarketSession,
    session_end: datetime,
    windows: list[tuple[datetime, datetime, MarketSession]],
) -> str:
    if next_session_start_same_day(windows, session_end, session.tz):
        return "lunch"
    return "closes"


def short_session_name(summary: str) -> str:
    if "Morning" in summary:
        return "morning"
    if "Afternoon" in summary:
        return "afternoon"
    return ""


def market_status(sessions: list[MarketSession], *, now: datetime) -> MarketStatus:
    tz_key = sessions[0].tz_key
    label, order = MARKET_META.get(tz_key, (sessions[0].summary, 99))
    windows = iter_session_windows(sessions, now=now)

    for start, end, session in windows:
        if start <= now < end:
            return MarketStatus(
                label=label,
                order=order,
                state="OPEN",
                event=close_event_label(session, end, windows),
                event_at=end,
                session_note=short_session_name(session.summary),
            )

    for idx, (start, end, session) in enumerate(windows):
        if start > now:
            if idx > 0:
                prev_start, prev_end, prev_session = windows[idx - 1]
                if (
                    prev_end <= now < start
                    and same_market_day(prev_end, start, session.tz)
                    and len(sessions) > 1
                ):
                    return MarketStatus(
                        label=label,
                        order=order,
                        state="LUNCH",
                        event="opens",
                        event_at=start,
                        session_note=short_session_name(session.summary),
                    )
            return MarketStatus(
                label=label,
                order=order,
                state="CLOSED",
                event="opens",
                event_at=start,
                session_note=short_session_name(session.summary),
            )

    raise RuntimeError(f"No upcoming sessions found for {label}")


def all_market_statuses(sessions: list[MarketSession], *, now: datetime) -> list[MarketStatus]:
    grouped = group_markets(sessions)
    statuses = [market_status(grouped[tz_key], now=now) for tz_key in grouped]
    statuses.sort(key=lambda item: item.order)
    return statuses


def format_duration(remaining: timedelta) -> str:
    total = max(0, int(remaining.total_seconds()))
    hours, rem = divmod(total, 3600)
    minutes, seconds = divmod(rem, 60)
    if hours >= 24:
        days, hours = divmod(hours, 24)
        return f"{days}d {hours:02d}h {minutes:02d}m"
    if hours:
        return f"{hours:02d}h {minutes:02d}m {seconds:02d}s"
    return f"{minutes:02d}m {seconds:02d}s"


def format_event_time(when: datetime) -> str:
    return when.strftime("%a %H:%M")


def status_tone(status: MarketStatus, remaining: timedelta) -> str:
    if status.state == "OPEN":
        if remaining <= THRESHOLD:
            return "orange"
        return "green"
    if status.event == "opens" and remaining <= THRESHOLD:
        return "light_green"
    return "red"


def format_menu_line(status: MarketStatus, *, now: datetime) -> str:
    remaining = status.event_at - now
    return f"{status.label}  {format_duration(remaining)}"


NOTIFY_SLACK = timedelta(seconds=59)


def notification_key(status: MarketStatus) -> str:
    return f"{status.order}:{status.event_at.isoformat()}:{status.event}"


def should_send_notification(remaining: timedelta) -> bool:
    if remaining > THRESHOLD:
        return False
    return THRESHOLD - NOTIFY_SLACK <= remaining


def notification_message(status: MarketStatus) -> tuple[str, str]:
    flag = status.label
    if status.event == "opens":
        return (f"{flag} opens in 30 minutes", "Market opening soon")
    return (f"{flag} closes in 30 minutes", "Market closing soon")
