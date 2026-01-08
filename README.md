# Notebook + LCD Wall

This repo is a static GitHub Pages site (a Tufte-inspired notebook) plus a full-screen "LCD wall" page.

## Pages

- Home: `/`
- Posts: `/posts/<slug>/`
- Topics/Projects/About: `/topics.html`, `/projects.html`
- **LCD Wall**: `/lcd.html` — Full-screen dashboard for TVs/kiosks

## LCD Wall Display (`/lcd.html`)

A public-facing, full-screen information dashboard designed for:
- Digital signage / street displays
- Kiosk screens
- TV/monitor walls
- Any fullscreen presentation

### Features

- **Live Clock** — Monospace time display (updates per second)
- **Scrolling Ticker** — Message feed with price token substitution
- **3-Column Dashboard**:
  - **Prices**: BTC, XAU, EUR (from `data/prices.json`)
  - **Weather**: Temp, humidity, wind (from `data/weather.json`)
  - **Polls**: Rotating polls with QR code for votes (from `data/polls.json`)
- **Responsive**: Adapts to desktop (3 columns), tablet (2 columns), mobile (1 column)
- **Aesthetic**: Pixel grid + scanline overlay for authentic LED/CRT feel
- **Typography**: System sans-serif + monospace for clean, readable data

### Design System

See `LCD_DESIGN.md` for:
- Typography choices (Consolas/monospace for data)
- Color palette and contrast ratios
- Future enhancement possibilities (APIs, themes, animations)
- Data format specifications
- Responsive breakpoints

## Ticker

The ticker appears site-wide (home, posts, topics/projects/about, and the LCD wall).

### Data sources

- Primary messages: `data/ticker.json` (array of strings)
- Optional prices: `data/prices.json`
- Polls: `data/polls.json`
- Weather: `data/weather.json`

The ticker supports tokens:

- `{TIME}` → inserts UB + UTC time
- `{PRICE:KEY}` → replaced with `data/prices.json.values.KEY` when available

Example ticker line:

- `BTC {PRICE:BTCUSD} • XAU {PRICE:XAUUSD} • {TIME}`

## Feeding messages (inbox)

Because GitHub Pages is static, external sources (SMS/email/messenger) can't write to the site directly.

Instead:

1) Send a message into GitHub (workflow/webhook)
2) GitHub updates `data/ticker.json`
3) All pages pick up the new feed automatically

See `INBOX.md` for the full "Ticker Inbox" workflow and webhook details.

## Custom domain

GitHub Pages can serve this site from a custom domain (e.g. `wall.mn`).

High-level steps:

- GitHub repo → Settings → Pages → set **Custom domain**
- Configure DNS at your registrar (A/AAAA/CNAME as GitHub instructs)
- Enable HTTPS once DNS is live

## Deployment to screens

Use any device/player that can load a URL in kiosk mode:

- Android TV box / signage player app
- Windows mini-PC in kiosk mode
- Pro signage (Samsung/LG) "web page" content

Point all screens to the same URL:

- `https://<your-domain>/lcd.html`

Control content by updating `data/ticker.json`, `data/prices.json`, `data/weather.json`, and `data/polls.json`.

## Technical Stack

- **Hosting**: GitHub Pages (static, HTTPS)
- **Frontend**: Vanilla HTML/CSS/JavaScript (no frameworks)
- **Fonts**: System sans-serif (Helvetica/Segoe UI) + Monospace (Consolas/Monaco) for data
- **CI/CD**: GitHub Actions for ticker inbox webhook
- **Styling**: Custom CSS with responsive grid layout

## File Structure

```
├── index.html                    # Home page
├── topics.html                   # Topics listing
├── projects.html                 # Projects listing
├── lcd.html                      # LCD wall display ★
├── posts/
│   └── YYYY-MM-DD-slug/
│       └── index.md              # Markdown post
├── assets/
│   ├── css/
│   │   └── tufte.css             # All styling (site + LCD)
│   └── js/
│       ├── reader.js             # Font size/alignment controls
│       ├── ticker.js             # Ticker feed loader
│       ├── lcd_clock.js           # Live clock ★
│       ├── lcd_prices.js          # Price widget ★
│       ├── lcd_weather.js         # Weather widget ★
│       └── lcd_polls.js           # Poll widget + QR ★
├── data/
│   ├── ticker.json               # Messages feed
│   ├── prices.json               # Market data
│   ├── weather.json              # Weather data ★
│   └── polls.json                # Poll questions ★
├── tools/
│   ├── build.ps1                 # Build script
│   ├── generate_index.py          # Index generator
│   └── ticker_inbox.py            # Inbox processor
├── .github/
│   └── workflows/
│       └── ticker-inbox.yml       # GitHub Action
├── README.md                     # This file
├── LCD_DESIGN.md                 # Design system ★
├── DESIGN.md                     # Typography/style guide
├── INBOX.md                      # Ticker feed setup
└── .gitignore
```

★ = LCD wall related
