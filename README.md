# Market Hours

Menu bar app and terminal tools that countdown global equity sessions and alert you **30 minutes before** an exchange opens or closes.

Runs on macOS 13+ as a **menu bar agent** (accessory activation policy; no dock icon) with an optional live terminal board.

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

Use **Python 3.12–3.14** for the build venv. **Python 3.15** currently produces a broken bundle (`ModuleNotFoundError: _math_integer` at launch).

**Easiest install** (one app, green **MKT** icon, no duplicate in `dist/`):

```bash
cd /path/to/market-hours
./scripts/install-app.sh
```

Manual build:

```bash
cd /path/to/market-hours
python3.14 -m venv .market-hours-venv   # or python3.12 / python3.13
source .market-hours-venv/bin/activate
pip install py2app rumps pyobjc-framework-Cocoa pyobjc-framework-UserNotifications
python setup_market_hours.py py2app
ditto "dist/Market Hours.app" "$HOME/Applications/Market Hours.app"
rm -rf "dist/Market Hours.app"   # avoid two icons in Finder
open "$HOME/Applications/Market Hours.app"
```

Launch **only** `~/Applications/Market Hours.app`. The copy under `dist/` is build output — if you leave it there, Finder shows two apps with the same name.

Current bundle version: **1.0.7** (`com.myloginid.market-hours`).

### Launch error (“Visit Website” / py2app dialog)

If the app dies immediately, run from Terminal to see the traceback:

```bash
~/Applications/Market\ Hours.app/Contents/MacOS/Market\ Hours
```

Rebuild with Python **3.14** (not 3.15) and reinstall the `.app`.

### No icon in the menu bar

1. Quit every copy: `pkill -x "Market Hours"`.
2. Launch: `open ~/Applications/Market\ Hours.app` (prefer this over running the binary from Terminal).
3. Look on the **right side** of the menu bar for the **clock icon** and **MKT** (or **MKT N** when markets are open).
4. On **macOS 26 (Tahoe)**, open **System Settings → Menu Bar** and turn **Market Hours** on. Tahoe can hide new items until they are allow-listed (even when the app is running).
5. Check menu bar overflow if you use Bartender or iBar.
6. Inspect `~/Library/Logs/market-hours.log` — you should see `started; sessions=9`, `status item pinned`, and usually `menubar visibility ok`.

## Notifications

1. Launch the app and choose **Enable Notifications** (or **Send Test Alert**).
2. If denied, open **System Settings → Notifications → Market Hours** and allow alerts.

## License

Private project; see repository owner for redistribution terms.