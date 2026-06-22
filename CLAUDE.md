# chart-generator Development Guidelines

Last updated: 2026-06-22

## Was ist das?

Ein Human-Design-Chart-Generator. Nutzer geben Name, Geburtsdatum, -zeit und -ort ein und erhalten ein vollständiges HD-Chart (Typ, Autorität, Profil, Zentren, Gates, Kanäle, Inkarnationskreuz).

**Frontend:** Next.js auf Vercel → `https://chart-generator.vercel.app` (o.ä.)
**Backend:** FastAPI auf Railway → `https://chart-generator-production-64fd.up.railway.app`

---

## Trunk-Based Development

1. `main` ist die einzige langlebige Branch
2. Kurzlebige Feature-Branches (max. 1-2 Tage)
3. Kleine, häufige Commits
4. PR → Squash-Merge → `main`

```bash
git checkout main && git pull
git checkout -b feature/kurze-beschreibung
# ... ändern, committen ...
git push -u origin feature/kurze-beschreibung
gh pr create --title "feat: beschreibung"
gh pr merge --squash
git checkout main && git pull && git branch -d feature/kurze-beschreibung
```

Branch-Präfixe: `feature/`, `fix/`, `docs/`, `refactor/`

---

## Projektstruktur

```text
backend/
  src/
    main.py                          # FastAPI-App, alle Routen, Geocoding-Pipeline
    api/routes/chart.py              # /api/chart Route (Hilfsfunktionen)
    models/
      chart.py                       # ChartRequest, ChartResponse und alle Pydantic-Modelle
      celestial.py                   # CelestialBody Enum (Sonne, Mond, Planeten, Knoten)
      ephemeris.py / ephemeris_storage.py
      lead_email_db.py               # E-Mail-Lead-Datenmodell
    services/
      geocoding_service.py           # Nominatim + TimezoneFinder; Photon-Koordinaten-Fallback
      validation_service.py
      normalization_service.py
      calculation/
        position_calculator.py       # Ekliptik-Länge → Gate/Linie für alle Planeten
        design_time.py               # Design-Zeitpunkt: 88° vor der Sonne zurück
        bodygraph_calculator.py      # Typ, Autorität, Profil, Zentren, Kanäle etc.
        gate_line_mapper.py
      ephemeris/
        swiss_ephemeris.py           # Haupt-Ephemeride (pyswisseph)
        source_factory.py            # Gibt SwissEphemerisSource zurück
        base.py / nasa_jpl.py / openastro_api.py  # Alternativen / Fallbacks
    handlers/email_handler.py
    database.py
  venv/                              # Python venv (Python 3.9.6 lokal, 3.11 auf Railway)
  data/ephemeris/                    # Swiss Ephemeris Datendateien
  tests/

frontend/
  app/
    layout.tsx                       # Root Layout
    page.tsx                         # Hauptseite (Form + Chart-Anzeige)
  components/
    ChartForm.tsx                    # Formular inkl. Photon-Autocomplete für Geburtsort
    ChartDisplay.tsx                 # Chart-Ergebnis-Wrapper
    Bodygraph.tsx                    # SVG-Bodygraph-Zeichnung
    EmailCaptureSection.tsx
    sections/                        # TypeSection, AuthoritySection, ProfileSection,
                                     # CentersSection, ChannelsSection, GatesSection,
                                     # ImpulseSection, IncarnationCrossSection
  services/api.ts                    # fetchChart() und APIError
  types/chart.ts                     # TypeScript-Interfaces (spiegeln Pydantic-Modelle)
  utils/constants.ts                 # Labels, Platzhalter, Fehlermeldungen

.claude/
  skills/chart-generator-context/   # Projekt-Skill mit Key-Learnings (Geocoding, nvm etc.)
  launch.json                        # Preview-Server-Config für Claude Code
  agents/                            # Spezialisierte Agenten-Definitionen
```

---

## Dev Setup & Befehle

### Backend

```bash
cd backend

# Venv aktivieren (lokal Python 3.9.6)
source venv/bin/activate

# Oder direkt ohne Aktivierung:
venv/bin/uvicorn src.main:app --port 5001 --reload

# Tests
venv/bin/pytest

# Lint
venv/bin/ruff check .
```

### Frontend

> **Wichtig:** node/npm sind via **nvm** installiert, nicht im System-PATH.
> Im Claude-Bash-Tool immer vollen Pfad oder PATH-Prepend verwenden:

```bash
# PATH setzen (einmalig pro Session)
export PATH="$HOME/.nvm/versions/node/v24.17.0/bin:$PATH"

cd frontend
npm install
npm run dev          # Dev-Server auf :3000
npm run build        # Produktions-Build
npm run lint         # ESLint + TypeScript-Check
npm run test:e2e     # Playwright E2E-Tests
```

Node/npm-Pfade: `~/.nvm/versions/node/v24.17.0/bin/{node,npm,npx}`

### Beide Server gleichzeitig

```bash
# Terminal 1 – Backend
cd backend && venv/bin/uvicorn src.main:app --port 5001 --reload

# Terminal 2 – Frontend
cd frontend && PATH="$HOME/.nvm/versions/node/v24.17.0/bin:$PATH" npm run dev
```

Frontend proxied `/api/*` → `http://localhost:5001/api/*` (via `next.config.js`).

---

## Geocoding & Standort-Logik

Die Geburtsort-Pipeline:

```
User-Input (Ortsname)
  → [optional] Photon-Autocomplete (Frontend) → lat/lng mitschicken
  → ChartRequest { birthPlace, latitude?, longitude? }
  → Backend main.py:
      if latitude+longitude vorhanden:
          get_timezone_from_coords(lat, lng)   # nur TimezoneFinder, kein Netzwerk
      else:
          get_location_data(birthPlace)        # Nominatim (langsamer, mehrdeutig)
  → pytz.timezone(tz_str).localize(birth_datetime)
  → birth_datetime_utc → Ephemeris
```

**Nur die Zeitzone zählt für das HD-Chart.** Koordinaten werden nur genutzt, um die Zeitzone zu ermitteln — die Ephemeride rechnet vom Erdmittelpunkt, nicht vom Geburtsort.

**Das Siegen-Problem:** Bare Stadtnamen (z.B. `"Siegen"`) können durch Nominatim falsch aufgelöst werden (Siegen, Frankreich statt NRW). Deshalb gibt es das Photon-Autocomplete im Formular, das Land und Bundesland anzeigt und die Koordinaten direkt mitliefert.

**Photon API:** `https://photon.komoot.io/api/?q=...&limit=8&lang=de`
- Filter: `osm_key === "place"` (keine Bahnhöfe, Straßen)
- Koordinaten-Reihenfolge: **[longitude, latitude]** (GeoJSON)

---

## Technologien

| Bereich | Stack |
|---|---|
| Backend | Python 3.11 (Railway) / 3.9 (lokal), FastAPI 0.115, pyswisseph |
| Geocoding | geopy (Nominatim), TimezoneFinder, Photon (Komoot) |
| Frontend | Next.js (App Router), TypeScript, React, Tailwind CSS |
| Testing | pytest (Backend), Playwright (E2E) |
| Deploy | Vercel (Frontend), Railway (Backend) |
| Rate Limiting | slowapi (10 req/min auf `/api/hd-chart`) |
| E-Mail | E-Mail-Lead-Capture mit SQLite-Backend |

---

## Code Style

- Python: PEP 8, Type Hints, ruff
- TypeScript: Strict Mode, ESLint + Prettier
- Commits: Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`)

---

## Deployment

- **Frontend**: Vercel, auto-deploy bei Push auf `main`
- **Backend**: Railway — `https://chart-generator-production-64fd.up.railway.app`
  - Konfiguration: `railway.json`, `Procfile`, `Dockerfile`
  - Ephemeris-Datendateien müssen im Deploy enthalten sein (`backend/data/ephemeris/`)
