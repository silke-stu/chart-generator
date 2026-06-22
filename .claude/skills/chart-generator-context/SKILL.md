---
name: chart-generator-context
description: >
  Key technical context for the chart-generator project — load this when working on geocoding,
  birth place input, location handling, Photon autocomplete, the ChartForm component, or
  node/npm/frontend tooling. Automatically apply this knowledge to avoid known pitfalls.
  Trigger on: geocoding, birthPlace, Photon, Nominatim, Siegen problem, npm/node not found,
  nvm, ChartForm, timezone, coordinates, autocomplete.
---

# chart-generator: Key Technical Context

## Geocoding Architecture

The birth place goes through this pipeline:

```
User input (city name)
  → GeocodingService (Nominatim via geopy)
  → lat, lng, timezone_str (via TimezoneFinder)
  → pytz.localize(birth_datetime_local)
  → birth_datetime_utc
  → Ephemeris / position calculation
```

**Only the timezone matters for the HD chart calculation.** Latitude and longitude are retrieved solely to look up the timezone — they are not passed to the ephemeris engine. The ephemeris calculates planetary positions from Earth's center, not from the birth location.

## The Siegen Problem (and its solution)

Bare city names fed to Nominatim (or Photon) can resolve to the wrong country.

**Example:** `"Siegen"` → Nominatim returns Siegen, Alsace, France (lat=48.95, lng=8.04, `Europe/Paris`) instead of Siegen, NRW, Germany (lat=50.87, lng=8.02, `Europe/Berlin`). A wrong timezone means a wrong UTC birth time and therefore a wrong chart.

**Solution implemented:** Photon autocomplete in `frontend/components/ChartForm.tsx`
- As the user types, suggestions are fetched from `https://photon.komoot.io/api/`
- The user picks the unambiguous result (e.g. "Siegen, Nordrhein-Westfalen, Deutschland")
- The exact `latitude` and `longitude` from Photon are sent to the backend
- The backend (`backend/src/main.py`) checks: if `latitude`/`longitude` are present in the request, skip Nominatim entirely and call `GeocodingService.get_timezone_from_coords(lat, lng)` directly

## Photon API Details

Public endpoint (free, reasonable use): `https://photon.komoot.io/api/`

```
GET https://photon.komoot.io/api/?q=Siegen&limit=8&lang=de
```

Key response details:
- Coordinates are `[longitude, latitude]` — **longitude first** (GeoJSON order)
- Filter by `feature.properties.osm_key === "place"` to get cities/towns/villages only (excludes railway stations, streets, buildings)
- Useful fields: `name`, `state`, `country`, `countrycode`, `osm_key`

```ts
// How to build the display label:
const { name, state, country } = feature.properties;
const label = [name, state, country].filter(Boolean).join(", ");
const [lng, lat] = feature.geometry.coordinates; // note: lng first!
```

## Backend: Coordinates vs. Nominatim

`ChartRequest` (Pydantic model in `backend/src/models/chart.py`) accepts optional coords:
```python
latitude: Optional[float] = Field(None, ge=-90, le=90)
longitude: Optional[float] = Field(None, ge=-180, le=180)
```

In `backend/src/main.py`, the geocoding step:
```python
if chart_request.latitude is not None and chart_request.longitude is not None:
    # Fast path: coords from Photon, just look up timezone
    tz_str = geocoding_service.get_timezone_from_coords(lat, lng)
else:
    # Fallback: full Nominatim geocode (slower, potentially ambiguous)
    lat, lng, tz_str = geocoding_service.get_location_data(chart_request.birthPlace)
```

## node / npm / nvm Paths

Node and npm are installed via **nvm**, not Homebrew or system packages.

- **node:** `~/.nvm/versions/node/v24.17.0/bin/node`
- **npm:** `~/.nvm/versions/node/v24.17.0/bin/npm`
- **npx:** `~/.nvm/versions/node/v24.17.0/bin/npx`
- nvm is configured in `~/.zprofile`, which the Bash tool does **not** source

The Bash tool will report `npm not found` / `node not found` unless you prepend the path:

```bash
# Option A: prepend to PATH
PATH="$HOME/.nvm/versions/node/v24.17.0/bin:$PATH" npm run dev

# Option B: full path
/Users/silkina/.nvm/versions/node/v24.17.0/bin/npm run dev
```

For `.claude/launch.json`, `runtimeExecutable` must be the full absolute path and `cwd` must be `"frontend"` (the package.json is in the frontend subdirectory, not the repo root).

## Frontend Dev Setup

```bash
# Backend (already has a venv at backend/venv/)
cd backend && venv/bin/uvicorn src.main:app --port 5001 --reload

# Frontend
PATH="$HOME/.nvm/versions/node/v24.17.0/bin:$PATH" npm run dev  # runs on :3000
```

Backend proxied via Next.js rewrites: `/api/*` → `http://localhost:5001/api/*`
