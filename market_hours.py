"""Shared market-hours logic for CLI and menu bar app."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time as dt_time, timedelta
from zoneinfo import ZoneInfo

WEEKDAYS = frozenset({0, 1, 2, 3, 4})  # Mon–Fri
THRESHOLD = timedelta(minutes=30)

# Exchange-local closed days (full sessions off). Keys match MARKET_SCHEDULE tz values.
EXCHANGE_HOLIDAYS: dict[str, frozenset[date]] = {
    "Asia/Tokyo": frozenset(
        {
            # JPX / TSE — https://www.jpx.co.jp/english/corporate/about-jpx/calendar/
            date(2026, 1, 1),
            date(2026, 1, 2),
            date(2026, 1, 12),
            date(2026, 2, 11),
            date(2026, 2, 23),
            date(2026, 3, 20),
            date(2026, 4, 29),
            date(2026, 5, 4),
            date(2026, 5, 5),
            date(2026, 5, 6),
            date(2026, 7, 20),
            date(2026, 8, 11),
            date(2026, 9, 21),
            date(2026, 9, 22),
            date(2026, 9, 23),
            date(2026, 10, 12),
            date(2026, 11, 3),
            date(2026, 11, 23),
            date(2026, 12, 31),
            date(2027, 1, 1),
            date(2027, 1, 11),
            date(2027, 2, 11),
            date(2027, 2, 23),
            date(2027, 3, 22),
            date(2027, 4, 29),
            date(2027, 5, 3),
            date(2027, 5, 4),
            date(2027, 5, 5),
            date(2027, 7, 19),
            date(2027, 8, 11),
            date(2027, 9, 20),
            date(2027, 9, 23),
            date(2027, 10, 11),
            date(2027, 11, 3),
            date(2027, 11, 23),
            date(2027, 12, 31),
        }
    ),
    "Asia/Seoul": frozenset(
        {
            # KRX — global.krx.co.kr market holiday calendar
            date(2026, 1, 1),
            date(2026, 2, 16),
            date(2026, 2, 17),
            date(2026, 2, 18),
            date(2026, 3, 2),
            date(2026, 5, 1),
            date(2026, 5, 5),
            date(2026, 5, 25),
            date(2026, 6, 3),
            date(2026, 7, 17),
            date(2026, 8, 17),
            date(2026, 9, 24),
            date(2026, 9, 25),
            date(2026, 10, 5),
            date(2026, 10, 9),
            date(2026, 12, 25),
            date(2026, 12, 31),
            date(2027, 1, 1),
            date(2027, 2, 8),
            date(2027, 2, 9),
            date(2027, 3, 1),
            date(2027, 5, 3),
            date(2027, 5, 5),
            date(2027, 5, 13),
            date(2027, 7, 19),
            date(2027, 8, 16),
            date(2027, 9, 14),
            date(2027, 9, 15),
            date(2027, 9, 16),
            date(2027, 10, 4),
            date(2027, 10, 11),
            date(2027, 12, 27),
            date(2027, 12, 31),
        }
    ),
    "Asia/Kolkata": frozenset(
        {
            date(2026, 1, 15),  # Municipal Corporation Election — Maharashtra
            date(2026, 1, 26),  # Republic Day
            date(2026, 3, 3),  # Holi
            date(2026, 3, 26),  # Shri Ram Navami
            date(2026, 3, 31),  # Shri Mahavir Jayanti
            date(2026, 4, 3),  # Good Friday
            date(2026, 4, 14),  # Dr. Baba Saheb Ambedkar Jayanti
            date(2026, 5, 1),  # Maharashtra Day
            date(2026, 5, 28),  # Bakri Id
            date(2026, 6, 26),  # Muharram
            date(2026, 9, 14),  # Ganesh Chaturthi
            date(2026, 10, 2),  # Mahatma Gandhi Jayanti
            date(2026, 10, 20),  # Dussehra
            date(2026, 11, 10),  # Diwali-Balipratipada
            date(2026, 11, 24),  # Prakash Gurpurb Sri Guru Nanak Dev
            date(2026, 12, 25),  # Christmas
        }
    ),
    "America/New_York": frozenset(
        {
            # 2026 — NYSE/Nasdaq full-day closures (America/New_York)
            date(2026, 1, 1),  # New Year's Day
            date(2026, 1, 19),  # Martin Luther King, Jr. Day
            date(2026, 2, 16),  # Washington's Birthday
            date(2026, 4, 3),  # Good Friday
            date(2026, 5, 25),  # Memorial Day
            date(2026, 6, 19),  # Juneteenth
            date(2026, 7, 3),  # Independence Day (observed)
            date(2026, 9, 7),  # Labor Day
            date(2026, 11, 26),  # Thanksgiving Day
            date(2026, 12, 25),  # Christmas Day
            # 2027
            date(2027, 1, 1),  # New Year's Day
            date(2027, 1, 18),  # Martin Luther King, Jr. Day
            date(2027, 2, 15),  # Washington's Birthday
            date(2027, 3, 26),  # Good Friday
            date(2027, 5, 31),  # Memorial Day
            date(2027, 6, 18),  # Juneteenth (observed)
            date(2027, 7, 5),  # Independence Day (observed)
            date(2027, 9, 6),  # Labor Day
            date(2027, 11, 25),  # Thanksgiving Day
            date(2027, 12, 24),  # Christmas Day (observed)
        }
    ),
}

# NYSE early closes: regular session ends 13:00 ET; after-hours begins then.
EXCHANGE_EARLY_CLOSE: dict[str, dict[date, dt_time]] = {
    "America/New_York": {
        date(2026, 11, 27): dt_time(13, 0),  # Day after Thanksgiving
        date(2026, 12, 24): dt_time(13, 0),  # Christmas Eve
        date(2027, 11, 26): dt_time(13, 0),  # Day after Thanksgiving
    },
}

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
    # US equity sessions in exchange local time (DST via America/New_York).
    # In Singapore (UTC+8): when US is on EST, pre/regular/after are roughly
    # 17:00–22:30 / 22:30–05:00+1 / 05:00+1–09:00+1 SGT; when US is on EDT, each
    # boundary is one hour earlier in SGT.
    {
        "tz": "America/New_York",
        "summary": "NYSE & Nasdaq — Pre-market",
        "start": (4, 0),
        "end": (9, 30),
    },
    {
        "tz": "America/New_York",
        "summary": "NYSE & Nasdaq — Regular trading",
        "start": (9, 30),
        "end": (16, 0),
    },
    {
        "tz": "America/New_York",
        "summary": "NYSE & Nasdaq — After-hours",
        "start": (16, 0),
        "end": (20, 0),
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


def is_exchange_holiday(on: datetime, session: MarketSession) -> bool:
    closed = EXCHANGE_HOLIDAYS.get(session.tz_key)
    if not closed:
        return False
    return on.astimezone(session.tz).date() in closed


def effective_session_times(
    exchange_date: date,
    session: MarketSession,
) -> tuple[dt_time, dt_time]:
    start, end = session.start, session.end
    early = EXCHANGE_EARLY_CLOSE.get(session.tz_key, {}).get(exchange_date)
    if early is not None:
        if "Regular trading" in session.summary:
            end = early
        elif "After-hours" in session.summary:
            start = early
    return start, end


def session_bounds(day: datetime, session: MarketSession) -> tuple[datetime, datetime]:
    cal = day.astimezone(session.tz).date()
    start_t, end_t = effective_session_times(cal, session)
    start = datetime.combine(cal, start_t, tzinfo=session.tz)
    end = datetime.combine(cal, end_t, tzinfo=session.tz)
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
            exchange_day = day.astimezone(session.tz).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            if exchange_day.weekday() not in session.weekdays:
                continue
            if is_exchange_holiday(exchange_day, session):
                continue
            start, end = session_bounds(exchange_day, session)
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
    if "Pre-market" in summary:
        return "pre"
    if "Regular trading" in summary or "Regular Market" in summary:
        return "reg"
    if "After-hours" in summary:
        return "after"
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
    if status.session_note:
        return f"{status.label} {status.session_note}  {format_duration(remaining)}"
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
    phase = status.session_note
    phase_text = f" ({phase})" if phase else ""
    if status.event == "opens":
        return (f"{flag} opens in 30 minutes{phase_text}", "Market opening soon")
    if status.event == "lunch":
        return (f"{flag} lunch break in 30 minutes", "Session ending soon")
    return (f"{flag} closes in 30 minutes{phase_text}", "Market closing soon")


def format_session_bounds_sgt(
    session: MarketSession,
    *,
    on_date: datetime,
) -> tuple[str, str]:
    """Human-readable start/end in Asia/Singapore for a session on its exchange calendar day."""
    sgt = ZoneInfo("Asia/Singapore")
    if on_date.tzinfo is None:
        on_date = on_date.replace(tzinfo=session.tz)
    day_local = on_date.astimezone(session.tz).replace(hour=0, minute=0, second=0, microsecond=0)
    start, end = session_bounds(day_local, session)
    return (
        start.astimezone(sgt).strftime("%a %H:%M"),
        end.astimezone(sgt).strftime("%a %H:%M"),
    )


def _verify_us_sgt_reference_windows() -> None:
    """Raise AssertionError if US session edges do not match known EST/EDT SGT offsets."""
    sgt = ZoneInfo("Asia/Singapore")
    sessions = [s for s in load_market_sessions() if s.tz_key == "America/New_York"]
    sessions.sort(key=lambda s: s.start)

    # US standard time (EST): Monday 2026-01-12
    winter_day = datetime(2026, 1, 12, 12, 0, tzinfo=ZoneInfo("America/New_York"))
    winter_bounds = [format_session_bounds_sgt(s, on_date=winter_day) for s in sessions]
    assert winter_bounds[0] == ("Mon 17:00", "Mon 22:30"), winter_bounds[0]
    assert winter_bounds[1] == ("Mon 22:30", "Tue 05:00"), winter_bounds[1]
    assert winter_bounds[2] == ("Tue 05:00", "Tue 09:00"), winter_bounds[2]

    # US daylight time (EDT): Monday 2026-06-15
    summer_day = datetime(2026, 6, 15, 12, 0, tzinfo=ZoneInfo("America/New_York"))
    summer_bounds = [format_session_bounds_sgt(s, on_date=summer_day) for s in sessions]
    assert summer_bounds[0] == ("Mon 16:00", "Mon 21:30"), summer_bounds[0]
    assert summer_bounds[1] == ("Mon 21:30", "Tue 04:00"), summer_bounds[1]
    assert summer_bounds[2] == ("Tue 04:00", "Tue 08:00"), summer_bounds[2]

    # zoneinfo must shift NY↔SGT offset by 1h across DST (13h vs 12h)
    pre = sessions[0]
    w_start, _ = session_bounds(winter_day.replace(hour=0, minute=0, second=0, microsecond=0), pre)
    s_start, _ = session_bounds(summer_day.replace(hour=0, minute=0, second=0, microsecond=0), pre)
    assert w_start.astimezone(sgt).hour == 17
    assert s_start.astimezone(sgt).hour == 16


def _verify_jpx_holidays() -> None:
    jst = ZoneInfo("Asia/Tokyo")
    sessions = [s for s in load_market_sessions() if s.tz_key == "Asia/Tokyo"]
    now = datetime(2026, 11, 3, 10, 0, tzinfo=jst).astimezone()
    status = market_status(sessions, now=now)
    assert status.state == "CLOSED", status
    assert status.event_at.astimezone(jst).date() == date(2026, 11, 4), status.event_at


def _verify_krx_holidays() -> None:
    kst = ZoneInfo("Asia/Seoul")
    sessions = [s for s in load_market_sessions() if s.tz_key == "Asia/Seoul"]
    now = datetime(2026, 2, 17, 10, 0, tzinfo=kst).astimezone()
    status = market_status(sessions, now=now)
    assert status.state == "CLOSED", status
    assert status.event_at.astimezone(kst).date() == date(2026, 2, 19), status.event_at


def _verify_nyse_holidays() -> None:
    ny = ZoneInfo("America/New_York")
    sessions = [s for s in load_market_sessions() if s.tz_key == "America/New_York"]
    # Independence Day observed — Friday Jul 3, 2026
    now = datetime(2026, 7, 3, 11, 0, tzinfo=ny).astimezone()
    status = market_status(sessions, now=now)
    assert status.state == "CLOSED", status
    assert status.event_at.astimezone(ny).date() == date(2026, 7, 6), status.event_at
    # Early close — day after Thanksgiving 2026, regular until 13:00 ET
    now = datetime(2026, 11, 27, 12, 0, tzinfo=ny).astimezone()
    status = market_status(sessions, now=now)
    assert status.state == "OPEN", status
    assert status.session_note == "reg", status
    assert status.event_at.astimezone(ny).hour == 13, status.event_at


def _verify_nse_holidays() -> None:
    sessions = [s for s in load_market_sessions() if s.tz_key == "Asia/Kolkata"]
    ist = ZoneInfo("Asia/Kolkata")
    # Republic Day — no session window; next open is Tuesday.
    now = datetime(2026, 1, 26, 10, 0, tzinfo=ist).astimezone()
    status = market_status(sessions, now=now)
    assert status.state == "CLOSED", status
    assert status.event_at.astimezone(ist).date() == date(2026, 1, 27), status.event_at


if __name__ == "__main__":
    _verify_us_sgt_reference_windows()
    _verify_jpx_holidays()
    _verify_krx_holidays()
    _verify_nyse_holidays()
    _verify_nse_holidays()
    print("US session SGT windows (EST/EDT): OK")
    print("JPX/TSE 2026–2027 holidays: OK")
    print("KRX 2026–2027 holidays: OK")
    print("NYSE/Nasdaq 2026–2027 holidays: OK")
    print("NSE 2026 holidays: OK")
