# LCD Display Design System

## Overview
The LCD wall (`/lcd.html`) is a full-screen information display designed for kiosks, TVs, and public screens. It combines a scrolling ticker feed with a structured dashboard of real-time data widgets.

## Design Principles

### Typography
- **System Font Stack**: `-apple-system, BlinkMacSystemFont, "Segoe UI", "Helvetica Neue"`
- **Monospace**: `ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas` for data/values
- **Rationale**: Modern sans-serif for readability at distance; monospace for numerical precision

### Color Palette
- **Background**: `#111` (dark gray/black)
- **Text Primary**: `rgba(255, 255, 255, 0.95)` (near-white for contrast)
- **Text Secondary**: `rgba(255, 255, 255, 0.65)` (muted labels)
- **Borders**: `rgba(255, 255, 255, 0.12-0.15)` (subtle grid structure)
- **Status**: `rgba(100, 255, 100, 0.9)` (green for "LIVE" indicator)

### Layout Strategy
- **3-Column Dashboard**: Prices | Weather | Polls (responsive to 2-column on tablet, 1-column on mobile)
- **Top Ticker**: Scrolling feed above dashboard
- **Header**: Clock + branding
- **Footer**: Status indicator ("LIVE") + system info

## Technical Features

### Currently Implemented
1. **Real-time Clock** (`lcd_clock.js`)
   - Updates every second in HH:MM format
   - Monospace styling for digital clock aesthetic

2. **Price Ticker** (`lcd_prices.js`)
   - Fetches JSON from `/data/prices.json`
   - Displays BTC, XAU, EUR with values
   - Updates on page load

3. **Weather Widget** (`lcd_weather.js`)
   - Fetches JSON from `/data/weather.json`
   - Shows temp, humidity, wind
   - Static data (can integrate with weather API)

4. **Poll Widget** (`lcd_polls.js`)
   - Fetches from `/data/polls.json`
   - Auto-rotates every 30 seconds
   - Displays QR code for voting (generated via api.qrserver.com)
   - Shows live vote counts

5. **Scrolling Ticker** (`ticker.js`)
   - Continuous scrolling message feed
   - Supports `{PRICE:KEY}` token replacement
   - Hover to pause
   - 75-second loop animation

6. **Pixel Grid + Scanline Overlay**
   - CSS-based effect for authentic LED/CRT aesthetic
   - `opacity: 0.18` for subtle but visible effect

## Possible Future Enhancements

### Data & Integration
- **Live Crypto APIs**: Replace static prices with CoinGecko/Binance
- **Weather API**: OpenWeather, WeatherAPI for real location data
- **News Feed**: RSS/JSON feed for rotating headlines
- **Social Media**: Twitter/X, Mastodon feed integration
- **WebSocket Updates**: Real-time price/poll ticks vs. polling

### UI & Interactions
- **Multiple Layouts**: Compact, expanded, carousel modes
- **Theme Toggle**: Dark/light modes or custom branding
- **Admin Dashboard**: Edit content without touching JSON files
- **Analytics**: Track poll votes, ticker engagement
- **Animations**: Smooth transitions, fade effects, glow states
- **Audio**: Notification sounds for poll rotation, price alerts

### Hardware & Deployment
- **Kiosk Mode**: Full-screen lockdown, auto-screensaver
- **Auto-rotation**: Landscape/portrait detection
- **Multiple Screens**: Daisy-chain displays or split layout
- **Power Management**: Scheduled on/off times
- **Mobile Fallback**: Optimized single-column for handheld displays

### Advanced Features
- **Message Queue**: Backend system for dynamic ticker feeds
- **A/B Testing**: Show different layouts to measure engagement
- **Geolocation**: Weather/data tailored to screen location
- **Performance Metrics**: FPS counter, data staleness indicator
- **Error Recovery**: Graceful fallbacks when APIs fail
- **Custom Domains**: White-label setup for customers

## Data Formats

### `/data/prices.json`
```json
{
  "values": {
    "BTCUSD": "$48,500",
    "XAUUSD": "$2,150",
    "EURUSD": "1.0920"
  }
}
```

### `/data/weather.json`
```json
{
  "location": "Ulaanbaatar",
  "temp": "−12°C",
  "humidity": "68%",
  "wind": "15 km/h",
  "condition": "Cloudy"
}
```

### `/data/polls.json`
```json
{
  "polls": [
    {
      "question": "What's your favorite programming language?",
      "options": ["Python", "JavaScript"],
      "votes": [42, 38]
    }
  ]
}
```

### `/data/ticker.json`
```json
[
  "BTC surged 5% today | Gold steady at {PRICE:XAUUSD}",
  "Weather: {PRICE:XAUUSD} and sunny ☀️",
  "New poll: Which tech stack is best? Vote via QR!"
]
```

## Responsive Behavior

- **Desktop (>1024px)**: 3-column dashboard
- **Tablet (680px–1024px)**: 2-column dashboard
- **Mobile (<680px)**: 1-column dashboard with safe-area insets

## Performance Notes

- **Scanline overlay**: Low opacity (~0.18) to avoid visual fatigue
- **Animation duration**: 75s for ticker ensures smooth scroll
- **Poll rotation**: 30s per poll (configurable in `lcd_polls.js`)
- **No auto-scroll**: Manual refresh required (can add fetch interval)

## Testing Checklist

- [ ] Clock updates every second
- [ ] Ticker scrolls continuously at 75s loop
- [ ] Poll rotates every 30s
- [ ] QR code generation works (api.qrserver.com)
- [ ] Vote counts display correctly
- [ ] Price values render in monospace
- [ ] Mobile responsive (1-column on <680px)
- [ ] Safe-area insets work on notched phones
- [ ] Scanline overlay visible but subtle
- [ ] Font hierarchy clear (headers > data > labels)

