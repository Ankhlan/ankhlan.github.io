# Central Bank Reserves: A Mongolian Consciousness Project

## Vision

This is not just a data visualization. This is **art**. This is **political engagement**.

**Statement:** A nation's monetary reserves represent collective wealth and sovereignty. Citizens deserve transparency, real-time visibility, and a voice in how that wealth is stewarded.

**Method:** A continuously-updating circular visualization that treats reserve data as a living, breathing entity—orbiting around a central value, pulsing with the rhythm of national currency flows.

---

## Project Structure

```
2026-01-07-reserves-overview/
├── index.md              # Markdown content + text
├── index.html            # (optional) Pre-rendered HTML version
├── style.css             # ★ SEPARATE CSS (not tufte.css) — standalone design
├── script.js             # ★ Real-time data fetching & animation
├── README.md             # This file
├── data/
│   └── reserves.csv      # Historical source data
├── scripts/
│   └── plot_reserves.py  # (optional) Chart generation
└── figures/
    └── reserves-ex-gold.png  # Static reference chart
```

## Design Principles

### Standalone Aesthetic
- **Not** using tufte.css (the main site stylesheet)
- Custom dark theme with gold/blue/silver accents
- Circular layout inspired by Mongolian cosmology
- Real-time animation and live data feed

### Typography
- **Headers**: Serif (`Noto Serif`) — tradition, authority
- **Body**: Sans-serif (`Noto Sans`) — clarity at distance
- **Data**: Monospace (`Courier New`) — precision, numerical accuracy

### Color Palette
- **Gold** (`#D4AF37`): Wealth, precious metals, Mongolia's mining heritage
- **Silver** (`#C0C0C0`): International cooperation (SDRs, IMF)
- **Blue** (`#1E90FF`): Foreign exchange, global markets, sky
- **Dark** (`#0a0a0a`): Focus, depth, contrast
- **Green** (`#90EE90`): Live indicator, positive engagement
- **Fire** (`#FF6347`): Volatility, urgent metrics

### Animations
- `breathe`: 3s pulse (economy's heartbeat)
- `rotate`: Dashed rings (eternal cycle, Mongolian cosmology)
- `shimmer`: Gold effect (precious reserves)
- `pulse-text`: Center value updates (real-time)
- `blink`: Live indicator (active feed)

## How It Works

### Real-Time Data Flow

1. **Source**: `/data/reserves.json` (hosted on GitHub Pages)
2. **Fetch**: JavaScript polls every 5 seconds
3. **Animate**: Smooth transitions with easing function
4. **Display**: 
   - Center circle: Total reserves
   - 6 segments: FX, Gold, SDRs, Other, Crypto (future), Citizen Engagement
   - Grid cards: Breakdown + change metrics
   - Live indicator: Shows data freshness

### Interactive Elements

- **Click segments**: Show reserve type details
- **Hover cards**: Highlight and zoom effect
- **Responsive**: Auto-adapts to desktop/tablet/mobile
- **Live badge**: Indicates real-time updates

## Technical Stack

- **Frontend**: Vanilla HTML/CSS/JavaScript (no frameworks)
- **Data**: JSON hosted via GitHub Pages
- **Styling**: CSS custom properties (variables), animations, flexbox/grid
- **Updates**: Fetch API with 5-second polling (can upgrade to WebSocket)

## Files Breakdown

| File | Purpose |
|------|---------|
| `index.md` | Markdown content (explanation, references) |
| `index.html` | Pre-rendered HTML (embedding viz directly) |
| `style.css` | **Separate** design system (not tufte.css) |
| `script.js` | Real-time data + animation logic |
| `/data/reserves.json` | Live reserve data |

## Future Enhancements

### Short-term
- Integrate with Bank of Mongolia API (live data)
- Historical chart (30-day trend)
- "Citizen Engagement" metric (linked to poll)
- Multiple languages (Mongolian, English, Mandarin)

### Medium-term
- WebSocket real-time updates
- Mobile voting app (reserve allocation priority)
- Regional comparison (vs. Kazakhstan, Russia, China)
- Explainer videos & podcasts

### Long-term
- Museum installation (large physical displays)
- AI policy recommendations
- Artist residencies (reimagine reserve data)
- Integration with national economic dashboard

## Deployment

```bash
cd c:\source\repos\ankhlan.github.io

# Files already in place:
# - posts/2026-01-07-reserves-overview/index.md
# - posts/2026-01-07-reserves-overview/style.css
# - posts/2026-01-07-reserves-overview/script.js
# - data/reserves.json

git add posts/2026-01-07-reserves-overview/ data/reserves.json
git commit -m "Add reserves consciousness project: standalone CSS, real-time viz, artist statement"
git push
```

**Access**: `https://ankhlan.github.io/posts/2026-01-07-reserves-overview/`

## Philosophy

> A nation's monetary reserves are a commons. Citizens have the right to understand them, question them, and participate in decisions about them. This visualization is an invitation to Mongolian consciousness—to collective responsibility for collective wealth.

The circular design echoes eternal Mongolian cycles: birth, growth, death, rebirth. The real-time feed emphasizes that reserves are not static—they flow, change, respond to global markets and local policy.

Every percentage point represents lives, livelihoods, and national sovereignty.

---

**Created**: 2026-01-08  
**Status**: Live & continuously updating  
**Artist/Developer**: Ankhlan  
**License**: CC BY-SA 4.0  
**For**: Mongolian citizens and global financial consciousness

```bash
python scripts/plot_reserves.py
```
