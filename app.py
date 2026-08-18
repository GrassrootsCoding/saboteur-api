"""
Saboteur Fantasy League — FPL API Proxy
Fetches and serves FPL data for the frontend, bypassing browser CORS restrictions.
Deploy to Railway. Serves these endpoints:
  GET /health             → health check
  GET /api/players        → pool of top players per position per club
  GET /api/gameweek/<gw>  → live points for a specific gameweek
  GET /api/player/<id>/history → per-player GW history
"""

import requests
import time
import logging
from flask import Flask, jsonify
from flask_cors import CORS

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

FPL_BASE = "https://fantasy.premierleague.com/api"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-GB,en;q=0.9",
    "Referer": "https://fantasy.premierleague.com/",
}

POS_LIMITS = {"GK": 1, "DEF": 5, "MID": 5, "FWD": 4}
POS_MAP = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}

_bootstrap_cache = {"data": None, "fetched_at": 0}
CACHE_TTL = 3600


def fpl_get(url, timeout=20):
    """GET request to FPL API with 3 retries."""
    last_err = None
    for attempt in range(3):
        try:
            resp = requests.get(url, headers=HEADERS, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            last_err = e
            log.warning(f"FPL request attempt {attempt+1} failed: {e}")
            if attempt < 2:
                time.sleep(3)
    raise last_err


def get_bootstrap():
    """Fetch and cache bootstrap-static data."""
    now = time.time()
    if _bootstrap_cache["data"] and (now - _bootstrap_cache["fetched_at"]) < CACHE_TTL:
        log.info("Returning cached bootstrap data")
        return _bootstrap_cache["data"]
    log.info("Fetching fresh bootstrap data from FPL")
    data = fpl_get(f"{FPL_BASE}/bootstrap-static/")
    _bootstrap_cache["data"] = data
    _bootstrap_cache["fetched_at"] = now
    return data


@app.route("/health")
def health():
    """Health check — does not call FPL so always responds instantly."""
    return jsonify({"status": "ok"})


@app.route("/api/players")
def get_players():
    """Returns the player pool: top N per position per club."""
    try:
        data = get_bootstrap()
        team_map = {t["id"]: t["short_name"] for t in data["teams"]}

        from collections import defaultdict
        by_team_pos = defaultdict(list)
        for p in data["elements"]:
            pos = POS_MAP.get(p["element_type"])
            if not pos:
                continue
            by_team_pos[(p["team"], pos)].append({
                "id":    p["id"],
                "name":  p["web_name"],
                "full":  f"{p['first_name']} {p['second_name']}",
                "team":  team_map.get(p["team"], ""),
                "teamId": p["team"],
                "pos":   pos,
                "price": p["now_cost"] / 10,
                "pts":   p["total_points"],
                "ppg":   float(p["points_per_game"] or 0),
                "form":  float(p["form"] or 0),
                "sel":   float(p["selected_by_percent"] or 0),
                "mins":  p["minutes"],
                "gwPts": p.get("event_points", 0),
            })

        pool = []
        seen = set()
        for (team_id, pos), players in by_team_pos.items():
            limit = POS_LIMITS[pos]
            top = sorted(players, key=lambda p: p["pts"], reverse=True)[:limit]
            for p in top:
                if p["id"] not in seen:
                    seen.add(p["id"])
                    pool.append(p)

        log.info(f"Returning {len(pool)} players")
        return jsonify({"players": pool, "count": len(pool)})

    except Exception as e:
        log.error(f"Error in /api/players: {e}")
        return jsonify({"error": str(e)}), 502


@app.route("/api/gameweek/<int:gw>")
def get_gameweek(gw):
    """Returns live points dict {player_id: points} for a gameweek."""
    try:
        data = fpl_get(f"{FPL_BASE}/event/{gw}/live/")
        points = {
            el["id"]: el.get("stats", {}).get("total_points", 0)
            for el in data.get("elements", [])
        }
        return jsonify({"gameweek": gw, "points": points})
    except Exception as e:
        log.error(f"Error in /api/gameweek/{gw}: {e}")
        return jsonify({"error": str(e)}), 502


@app.route("/api/player/<int:player_id>/history")
def get_player_history(player_id):
    """Returns GW-by-GW points history for a single player."""
    try:
        data = fpl_get(f"{FPL_BASE}/element-summary/{player_id}/")
        history = [
            {
                "gw":      h["round"],
                "pts":     h["total_points"],
                "mins":    h["minutes"],
                "goals":   h["goals_scored"],
                "assists": h["assists"],
                "cs":      h["clean_sheets"],
            }
            for h in data.get("history", [])
        ]
        return jsonify({"player_id": player_id, "history": history})
    except Exception as e:
        log.error(f"Error in /api/player/{player_id}/history: {e}")
        return jsonify({"error": str(e)}), 502


if __name__ == "__main__":
    app.run(debug=True, port=5000)
