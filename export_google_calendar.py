#!/usr/bin/env python3
"""Export market holidays and/or trading sessions as ICS for Google Calendar."""

from __future__ import annotations

import argparse
import re
from datetime import date, datetime, time as dt_time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import market_hours as mh

DEFAULT_START = date(2026, 1, 1)
DEFAULT_END = date(2027, 12, 31)

EXCHANGE_LABEL: dict[str, str] = {
    "Asia/Tokyo": "JPX/TSE",
    "Asia/Seoul": "KRX",
    "Asia/Kolkata": "NSE",
    "Asia/Hong_Kong": "HKEX",
    "America/New_York": "NYSE/Nasdaq",
}

# Optional human labels (exchange-local dates).
HOLIDAY_NAMES: dict[str, dict[date, str]] = {
    "Asia/Kolkata": {
        date(2026, 1, 15): "Municipal Corporation Election — Maharashtra",
        date(2026, 1, 26): "Republic Day",
        date(2026, 3, 3): "Holi",
        date(2026, 3, 26): "Shri Ram Navami",
        date(2026, 3, 31): "Shri Mahavir Jayanti",
        date(2026, 4, 3): "Good Friday",
        date(2026, 4, 14): "Dr. Baba Saheb Ambedkar Jayanti",
        date(2026, 5, 1): "Maharashtra Day",
        date(2026, 5, 28): "Bakri Id",
        date(2026, 6, 26): "Muharram",
        date(2026, 9, 14): "Ganesh Chaturthi",
        date(2026, 10, 2): "Mahatma Gandhi Jayanti",
        date(2026, 10, 20): "Dussehra",
        date(2026, 11, 10): "Diwali-Balipratipada",
        date(2026, 11, 24): "Prakash Gurpurb Sri Guru Nanak Dev",
        date(2026, 12, 25): "Christmas",
    },
    "America/New_York": {
        date(2026, 1, 1): "New Year's Day",
        date(2026, 1, 19): "Martin Luther King, Jr. Day",
        date(2026, 2, 16): "Washington's Birthday",
        date(2026, 4, 3): "Good Friday",
        date(2026, 5, 25): "Memorial Day",
        date(2026, 6, 19): "Juneteenth",
        date(2026, 7, 3): "Independence Day (observed)",
        date(2026, 9, 7): "Labor Day",
        date(2026, 11, 26): "Thanksgiving Day",
        date(2026, 12, 25): "Christmas Day",
        date(2027, 1, 1): "New Year's Day",
        date(2027, 1, 18): "Martin Luther King, Jr. Day",
        date(2027, 2, 15): "Washington's Birthday",
        date(2027, 3, 26): "Good Friday",
        date(2027, 5, 31): "Memorial Day",
        date(2027, 6, 18): "Juneteenth (observed)",
        date(2027, 7, 5): "Independence Day (observed)",
        date(2027, 9, 6): "Labor Day",
        date(2027, 11, 25): "Thanksgiving Day",
        date(2027, 12, 24): "Christmas Day (observed)",
    },
}

EARLY_CLOSE_NAMES: dict[date, str] = {
    date(2026, 11, 27): "Day after Thanksgiving",
    date(2026, 12, 24): "Christmas Eve",
    date(2027, 11, 26): "Day after Thanksgiving",
}


def ics_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def fold_lines(content: str) -> str:
    out: list[str] = []
    for raw in content.splitlines():
        line = raw
        first = True
        while line:
            limit = 75 if first else 74
            if len(line) <= limit:
                out.append((" " + line) if not first else line)
                break
            if first:
                out.append(line[:75])
                line = line[75:]
            else:
                out.append(" " + line[:74])
                line = line[74:]
            first = False
    return "\r\n".join(out) + "\r\n"


def dtstamp() -> str:
    return datetime.now(ZoneInfo("UTC")).strftime("%Y%m%dT%H%M%SZ")


def date_to_ics(d: date) -> str:
    return d.strftime("%Y%m%d")


def session_slug(summary: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", summary).strip("-").lower()
    return slug[:48]


def all_day_vevent(
    *,
    uid: str,
    on: date,
    summary: str,
    description: str,
) -> str:
    end = on + timedelta(days=1)
    return "\r\n".join(
        (
            "BEGIN:VEVENT",
            f"UID:{ics_escape(uid)}",
            f"DTSTAMP:{dtstamp()}",
            f"DTSTART;VALUE=DATE:{date_to_ics(on)}",
            f"DTEND;VALUE=DATE:{date_to_ics(end)}",
            f"SUMMARY:{ics_escape(summary)}",
            f"DESCRIPTION:{ics_escape(description)}",
            "TRANSP:TRANSPARENT",
            "END:VEVENT",
        )
    )


def timed_vevent(
    *,
    uid: str,
    tz_key: str,
    start: datetime,
    end: datetime,
    summary: str,
    description: str,
) -> str:
    return "\r\n".join(
        (
            "BEGIN:VEVENT",
            f"UID:{ics_escape(uid)}",
            f"DTSTAMP:{dtstamp()}",
            f"DTSTART;TZID={tz_key}:{start.strftime('%Y%m%dT%H%M%S')}",
            f"DTEND;TZID={tz_key}:{end.strftime('%Y%m%dT%H%M%S')}",
            f"SUMMARY:{ics_escape(summary)}",
            f"DESCRIPTION:{ics_escape(description)}",
            "TRANSP:OPAQUE",
            "END:VEVENT",
        )
    )


def wrap_calendar(*, calname: str, events: list[str]) -> str:
    header = "\r\n".join(
        (
            "BEGIN:VCALENDAR",
            "VERSION:2.0",
            "PRODID:-//Market Hours//EN",
            "CALSCALE:GREGORIAN",
            "METHOD:PUBLISH",
            f"X-WR-CALNAME:{ics_escape(calname)}",
        )
    )
    footer = "END:VCALENDAR"
    body = "\r\n".join(events)
    return fold_lines(f"{header}\r\n{body}\r\n{footer}")


def daterange(start: date, end: date) -> list[date]:
    days: list[date] = []
    d = start
    while d <= end:
        days.append(d)
        d += timedelta(days=1)
    return days


def build_holidays_only() -> str:
    """All-day closures and NYSE early-close reminders (no timed sessions)."""
    events: list[str] = []

    for tz_key in sorted(mh.EXCHANGE_HOLIDAYS, key=lambda k: mh.MARKET_META.get(k, ("", 99))[1]):
        flag, _order = mh.MARKET_META[tz_key]
        venue = EXCHANGE_LABEL[tz_key]
        names = HOLIDAY_NAMES.get(tz_key, {})
        for on in sorted(mh.EXCHANGE_HOLIDAYS[tz_key]):
            label = names.get(on, "Market holiday")
            summary = f"{flag} {venue} closed — {label}"
            description = (
                f"Full-day closure for {venue}.\n"
                f"Exchange timezone: {tz_key}.\n"
                f"Date (exchange local): {on.isoformat()}."
            )
            uid = f"{tz_key}-{on.isoformat()}-closed@market-hours"
            events.append(all_day_vevent(uid=uid, on=on, summary=summary, description=description))

    flag = mh.MARKET_META["America/New_York"][0]
    venue = EXCHANGE_LABEL["America/New_York"]
    for on, close_at in sorted(mh.EXCHANGE_EARLY_CLOSE.get("America/New_York", {}).items()):
        label = EARLY_CLOSE_NAMES.get(on, "Early close")
        summary = f"{flag} {venue} early close — {label} (1:00 PM ET)"
        description = (
            f"Regular cash session ends {close_at.strftime('%H:%M')} America/New_York.\n"
            f"After-hours begins at the same time.\n"
            f"Date: {on.isoformat()}."
        )
        uid = f"America/New_York-{on.isoformat()}-early@market-hours"
        events.append(all_day_vevent(uid=uid, on=on, summary=summary, description=description))

    return wrap_calendar(calname="Market Hours — Exchange Holidays", events=events)


def build_combined(*, start: date, end: date) -> str:
    """Timed sessions on open weekdays; all-day closed on exchange holidays."""
    events: list[str] = []
    all_sessions = mh.load_market_sessions()
    grouped = mh.group_markets(all_sessions)

    for tz_key in sorted(grouped, key=lambda k: mh.MARKET_META.get(k, ("", 99))[1]):
        flag, _order = mh.MARKET_META[tz_key]
        venue = EXCHANGE_LABEL.get(tz_key, tz_key)
        sessions = grouped[tz_key]
        tz = ZoneInfo(tz_key)
        names = HOLIDAY_NAMES.get(tz_key, {})
        closed = mh.EXCHANGE_HOLIDAYS.get(tz_key, frozenset())

        for d in daterange(start, end):
            exchange_day = datetime.combine(d, dt_time(0, 0), tzinfo=tz)
            if exchange_day.weekday() not in mh.WEEKDAYS:
                continue

            if d in closed:
                label = names.get(d, "Market holiday")
                summary = f"{flag} {venue} closed — {label}"
                description = (
                    f"Full-day closure for {venue}.\n"
                    f"Exchange timezone: {tz_key}.\n"
                    f"Date (exchange local): {d.isoformat()}."
                )
                uid = f"{tz_key}-{d.isoformat()}-closed@market-hours"
                events.append(
                    all_day_vevent(uid=uid, on=d, summary=summary, description=description)
                )
                continue

            early = mh.EXCHANGE_EARLY_CLOSE.get(tz_key, {}).get(d)
            for session in sessions:
                start_dt, end_dt = mh.session_bounds(exchange_day, session)
                summary = f"{flag} {session.summary}"
                lines = [
                    session.summary,
                    f"Exchange timezone: {tz_key}.",
                    f"Local: {start_dt.strftime('%H:%M')}–{end_dt.strftime('%H:%M')}.",
                ]
                if early is not None:
                    lines.append(f"NYSE early close day ({early.strftime('%H:%M')} ET).")
                description = "\n".join(lines)
                uid = (
                    f"{tz_key}-{d.isoformat()}-{session_slug(session.summary)}@market-hours"
                )
                events.append(
                    timed_vevent(
                        uid=uid,
                        tz_key=tz_key,
                        start=start_dt,
                        end=end_dt,
                        summary=summary,
                        description=description,
                    )
                )

    return wrap_calendar(calname="Market Hours — Sessions & Holidays", events=events)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Write ICS for Google Calendar (Settings → Import)."
    )
    parser.add_argument(
        "--mode",
        choices=("combined", "holidays-only"),
        default="combined",
        help="combined: sessions + holidays (default); holidays-only: old all-day export",
    )
    parser.add_argument(
        "--from",
        dest="from_date",
        type=date.fromisoformat,
        default=DEFAULT_START,
        metavar="YYYY-MM-DD",
        help=f"First exchange date for sessions (default {DEFAULT_START})",
    )
    parser.add_argument(
        "--to",
        dest="to_date",
        type=date.fromisoformat,
        default=DEFAULT_END,
        metavar="YYYY-MM-DD",
        help=f"Last exchange date for sessions (default {DEFAULT_END})",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Output .ics path",
    )
    args = parser.parse_args()

    if args.output is None:
        root = Path(__file__).resolve().parent
        args.output = (
            root / "market-holidays.ics"
            if args.mode == "holidays-only"
            else root / "market-calendar.ics"
        )

    if args.from_date > args.to_date:
        parser.error("--from must be on or before --to")

    if args.mode == "holidays-only":
        cal = build_holidays_only()
    else:
        cal = build_combined(start=args.from_date, end=args.to_date)

    args.output.write_text(cal, encoding="utf-8")
    event_count = cal.count("BEGIN:VEVENT")
    print(f"Wrote {args.output} ({event_count} events, mode={args.mode})")
    print("Google Calendar: Settings → Import → Create new calendar → select this file.")
    print("Remove old recurring market calendars to avoid duplicate US sessions.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())