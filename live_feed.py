"""Load and normalize live flight data before passing records to H2O."""

import json
import math
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd


REQUIRED_COLUMNS = (
    "flight_id",
    "scheduled_local",
    "carrier",
    "origin",
    "dest",
    "distance",
    "departure_density_30m",
)

AVIATIONSTACK_URL = "https://api.aviationstack.com/v1/flights"


class LiveFeedError(RuntimeError):
    """A safe, user-facing error raised while retrieving a live feed."""


def _distance_miles(origin: str, dest: str, coordinates: dict[str, tuple[float, float]]) -> float | None:
    """Return great-circle distance between two airports."""
    if origin not in coordinates or dest not in coordinates:
        return None
    lat1, lon1 = coordinates[origin]
    lat2, lon2 = coordinates[dest]
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 3958.8 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def aviationstack_to_feed(payload: dict, airport_locations: pd.DataFrame) -> pd.DataFrame:
    """Convert an Aviationstack response to the model's live-feed schema."""
    if payload.get("error"):
        error = payload["error"]
        raise LiveFeedError(str(error.get("message") or error.get("info") or "Aviationstack trả về lỗi"))
    records = payload.get("data")
    if not isinstance(records, list):
        raise LiveFeedError("Phản hồi Aviationstack không có danh sách data hợp lệ")

    coordinates = {
        str(row.Origin).upper(): (float(row.latitude), float(row.longitude))
        for row in airport_locations.itertuples()
    }
    rows = []
    for item in records:
        departure = item.get("departure") or {}
        arrival = item.get("arrival") or {}
        airline = item.get("airline") or {}
        flight = item.get("flight") or {}
        origin = str(departure.get("iata") or "").upper()
        dest = str(arrival.get("iata") or "").upper()
        distance = _distance_miles(origin, dest, coordinates)
        scheduled = pd.to_datetime(departure.get("scheduled"), errors="coerce")
        flight_id = str(flight.get("iata") or flight.get("icao") or "").upper()
        carrier = str(airline.get("iata") or "").upper()
        if (
            item.get("flight_status") == "cancelled"
            or not flight_id
            or not carrier
            or not origin
            or not dest
            or pd.isna(scheduled)
            or distance is None
        ):
            continue
        rows.append(
            {
                "flight_id": flight_id,
                "scheduled_local": scheduled,
                "carrier": carrier,
                "origin": origin,
                "dest": dest,
                "distance": round(distance, 1),
            }
        )

    if not rows:
        result = pd.DataFrame(columns=REQUIRED_COLUMNS)
        result.attrs["source_count"] = len(records)
        return result
    frame = pd.DataFrame(rows).drop_duplicates("flight_id", keep="last")
    half_hour = frame["scheduled_local"].dt.floor("30min")
    frame["departure_density_30m"] = frame.groupby(["origin", half_hour])["flight_id"].transform("count")
    frame = frame.loc[:, list(REQUIRED_COLUMNS)].sort_values("scheduled_local").reset_index(drop=True)
    frame.attrs["source_count"] = len(records)
    return frame


def fetch_aviationstack_feed(
    api_key: str,
    departure_airport: str,
    airport_locations: pd.DataFrame,
    limit: int = 100,
    timeout: int = 20,
) -> pd.DataFrame:
    """Fetch one current Aviationstack snapshot for a departure airport."""
    if not api_key.strip():
        raise LiveFeedError("Thiếu AVIATIONSTACK_API_KEY")
    airport = departure_airport.strip().upper()
    if len(airport) != 3 or not airport.isalpha():
        raise LiveFeedError("Mã sân bay đi phải là mã IATA gồm 3 chữ cái")
    query = urlencode({"access_key": api_key.strip(), "dep_iata": airport, "limit": limit})
    try:
        with urlopen(f"{AVIATIONSTACK_URL}?{query}", timeout=timeout) as response:
            payload = json.load(response)
    except HTTPError as exc:
        raise LiveFeedError(f"Aviationstack trả về HTTP {exc.code}") from exc
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise LiveFeedError(f"Không đọc được Aviationstack: {exc}") from exc
    return aviationstack_to_feed(payload, airport_locations)


def read_live_feed(path: Path) -> pd.DataFrame:
    """Read a CSV snapshot supplied by an external source; never invent live flights."""
    if not path.exists():
        return pd.DataFrame(columns=REQUIRED_COLUMNS)

    frame = pd.read_csv(path, dtype={"flight_id": str, "carrier": str, "origin": str, "dest": str})
    missing = set(REQUIRED_COLUMNS) - set(frame.columns)
    if missing:
        raise ValueError(f"CSV thiếu cột: {', '.join(sorted(missing))}")
    frame = frame.loc[:, list(REQUIRED_COLUMNS)].copy()
    frame["scheduled_local"] = pd.to_datetime(frame["scheduled_local"], errors="coerce")
    if frame["scheduled_local"].isna().any():
        raise ValueError("scheduled_local phải có dạng YYYY-MM-DD HH:MM")
    for column in ("distance", "departure_density_30m"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    if frame[["distance", "departure_density_30m"]].isna().any().any():
        raise ValueError("distance và departure_density_30m phải là số")
    if (frame["distance"] <= 0).any() or (frame["departure_density_30m"] < 1).any():
        raise ValueError("distance phải > 0 và departure_density_30m phải >= 1")
    for column in ("flight_id", "carrier", "origin", "dest"):
        frame[column] = frame[column].str.strip().str.upper()
        if frame[column].isna().any() or frame[column].eq("").any():
            raise ValueError(f"{column} không được để trống")
    if frame["flight_id"].duplicated().any():
        raise ValueError("flight_id phải duy nhất trong mỗi bản CSV")
    return frame.sort_values("scheduled_local").reset_index(drop=True)


def to_prediction_kwargs(row: pd.Series) -> dict:
    timestamp = row["scheduled_local"]
    return {
        "month": int(timestamp.month),
        "day": int(timestamp.day),
        "day_of_week": int(timestamp.dayofweek + 1),
        "dep_hour": int(timestamp.hour),
        "dep_minute": int(timestamp.minute),
        "carrier": str(row["carrier"]),
        "origin": str(row["origin"]),
        "dest": str(row["dest"]),
        "distance": float(row["distance"]),
        "departure_density": float(row["departure_density_30m"]),
    }
