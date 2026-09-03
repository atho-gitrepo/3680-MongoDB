"""FotMob live-data provider with API + HTML/Next-data fallback.

FotMob is used as the preferred live provider because the current SofaScore and
LiveScore endpoints may return IP blocks (403/429) for hosted workers.

The provider is deliberately read-only and rate-limited. It uses the public
FotMob web endpoints; no login or private credential is required.
"""
from __future__ import annotations

import json
import logging
import random
import re
import time
from datetime import datetime, timezone
from typing import Any, Optional
from urllib.parse import urljoin

import requests

logger = logging.getLogger("BetBot.FotMob")

BASE = "https://www.fotmob.com"
MATCHES_URLS = (f"{BASE}/api/data/matches", f"{BASE}/api/matches")
DETAILS_URLS = (f"{BASE}/api/data/matchDetails", f"{BASE}/api/matchDetails")


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _score_pair(score: Any) -> tuple[int, int]:
    if isinstance(score, dict):
        return _safe_int(score.get("home")), _safe_int(score.get("away"))
    if isinstance(score, str):
        m = re.search(r"(\d+)\s*[-:]\s*(\d+)", score)
        if m:
            return int(m.group(1)), int(m.group(2))
    return 0, 0


def _parse_minute(status: dict[str, Any], match: dict[str, Any]) -> Optional[int]:
    # Some FotMob payloads expose liveTime/minutesPlayed/currentMinute.
    for obj in (status, match):
        for key in ("liveTime", "minutesPlayed", "currentMinute", "minute"):
            value = obj.get(key) if isinstance(obj, dict) else None
            if isinstance(value, dict):
                value = value.get("minute") or value.get("current")
            if isinstance(value, (int, float)):
                return max(0, int(value))
            if isinstance(value, str):
                m = re.search(r"(\d+)", value)
                if m:
                    return int(m.group(1))

    utc = status.get("utcTime") or match.get("utcTime")
    if utc and status.get("started") and not status.get("finished"):
        try:
            ts = datetime.fromisoformat(str(utc).replace("Z", "+00:00")).timestamp()
            return max(0, int((time.time() - ts) / 60))
        except (ValueError, TypeError, OverflowError):
            pass
    return None


class FotMobProvider:
    def __init__(self, session: Optional[requests.Session] = None, timeout: float = 10.0):
        self.session = session or requests.Session()
        self.timeout = timeout
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/151.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": f"{BASE}/",
            "Origin": BASE,
            "Cache-Control": "no-cache",
        })
        self.last_request = 0.0
        self.min_interval = 0.35
        self.api_failures = 0
        self.page_failures = 0

    def _throttle(self) -> None:
        wait = self.min_interval - (time.monotonic() - self.last_request)
        if wait > 0:
            time.sleep(wait)

    def _get(self, url: str, params: Optional[dict[str, Any]] = None,
             accept_json: bool = True, retries: int = 2) -> Optional[requests.Response]:
        for attempt in range(retries):
            try:
                self._throttle()
                response = self.session.get(url, params=params, timeout=self.timeout)
                self.last_request = time.monotonic()
                if response.status_code in (403, 429):
                    logger.warning("FotMob blocked/rate-limited: HTTP %s", response.status_code)
                    if attempt + 1 < retries:
                        time.sleep((1.2 * (attempt + 1)) + random.uniform(0.1, 0.5))
                        continue
                    return None
                response.raise_for_status()
                if accept_json and "json" not in response.headers.get("content-type", "").lower():
                    # FotMob occasionally serves JSON with a text content type.
                    return response
                return response
            except requests.RequestException as exc:
                logger.warning("FotMob request failed (%s/%s): %s", attempt + 1, retries, exc)
                if attempt + 1 < retries:
                    time.sleep((0.8 * (attempt + 1)) + random.uniform(0.1, 0.4))
        return None

    def get_matches(self, date_yyyymmdd: str) -> list[dict[str, Any]]:
        """Return all matches for one calendar date, flattened from leagues."""
        if re.fullmatch(r"\d{8}", date_yyyymmdd):
            date_yyyymmdd = f"{date_yyyymmdd[:4]}-{date_yyyymmdd[4:6]}-{date_yyyymmdd[6:]}"
        response = None
        for endpoint in MATCHES_URLS:
            response = self._get(endpoint, {"date": date_yyyymmdd})
            if response is not None:
                break
        if response is None:
            self.api_failures += 1
            return []
        try:
            payload = response.json()
        except ValueError:
            self.api_failures += 1
            return []

        result: list[dict[str, Any]] = []
        for league in payload.get("leagues", []) or []:
            league_name = league.get("name") or league.get("league", {}).get("name") or "Unknown League"
            country = league.get("ccode") or league.get("ccode3") or league.get("country") or "World"
            for match in league.get("matches", []) or []:
                if not isinstance(match, dict):
                    continue
                item = dict(match)
                item["_fotmob_league"] = league_name
                item["_fotmob_country"] = country
                result.append(item)
        return result

    def get_live_matches(self, date_yyyymmdd: Optional[str] = None) -> list[dict[str, Any]]:
        if date_yyyymmdd is None:
            date_yyyymmdd = datetime.now().strftime("%Y%m%d")
        matches = self.get_matches(date_yyyymmdd)
        live: list[dict[str, Any]] = []
        for match in matches:
            status = match.get("status") or {}
            if status.get("started") and not status.get("finished") and not status.get("cancelled"):
                live.append(match)
        return live

    def _extract_next_data(self, html: str) -> Optional[dict[str, Any]]:
        # Next.js commonly embeds a JSON script. Handle both normal and escaped
        # script tags without depending on a particular page layout.
        patterns = [
            r'<script[^>]+id=["\']__NEXT_DATA__["\'][^>]*>(.*?)</script>',
            r'<script[^>]+type=["\']application/json["\'][^>]*>(.*?)</script>',
        ]
        for pattern in patterns:
            m = re.search(pattern, html, re.S | re.I)
            if not m:
                continue
            try:
                return json.loads(m.group(1).strip())
            except Exception:
                continue
        return None

    def get_match_details(self, match_id: int | str) -> Optional[dict[str, Any]]:
        """Fetch detailed match data. API is primary; page JSON is fallback."""
        for endpoint in DETAILS_URLS:
            response = self._get(endpoint, {"matchId": str(match_id)})
            if response is not None:
                try:
                    payload = response.json()
                    if isinstance(payload, dict) and payload:
                        return payload
                except ValueError:
                    pass
        self.api_failures += 1

        # A page request is useful when the JSON route is blocked/changed.
        page_url = f"{BASE}/matches/-/{match_id}"
        response = self._get(page_url, accept_json=False)
        if response is None:
            self.page_failures += 1
            return None
        data = self._extract_next_data(response.text)
        if not data:
            self.page_failures += 1
            return None
        # Different page builds put the hydrated match object in different
        # locations. Return the closest useful subtree.
        props = data.get("props", {}).get("pageProps", {}) if isinstance(data, dict) else {}
        for key in ("match", "matchDetails", "data"):
            if isinstance(props.get(key), dict):
                return props[key]
        return data

    def normalize_event(self, match: dict[str, Any]) -> dict[str, Any]:
        status = match.get("status") or {}
        home = match.get("home") or {}
        away = match.get("away") or {}
        hs, aws = _score_pair(status.get("scoreStr"))
        if "score" in home:
            hs = _safe_int(home.get("score"), hs)
        if "score" in away:
            aws = _safe_int(away.get("score"), aws)
        minute = _parse_minute(status, match)
        started = bool(status.get("started"))
        finished = bool(status.get("finished"))
        if finished:
            desc = "FT"
        elif started:
            desc = str(minute if minute is not None else 0)
        else:
            desc = "NS"
        utc_time = status.get("utcTime")
        start_ts = 0
        if utc_time:
            try:
                start_ts = int(datetime.fromisoformat(str(utc_time).replace("Z", "+00:00")).timestamp())
            except (ValueError, TypeError):
                start_ts = 0
        return {
            "id": _safe_int(match.get("id")),
            "startTimestamp": start_ts,
            "slug": f"{home.get('name', 'home')}-vs-{away.get('name', 'away')}",
            "homeTeam": {"id": home.get("id"), "name": home.get("name", "Unknown")},
            "awayTeam": {"id": away.get("id"), "name": away.get("name", "Unknown")},
            "homeScore": {"current": hs},
            "awayScore": {"current": aws},
            "status": {"description": desc},
            "tournament": {
                "id": match.get("leagueId") or match.get("tournamentId"),
                "name": match.get("_fotmob_league", "Unknown League"),
                "category": {"name": match.get("_fotmob_country", "World"), "slug": str(match.get("_fotmob_country", "world")).lower()},
            },
            "_provider": "fotmob",
            "_raw": match,
        }

    @staticmethod
    def extract_features(details: dict[str, Any]) -> dict[str, Any]:
        """Best-effort extraction of live xG/shot/corner/chance/card features."""
        features: dict[str, Any] = {"provider": "fotmob"}
        # Match-detail API commonly nests data under content.*
        content = details.get("content", details) if isinstance(details, dict) else {}
        stats_root = content.get("stats", {}) if isinstance(content, dict) else {}
        periods = stats_root.get("Periods", {}) if isinstance(stats_root, dict) else {}
        all_period = periods.get("All", {}) if isinstance(periods, dict) else {}
        stat_rows = all_period.get("stats", []) if isinstance(all_period, dict) else []

        def walk_stats(rows: Any):
            if isinstance(rows, list):
                for row in rows:
                    if isinstance(row, dict):
                        yield row
                        yield from walk_stats(row.get("stats"))
                        yield from walk_stats(row.get("subStats"))
            elif isinstance(rows, dict):
                for v in rows.values():
                    yield from walk_stats(v)

        def normalize_key(k: str) -> str:
            return re.sub(r"[^a-z0-9]", "_", str(k).lower()).strip("_")

        for row in walk_stats(stat_rows):
            key = normalize_key(row.get("key") or row.get("title") or row.get("name") or "")
            vals = row.get("stats")
            if vals is None:
                vals = row.get("value")
            if isinstance(vals, list) and len(vals) >= 2:
                features.setdefault(key, [_safe_float(vals[0]), _safe_float(vals[1])])
            elif vals is not None:
                features.setdefault(key, vals)

        shotmap = content.get("shotmap", {}) if isinstance(content, dict) else {}
        shots = shotmap.get("shots", []) if isinstance(shotmap, dict) else []
        features["shots_total"] = len(shots) if isinstance(shots, list) else 0
        features["shots_on_target"] = 0
        features["xg_from_shots"] = 0.0
        if isinstance(shots, list):
            for shot in shots:
                if not isinstance(shot, dict):
                    continue
                xg = _safe_float(shot.get("expectedGoals") or shot.get("xg"))
                if xg is not None:
                    features["xg_from_shots"] += xg
                result = str(shot.get("shotType") or shot.get("result") or "").lower()
                if any(x in result for x in ("goal", "on target", "save")):
                    features["shots_on_target"] += 1

        # Extract incident counts; red cards are especially important for an
        # Under strategy because a dismissal can materially change goal hazard.
        incidents = content.get("matchFacts", {}).get("events", []) if isinstance(content, dict) else []
        if not incidents and isinstance(content.get("events"), list):
            incidents = content.get("events")
        red_cards = 0
        first_half_goals = 0
        for incident in incidents or []:
            if not isinstance(incident, dict):
                continue
            typ = str(incident.get("type") or incident.get("incidentType") or "").lower()
            card = str(incident.get("card") or incident.get("incidentClass") or "").lower()
            if "red" in typ or "red" in card:
                red_cards += 1
            if "goal" in typ and not ("miss" in typ):
                first_half_goals += 1
        features["red_cards"] = red_cards
        features["incident_goals"] = first_half_goals

        # Common key aliases used by different FotMob builds.
        aliases = {
            "expected_goals": "xg",
            "expected_goals_on_target": "xgot",
            "total_shots": "shots",
            "shots_on_target": "sot",
            "corners": "corners",
            "big_chances": "big_chances",
            "dangerous_attacks": "dangerous_attacks",
            "possession": "possession",
        }
        for source, target in aliases.items():
            if source in features and target not in features:
                features[target] = features[source]

        # Produce combined totals where values are [home, away].
        def pair_total(key: str) -> Optional[float]:
            value = features.get(key)
            if isinstance(value, list) and len(value) >= 2:
                a, b = _safe_float(value[0]), _safe_float(value[1])
                if a is not None and b is not None:
                    return a + b
            return _safe_float(value)

        for key in ("xg", "xgot", "shots", "sot", "corners", "big_chances", "dangerous_attacks"):
            total = pair_total(key)
            if total is not None:
                features[f"combined_{key}"] = total
        return features
