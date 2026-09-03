"""LiveScore provider used as a fallback for live match data."""
from __future__ import annotations

import logging
import re
import time
from typing import Any, Optional

import requests

logger = logging.getLogger("BetBot.LiveScore")


class LiveScoreProvider:
    BASE_URL = "https://prod-public-api.livescore.com/v1/api/app"

    def __init__(self, session: Optional[requests.Session] = None, timeout: float = 10.0):
        self.session = session or requests.Session()
        self.timeout = timeout
        self.session.headers.update({
            "User-Agent": "LiveScore/5.23.0 (iPhone; iOS 16.5; Scale/3.00)",
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Origin": "https://www.livescore.com",
            "Referer": "https://www.livescore.com/",
        })
        self._blocked_until = 0.0
        self._cache: dict[str, tuple[Any, float]] = {}
        self.cache_ttl = 30.0

    def _blocked(self) -> bool:
        return time.time() < self._blocked_until

    def _cache_get(self, key: str) -> Any:
        cached = self._cache.get(key)
        if cached and time.time() - cached[1] < self.cache_ttl:
            return cached[0]
        return None

    def _cache_set(self, key: str, value: Any) -> None:
        self._cache[key] = (value, time.time())

    def _get_json(self, path: str, params: Optional[dict[str, str]] = None) -> Optional[dict]:
        if self._blocked():
            return None
        try:
            response = self.session.get(f"{self.BASE_URL}{path}", params=params, timeout=self.timeout)
            if response.status_code in (403, 429):
                self._blocked_until = time.time() + 300
                logger.warning("LiveScore blocked/rate-limited: HTTP %s", response.status_code)
                return None
            response.raise_for_status()
            payload = response.json()
            return payload if isinstance(payload, dict) else None
        except (requests.RequestException, ValueError) as exc:
            logger.debug("LiveScore request failed for %s: %s", path, exc)
            return None

    def get_live_matches(self) -> list[dict[str, Any]]:
        cached = self._cache_get("live_matches")
        if cached is not None:
            return cached
        payload = self._get_json("/live/soccer/0.00", {"MD": "1"})
        events: list[dict[str, Any]] = []
        for stage in (payload or {}).get("Stages", []) or []:
            stage_info = {key: stage.get(key) for key in ("Sid", "Snm", "Cnm", "Ccd", "CompN", "CompId")}
            for event in stage.get("Events", []) or []:
                item = dict(event)
                item["Stg"] = stage_info
                events.append(item)
        self._cache_set("live_matches", events)
        return events

    def get_match_details(self, event_id: int | str) -> Optional[dict[str, Any]]:
        key = f"details:{event_id}"
        cached = self._cache_get(key)
        if cached is not None:
            return cached
        payload = self._get_json(f"/detail/soccer/{event_id}")
        if payload:
            self._cache_set(key, payload)
        return payload

    def get_match_stats(self, event_id: int | str) -> Optional[dict[str, Any]]:
        key = f"stats:{event_id}"
        cached = self._cache_get(key)
        if cached is not None:
            return cached
        payload = self._get_json(f"/statistics/soccer/{event_id}")
        if payload:
            self._cache_set(key, payload)
        return payload

    def get_match_odds(self, event_id: int | str) -> Optional[dict[str, float]]:
        payload = self._get_json(f"/odds/soccer/{event_id}")
        return self._parse_odds(payload or {}) if payload else None

    @staticmethod
    def _parse_odds(payload: dict[str, Any]) -> dict[str, float]:
        odds: dict[str, float] = {}
        rows = payload.get("Odds", []) or []
        for row in rows:
            if not isinstance(row, dict):
                continue
            name = str(row.get("Name", "")).lower()
            value = row.get("Value")
            if isinstance(value, (int, float)):
                key = re.sub(r"[^a-z0-9]+", "_", name).strip("_")
                odds[key] = float(value)
                if "under" in name and "0.5" in name and ("ht" in name or "half" in name):
                    odds["under05_ht"] = float(value)
        return odds

    def _extract_stats(self, features: dict[str, Any], payload: dict[str, Any]) -> None:
        mapping = {
            "BallPossession": "possession", "ShotsOn": "sot", "TotalShots": "shots",
            "Corners": "corners", "Fouls": "fouls", "YellowCards": "yellow_cards",
            "RedCards": "red_cards", "Saves": "saves",
        }
        for row in payload.get("Stat", []) or []:
            if not isinstance(row, dict) or row.get("Type") not in mapping:
                continue
            key = mapping[row["Type"]]
            try:
                home = float(row.get("Value1", 0))
                away = float(row.get("Value2", 0))
            except (TypeError, ValueError):
                continue
            features[key] = [home, away]
            features[f"combined_{key}"] = home + away

    def extract_features(self, event_id: int | str) -> dict[str, Any]:
        features: dict[str, Any] = {"provider": "livescore", "timestamp": time.time()}
        details = self.get_match_details(event_id)
        if not details:
            return features
        stats = self.get_match_stats(event_id)
        if stats:
            self._extract_stats(features, stats)
        incidents = details.get("Incidents", []) or []
        features["goals_scored"] = 0
        features["red_cards"] = features.get("combined_red_cards", 0)
        features["yellow_cards"] = features.get("combined_yellow_cards", 0)
        for incident in incidents:
            if not isinstance(incident, dict):
                continue
            incident_type = str(incident.get("Type", "")).lower()
            card = str(incident.get("Card", "")).lower()
            if "goal" in incident_type:
                features["goals_scored"] += 1
            if "red" in card or "red" in incident_type:
                features["red_cards"] += 1
            elif "yellow" in card or "yellow" in incident_type:
                features["yellow_cards"] += 1
        return features

    def get_live_features(self, event_id: int | str) -> dict[str, Any]:
        return self.extract_features(event_id)
