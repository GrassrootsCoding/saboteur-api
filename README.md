# Saboteur Fantasy League — Deployment Guide

Two repos, two deploys: the Python API goes to Railway, the HTML frontend goes to Netlify.

---

## Part 1: Deploy the Python API to Railway

### Step 1 — Create a GitHub repo for the API

Create a new repo called `saboteur-api` and push these files into it:
```
saboteur-api/
├── app.py
├── requirements.txt
├── Procfile
└── railway.toml
```

```bash
git init
git add .
git commit -m "Initial API"
git remote add origin https://github.com/YOUR_USERNAME/saboteur-api.git
git push -u origin main
```

### Step 2 — Deploy to Railway

1. Go to https://railway.app and sign up (GitHub login is easiest)
2. Click **New Project → Deploy from GitHub repo**
3. Select your `saboteur-api` repo
4. Railway auto-detects Python via nixpacks — no config needed
5. Click **Deploy**
6. Once deployed, go to **Settings → Networking → Generate Domain**
7. Copy your URL — it'll look like:
   `https://saboteur-api-production.up.railway.app`

### Step 3 — Test your API

Open these URLs in your browser to confirm it works:
```
https://YOUR-RAILWAY-URL.up.railway.app/health
https://YOUR-RAILWAY-URL.up.railway.app/api/players
https://YOUR-RAILWAY-URL.up.railway.app/api/gameweek/1
```

`/health` should return `{"status": "ok"}`
`/api/players` should return a list of ~300 FPL players as JSON

---

## Part 2: Deploy the Frontend to Netlify

### Step 1 — Create a GitHub repo for the frontend

Create a new repo called `saboteur-frontend` and push these files:
```
saboteur-frontend/
├── index.html
└── netlify.toml
```

### Step 2 — Deploy to Netlify

1. Go to https://netlify.com and sign up (GitHub login)
2. Click **Add new site → Import an existing project**
3. Connect GitHub and select `saboteur-frontend`
4. Build settings — leave everything blank (no build command needed)
5. Click **Deploy site**
6. Netlify gives you a URL like `https://saboteur-draft.netlify.app`
   You can rename it under **Site settings → Change site name**

---

## Part 3: Connect Frontend to API

Once both are deployed, open `index.html` in the **Setup** screen.
You'll see an **API Backend URL** field — paste your Railway URL there before starting the draft.

To hardcode it permanently, open `index.html` and change this line near the top of the `<script>`:
```javascript
const API_BASE = window.SABOTEUR_API_URL || 'http://localhost:5000';
```
to:
```javascript
const API_BASE = 'https://your-app.up.railway.app';
```
Then push to GitHub — Netlify redeploys automatically.

---

## Local Testing (before deploying)

To test everything locally:

```bash
# Install dependencies
pip install -r requirements.txt

# Run the API
python app.py
# API now running at http://localhost:5000

# Open index.html directly in your browser
# Leave the API URL field blank — it defaults to localhost:5000
```

---

## API Endpoints Reference

| Endpoint | Description |
|---|---|
| `GET /health` | Health check — confirms API is running |
| `GET /api/players` | Full player pool (~300 players, top N per position per club) |
| `GET /api/gameweek/<gw>` | Live points for all players in gameweek N |
| `GET /api/player/<id>/history` | GW-by-GW points history for a single player |

---

## Costs

- **Railway free tier**: $5 free credit/month — more than enough for a hobby project
- **Netlify free tier**: 100GB bandwidth/month — no issue for a small group app
- Total expected cost: **£0**

---

## Updating the App

Any push to either GitHub repo triggers an automatic redeploy on Railway/Netlify.
No manual steps needed after initial setup.
