# ClawdBot Config Dashboard (Next.js)

Modern web dashboard for ClawdBot configuration and monitoring, deployed to Firebase Hosting.

## Features

- **Dashboard**: System status overview with metrics
- **Config Editor**: Edit OpenClaw gateway configuration
- **Keys Manager**: Manage API keys securely
- **Predictions**: View historical prediction data
- **Trades**: Monitor trade history and PnL
- **Hosting Advisor**: Latency optimization recommendations

## Setup

```bash
cd firebase/web
npm install
```

## Development

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

## Environment Variables

Create `.env.local`:

```
NEXT_PUBLIC_API_URL=https://clawdbot-api-xxxxx-uc.a.run.app
NEXT_PUBLIC_API_KEY=your-api-key
```

## Build

```bash
npm run build
```

Output is in `.next/out/` for static export.

## Deploy to Firebase Hosting

```bash
npm run build
firebase deploy --only hosting
```
