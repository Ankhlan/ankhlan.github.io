# LCD Wall: Technical Capabilities & Roadmap

## Currently Working

✅ Real-time clock (updates per second)  
✅ 3-column responsive dashboard (desktop/tablet/mobile)  
✅ Scrolling ticker with price token substitution  
✅ Poll rotation with QR code generation  
✅ Vote counts display  
✅ Pixel grid + scanline overlay (LED aesthetic)  
✅ Monospace typography (Consolas/Monaco/system mono)  
✅ Safe-area insets (notched phones)  
✅ Static data feeds (JSON files)  

---

## Possible Features (By Category)

### 🔄 Real-Time Data Integration

**Crypto Prices**
- CoinGecko API (free, no auth): `https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,gold&vs_currencies=usd`
- Binance Spot API (lightweight): `https://api.binance.com/api/v3/ticker/price?symbol=BTCUSDT`
- Auto-update every 30–60 seconds via `fetch()` with interval
- Technical: Add `lcd_crypto.js`, update `assets/css/tufte.css` with animation/pulse effects

**Weather**
- OpenWeather API: `https://api.openweathermap.org/data/2.5/weather?q=Ulaanbaatar&appid=YOUR_KEY`
- WeatherAPI: `https://api.weatherapi.com/v1/current.json?key=YOUR_KEY&q=Ulaanbaatar`
- Replace static JSON with live fetch
- Add icons (sunny ☀️, cloudy ☁️, rainy 🌧️)
- Technical: Update `lcd_weather.js` to fetch live data

**Stock Market**
- yfinance-like endpoints (IEX Cloud, Finnhub)
- Show indices (S&P 500, NASDAQ, Hang Seng)
- Display as separate widget or integrate into prices widget
- Technical: New `lcd_stocks.js` module

**News Feed**
- RSS/JSON feed (MediaStack, NewsAPI, NewsData.io)
- Rotating headlines in ticker or separate widget
- Category filters (tech, finance, local)
- Technical: `lcd_news.js` + new data source

**Social Media**
- Twitter/X API: Stream or widget showing latest posts
- Mastodon API: Alternative social integration
- Discord/Slack webhooks: Real-time message bridge
- Technical: OAuth/API keys, likely backend service required

---

### 🎨 Visual & UX Enhancements

**Layout Variants**
- Compact mode: Hide headers, squeeze data, 2-row ticker
- Expanded mode: Large text, 1 widget full-screen
- Carousel mode: Cycle through widgets on timer
- Custom layouts: Draggable/configurable grid
- Technical: `localStorage` for preferences, CSS variants

**Themes**
- Dark (current) / Light / Neon / Retro arcade
- Custom brand colors (upload hex palette)
- Day/night auto-switch based on time or geolocation
- Technical: CSS custom properties (`--primary-color`), theme switcher JS

**Animations**
- Smooth fade/slide transitions between polls
- Price ticker up/down arrows (↑ green, ↓ red)
- Pulsing "LIVE" indicator
- Scroll easing (ease-in-out instead of linear)
- Animated scanlines (slow drift effect)
- Technical: CSS `@keyframes`, requestAnimationFrame

**Accessibility**
- High-contrast mode (AAA compliance)
- Adjustable font size for elderly viewers
- Screen reader support (ARIA labels)
- Keyboard navigation (Tab, arrow keys)
- Technical: ARIA attributes, focus management

---

### 📊 Interactivity & Engagement

**Live Polling**
- WebSocket for real-time vote sync (no page refresh)
- Vote via QR → backend → broadcast to all screens
- Multiple question types (Y/N, Likert scale, multiple choice)
- Live result charts (bar graphs, pie charts)
- Technical: Backend (Node.js, Python Flask) + WebSocket, or serverless (Firebase Realtime DB)

**Admin Dashboard**
- Web UI to edit ticker, prices, polls without touching JSON
- Schedule posts for future times
- Analytics: Vote counts, engagement metrics, screen uptime
- Content library (templates, media uploads)
- Technical: Full-stack app (React/Vue + API)

**Audience Interaction**
- Mobile companion app: Scan QR to vote + see live results
- Text-to-join: "Text VOTE to 1234" (SMS integration)
- Leaderboard: Top voters, trending topics
- Technical: Backend message queue, SMS gateway (Twilio)

---

### 🚀 Performance & Reliability

**Caching & Offline Mode**
- Service Worker: Cache JSON feeds for offline viewing
- Fallback content: Show last-known data if API fails
- Graceful degradation: Hide broken widgets, show placeholders
- Technical: Service Worker, IndexedDB

**Performance Optimization**
- Lazy-load images (news thumbnails, weather icons)
- Image compression (WebP, AVIF)
- Minified JS/CSS bundles
- Gzip compression via GitHub Pages
- Technical: Build step with esbuild/webpack

**Analytics & Monitoring**
- Track page views, FPS, load times
- Error logging (Sentry, LogRocket)
- Uptime monitoring (Pingdom, StatusCake)
- API response times
- Technical: Telemetry service integration

---

### 🔐 Security & Content Moderation

**Admin Authentication**
- GitHub OAuth for admins only
- Two-factor authentication (2FA)
- Edit history & rollback
- Technical: GitHub Gist/GitHub API + OAuth

**Content Filtering**
- Banned words / profanity filter
- Rate limiting (max posts per minute)
- Spam detection (duplicate messages)
- Moderate ticker before display
- Technical: Regex patterns, database rules

**SSL/TLS & API Keys**
- Environment variables for secrets (no hardcoding)
- API key rotation
- Webhook signature verification
- Technical: `.env` file, GitHub Secrets

---

### 🌐 Multi-Screen & Networking

**Daisy-Chain Displays**
- Multiple screens showing same content (current setup)
- Split-view: Different zones on different screens
- Master/replica: One screen controls others
- Technical: WebSocket broadcast, shared state server

**Geolocation Targeting**
- Show different content based on screen location
- Weather for office building, HQ, stores
- Local news for each region
- Technical: IP-based geolocation or manual screen config

**Screen Groups**
- Label screens by zone (entrance, hallway, lobby)
- Schedule content per zone (morning announcements, lunch deals)
- Technical: Backend admin panel with zone management

---

### 📱 Device-Specific Features

**Mobile Optimization**
- Full app mode: Hide address bar, lock orientation
- Responsive 1-column layout (current)
- Touch-optimized vote buttons
- Safe-area insets (current)
- Technical: Manifest.json, viewport-fit, meta tags

**TV-Specific**
- Remote control support (arrow keys, enter)
- Idle animations (screen saver on no data)
- Auto-brightness (detect ambient light?)
- Power management (scheduled on/off)
- Technical: JavaScript keyboard handlers, device API

**Kiosk Mode**
- Full-screen lockdown (F11, no menu bar)
- Auto-reload on crash
- Network failover (switch WiFi/4G)
- Technical: Browser automation (Selenium), device firmware

---

### 🎯 Monetization & Commercial

**White-Label**
- Resell as SaaS product for businesses
- Custom branding (logo, colors, domain)
- Multi-tenant architecture
- Technical: Backend service, tenant isolation

**Ad Network**
- Sponsor integrations (price ticker → Binance link)
- Banner space for sponsors
- Programmatic ads (rotate through sponsors)
- Technical: Ad manager backend, rotating impressions

**Premium Features**
- Free tier: Basic ticker + 1 widget
- Pro tier: All widgets + API access + admin dashboard
- Enterprise: Custom integrations, dedicated support
- Technical: Subscription management (Stripe, Patreon)

---

## Implementation Priorities

### Phase 1 (Next week)
1. Live crypto prices (CoinGecko API) → Replace static prices
2. Better error handling (fallback UI when APIs fail)
3. Admin panel MVP (edit ticker without JSON)

### Phase 2 (Month 1)
1. WebSocket real-time poll sync
2. Weather API integration
3. Theme switcher (dark/light)
4. Service Worker for offline

### Phase 3 (Month 2)
1. Mobile companion app (voting)
2. Analytics dashboard
3. Content scheduling
4. Multi-screen management

### Phase 4+ (Backlog)
1. News feed integration
2. White-label SaaS
3. Advanced monetization
4. Hardware-specific features

---

## Tech Stack Options

| Feature | Tool | Pros | Cons |
|---------|------|------|------|
| Real-time sync | WebSocket (Node.js) | Native, fast | Requires backend |
| Real-time sync | Firebase Realtime DB | No backend needed | Vendor lock-in |
| Real-time sync | Supabase (Postgres + Realtime) | Open-source feel | Still vendor |
| Admin panel | React + Vite | Fast, modern | More JS to ship |
| Admin panel | htmx + Flask | Lightweight | Less interactive |
| Hosting (backend) | Vercel | Node.js native | $$$$ for scale |
| Hosting (backend) | Railway.app | Affordable, simple | Smaller ecosystem |
| Hosting (backend) | DigitalOcean | VM control, cheap | More ops work |
| API polling | Vercel Cron | Serverless, free | Overkill for simple tasks |
| API polling | GitHub Actions | Already integrated | Rate-limited, slow |

---

## Questions for Product Direction

1. **Revenue model**: Is this a hobby, a startup, or internal tool?
2. **Scale**: 1 screen? 100 screens? 1M users?
3. **Data freshness**: Real-time or 5-min updates?
4. **Admin workflow**: JSON files or web UI?
5. **Moderation**: Trust the input, or moderate?
6. **Accessibility**: Who are the viewers? (offices, retail, airports?)

**Current setup works great for**: Personal signage, event displays, hobby projects  
**Needs backend for**: Commercial deployments, real-time sync, user authentication

