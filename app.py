"""
Saboteur Fantasy League — FPL API Proxy
Fetches and serves FPL data for the frontend, bypassing browser CORS restrictions.
Deploy to Railway. Serves two endpoints:
  GET /api/players        → pool of top players per position per club
  GET /api/gameweek/<gw>  → live points for a specific gameweek
"""

import requests
from flask import Flask, jsonify
from flask_cors import CORS
from functools import lru_cache
import time
import logging

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Allow requests from your Netlify frontend

FPL_BASE = "https://fantasy.premierleague.com/api"
HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
}

# Position limits per club (top N by season points)
POS_LIMITS = {"GK": 1, "DEF": 5, "MID": 5, "FWD": 4}
POS_MAP = {1: "GK", 2: "DEF", 3: "MID", 4: "FWD"}

# Cache bootstrap data for 1 hour to avoid hammering FPL
_bootstrap_cache = {"data": None, "fetched_at": 0}
CACHE_TTL = 3600  # seconds


def get_bootstrap():
    """Fetch and cache the FPL bootstrap-static data."""
    now = time.time()
    if _bootstrap_cache["data"] and (now - _bootstrap_cache["fetched_at"]) < CACHE_TTL:
        log.info("Returning cached bootstrap data")
        return _bootstrap_cache["data"]

    log.info("Fetching fresh bootstrap data from FPL API")
    resp = requests.get(f"{FPL_BASE}/bootstrap-static/", headers=HEADERS, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    _bootstrap_cache["data"] = data
    _bootstrap_cache["fetched_at"] = now
    return data


@app.route("/api/players")
def get_players():
    """
    Returns the player pool: top N players per position per club.
    Structure matches what the frontend expects.
    """
    try:
        data = get_bootstrap()

        # Build lookup maps
        team_map = {t["id"]: t["short_name"] for t in data["teams"]}

        # Parse all players
        all_players = []
        for p in data["elements"]:
            pos = POS_MAP.get(p["element_type"])
            if not pos:
                continue
            all_players.append({
                "id":       p["id"],
                "name":     p["web_name"],
                "full":     f"{p['first_name']} {p['second_name']}",
                "team":     team_map.get(p["team"], ""),
                "teamId":   p["team"],
                "pos":      pos,
                "price":    p["now_cost"] / 10,
                "pts":      p["total_points"],
                "ppg":      float(p["points_per_game"] or 0),
                "form":     float(p["form"] or 0),
                "sel":      float(p["selected_by_percent"] or 0),
                "mins":     p["minutes"],
                "gwPts":    p.get("event_points", 0),
            })

        # Top N per position per club
        pool = []
        seen = set()

        # Group by teamId + pos
        from collections import defaultdict
        by_team_pos = defaultdict(list)
        for p in all_players:
            by_team_pos[(p["teamId"], p["pos"])].append(p)

        for (team_id, pos), players in by_team_pos.items():
            limit = POS_LIMITS[pos]
            top = sorted(players, key=lambda p: p["pts"], reverse=True)[:limit]
            for p in top:
                if p["id"] not in seen:
                    seen.add(p["id"])
                    pool.append(p)

        log.info(f"Returning {len(pool)} players in pool")
        return jsonify({"players": pool, "count": len(pool)})

    except requests.exceptions.RequestException as e:
        log.error(f"FPL API error: {e}")
        return jsonify({"error": "Could not reach FPL API", "detail": str(e)}), 502
    except Exception as e:
        log.error(f"Unexpected error: {e}")
        return jsonify({"error": "Server error", "detail": str(e)}), 500


@app.route("/api/gameweek/<int:gw>")
def get_gameweek(gw):
    """
    Returns live points for all players in a given gameweek.
    Returns a dict of {player_id: points} for easy lookup.
    """
    try:
        resp = requests.get(
            f"{FPL_BASE}/event/{gw}/live/",
            headers=HEADERS,
            timeout=10
        )
        resp.raise_for_status()
        data = resp.json()

        # Flatten to {id: total_points}
        points = {}
        for element in data.get("elements", []):
            pid = element["id"]
            pts = element.get("stats", {}).get("total_points", 0)
            points[pid] = pts

        log.info(f"GW{gw}: returning points for {len(points)} players")
        return jsonify({"gameweek": gw, "points": points})

    except requests.exceptions.RequestException as e:
        log.error(f"FPL API error for GW{gw}: {e}")
        return jsonify({"error": "Could not reach FPL API", "detail": str(e)}), 502
    except Exception as e:
        log.error(f"Unexpected error for GW{gw}: {e}")
        return jsonify({"error": "Server error", "detail": str(e)}), 500


@app.route("/api/player/<int:player_id>/history")
def get_player_history(player_id):
    """
    Returns gameweek-by-gameweek points history for a single player.
    Useful for checking past GW scores.
    """
    try:
        resp = requests.get(
            f"{FPL_BASE}/element-summary/{player_id}/",
            headers=HEADERS,
            timeout=10
        )
        resp.raise_for_status()
        data = resp.json()

        history = [
            {
                "gw":   h["round"],
                "pts":  h["total_points"],
                "mins": h["minutes"],
                "goals": h["goals_scored"],
                "assists": h["assists"],
                "cs":   h["clean_sheets"],
            }
            for h in data.get("history", [])
        ]

        return jsonify({"player_id": player_id, "history": history})

    except requests.exceptions.RequestException as e:
        return jsonify({"error": "Could not reach FPL API", "detail": str(e)}), 502
    except Exception as e:
        return jsonify({"error": "Server error", "detail": str(e)}), 500


@app.route("/health")
def health():
    """Health check endpoint — Railway uses this to confirm the app is running."""
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    app.run(debug=True, port=5000)
