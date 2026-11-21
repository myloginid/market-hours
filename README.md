# Market Hours

Menu bar app and terminal tools that countdown global equity sessions and alert you **30 minutes before** an exchange opens or closes.

Runs on macOS 13+ as a **menu bar agent** (`LSUIElement`) with an optional live terminal board.

## Features

- **Menu bar** (`MKT`): per-market countdown, color-coded by urgency (green / orange / red).
- **Notifications**: macOS UserNotifications 30 minutes before open/close (enable via menu → *Enable Notifications*).
- **Single instance**: only one copy runs; lock file in `~/Library/Application Support/Market Hours/.lock`.
- **DST-aware**: all session times are defined in each exchange’s IANA timezone (`zoneinfo`); US hours use `America/New_York` so Singapore/local display shifts automatically when US switches between EST and EDT.

## Markets and sessions

| Region | Timezone | Sessions (local) |
|--------|----------|------------------|
| Japan | `Asia/Tokyo` | Morning 09:00–11:30, Afternoon 12:30–15:30 |
| Korea | `Asia/Seoul` | Regular 09:00–15:30 |
| India | `Asia/Kolkata` | Regular 09:15–15:30 |
| Hong Kong | `Asia/Hong_Kong` | Morning 09:30–12:00, Afternoon 13:00–16:00 |
| US | `America/New_York` | Pre-market 04:00–09:30, Regular 09:30–16:00, After-hours 16:00–20:00 |

Weekdays are Monday–Friday in each exchange’s calendar unless a session entry overrides `weekdays`.

### US sessions in Singapore time

US boundaries are stored in **New York** time; when viewed in **Asia/Singapore**:

| Session | US on **EST** (winter) | US on **EDT** (summer) |
|---------|------------------------|-------------------------|
| Pre-market | Mon 17:00 → 22:30 | Mon 16:00 → 21:30 |
| Regular | Mon 22:30 → Tue 05:00 | Mon 21:30 → Tue 04:00 |
| After-hours | Tue 05:00 → 09:00 | Tue 04:00 → Tue 08:00 |

The menu bar uses your Mac’s local timezone for countdowns; notification subtitles use the same.

## Project layout

| File | Purpose |
|------|---------|
| `market_hours.py` | Schedules, status logic, notifications helpers, DST sanity check |
| `market_menubar.py` | rumps menu bar application |
| `setup_market_hours.py` | py2app build configuration |
| `market-close-countdown` | Terminal live countdown (`Esc` to quit) |
| `market-hours` | Shell helper: `open ~/Applications/Market\ Hours.app` |

## Run from source (development)

```bash
cd /path/to/market-hours
python3 market_menubar.py
```

Terminal board:

```bash
./market-close-countdown          # live refresh
./market-close-countdown --once   # single snapshot
```

Verify US ↔ SGT windows (EST/EDT):

```bash
python3 market_hours.py
# prints: US session SGT windows (EST/EDT): OK
```

## Build the `.app` (py2app)

```bash
cd /path/to/market-hours
python3 -m venv .market-hours-venv
source .market-hours-venv/bin/activate
pip install py2app rumps pyobjc-framework-Cocoa pyobjc-framework-UserNotifications
python setup_market_hours.py py2app
```

Install:

```bash
# User Applications (no sudo)
ditto "dist/Market Hours.app" "$HOME/Applications/Market Hours.app"

# System Applications (sudo)
sudo ditto "dist/Market Hours.app" "/Applications/Market Hours.app"
```

Quit any running instance before replacing the bundle.

Current bundle version: **1.0.2** (`com.manish.market-hours`).

## Notifications

1. Launch the app and choose **Enable Notifications** (or **Send Test Alert**).
2. If denied, open **System Settings → Notifications → Market Hours** and allow alerts.

## License

Private project; see repository owner for redistribution terms.