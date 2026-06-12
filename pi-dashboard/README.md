# Pi Weather Dashboard

An always-on weather, stocks, and news dashboard served by a Raspberry Pi,
displayed on a wall-mounted first-generation iPad (iOS 5) over your local Wi-Fi.

The Pi does all the work. The iPad opens one URL in Safari and never touches
the internet directly.

---

## What it shows

- Current temperature, conditions, feels-like, humidity, wind
- Today's high/low and rain probability
- 6-hour forecast bar
- Live stock strip: GOLD, OIL, TSX, S&P 500
- Scrolling news ticker: CBC, Kingston Whig-Standard, TheJournal.ie (Irish), Al Jazeera
- Sunrise and sunset times
- Nightly blackout screen (01:00–06:00) to save the display

---

## Requirements

- Raspberry Pi (any model with Wi-Fi — Zero W or better)
- Raspberry Pi OS (Lite or Desktop) with Python 3 installed
- Pi and iPad on the same Wi-Fi network
- Internet access from the Pi (to fetch weather, stocks, and news)

---

## One-time setup

### 1. Copy files to the Pi

Run this from your Mac (replace `<PI_IP>` with your Pi's IP address):

```bash
scp -r /Users/ardanhennessy/Documents/Claude/Code/pi-dashboard/ pi@<PI_IP>:~/dashboard
```

To find your Pi's IP, either check your router's device list or run on the Pi:
```bash
hostname -I
```

### 2. SSH into the Pi

```bash
ssh pi@<PI_IP>
```

### 3. Install the Python dependency

```bash
pip3 install requests
```

### 4. Test it manually first

```bash
cd ~/dashboard
python3 dashboard.py
```

You should see output like:
```
2026-04-22 21:40:19 INFO Weather fetched OK — 9°C Mainly clear
2026-04-22 21:40:19 INFO Stock OK: GOLD 4734.235 (-0.23%)
2026-04-22 21:40:19 INFO News OK: CBC (4 headlines)
2026-04-22 21:40:22 INFO Serving at http://0.0.0.0:8080/
```

From another terminal on your Mac, confirm it's working:
```bash
curl http://<PI_IP>:8080/
```

Press `Ctrl-C` to stop the manual test when done.

### 5. Install as a systemd service

```bash
sudo cp ~/dashboard/dashboard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable dashboard
sudo systemctl start dashboard
```

Verify it's running:
```bash
sudo systemctl status dashboard
```

The service will now start automatically on every boot and restart itself if it crashes.

---

## Setting up the iPad

### Find the Pi's permanent address

On the Pi, run:
```bash
hostname
```

This prints something like `raspberrypi`. Your permanent dashboard URL is:

```
http://raspberrypi.local:8080/
```

This address never changes, even if the Pi's IP changes — it uses mDNS
(Bonjour), which the first-gen iPad supports natively.

### Open the dashboard on the iPad

1. Open **Safari** on the iPad
2. Type `http://raspberrypi.local:8080/` in the address bar
3. Wait for the dashboard to load

### Add to Home Screen (removes all Safari chrome)

1. Tap the **Share** icon (box with arrow, bottom toolbar in Safari)
2. Tap **"Add to Home Screen"**
3. Name it `Dashboard` and tap **Add**
4. Press the Home button, find the Dashboard icon, tap it

The dashboard will now open fullscreen with no Safari address bar or toolbar.

### Prevent the iPad from sleeping

- Settings → General → Auto-Lock → **Never**
- Settings → Brightness & Wallpaper → drag brightness to a comfortable level

---

## Configuration

All settings are in `config.py` on the Pi. Edit and then restart the service:

```bash
nano ~/dashboard/config.py
sudo systemctl restart dashboard
```

| Setting | Default | Description |
|---|---|---|
| `LATITUDE` / `LONGITUDE` | 44.2312, -76.4860 | Kingston, ON |
| `LOCATION_NAME` | `"Kingston, ON"` | Display name |
| `PORT` | `8080` | HTTP port |
| `REST_START` / `REST_END` | `1`, `6` | Black screen window (01:00–06:00 local) |
| `FETCH_INTERVAL` | `600` | Weather poll interval (seconds) |
| `NEWS_PER_SOURCE` | `4` | Headlines fetched per news feed |
| `NEWS_FETCH_INTERVAL` | `900` | News poll interval (15 min) |
| `STOCK_FETCH_INTERVAL` | `300` | Stocks poll interval (5 min) |

### News sources

Edit the `NEWS_SOURCES` list in `config.py` to add or remove feeds.
Any RSS feed URL works.

### Stocks

Edit the `STOCKS` list in `config.py`. Symbols use Stooq notation:

| Symbol | Meaning |
|---|---|
| `xauusd` | Gold (USD/oz) |
| `cl.f` | WTI Crude Oil |
| `%5etsx` | TSX Composite |
| `%5espx` | S&P 500 |

---

## Refresh schedule

| Data | How often |
|---|---|
| Page reload | Every **120 seconds** |
| Weather | Every **10 minutes** |
| Stocks | Every **5 minutes** |
| News headlines | Every **15 minutes** |

Data is fetched in background threads on the Pi — the page reload just
picks up whatever was last cached. The dashboard never goes blank if a
fetch fails; it shows the last good data with a stale indicator.

---

## Day-to-day management

```bash
# View live logs
sudo journalctl -u dashboard -f

# Restart after a config change
sudo systemctl restart dashboard

# Check service status
sudo systemctl status dashboard

# Stop the service
sudo systemctl stop dashboard
```

---

## Troubleshooting

**"Safari cannot open the page"**
- Confirm the Pi is on and the service is running: `sudo systemctl status dashboard`
- Try the IP address instead of the hostname: `http://192.168.x.x:8080/`
- Confirm both devices are on the same Wi-Fi network

**"raspberrypi.local" doesn't resolve on the iPad**
- Make sure `avahi-daemon` is installed and running on the Pi:
  ```bash
  sudo apt install avahi-daemon
  sudo systemctl enable avahi-daemon
  sudo systemctl start avahi-daemon
  ```
- Alternatively, use the Pi's IP address directly

**Stocks show "Market data unavailable"**
- Pi has no internet access, or Stooq is temporarily down
- Last cached prices are shown automatically once data was fetched at least once

**News ticker shows "Loading news..."**
- Feeds haven't been fetched yet — wait 10 seconds and reload
- Check logs: `sudo journalctl -u dashboard -f`

**Screen is black at an unexpected time**
- Check `REST_START` / `REST_END` in `config.py`
- Default blackout is 01:00–06:00 local time on the Pi

**After a Pi reboot, the dashboard takes ~5 seconds to appear**
- Normal — the service starts, fetches weather/stocks/news, then begins serving

---

## Files

```
dashboard.py      Main server and HTML renderer
weather.py        Open-Meteo weather fetch and cache
stocks.py         Stooq stock price fetch
news.py           RSS news feed fetch
config.py         All configuration
dashboard.service systemd unit file
```
