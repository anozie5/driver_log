# 🚚 Anozie's TruckLog — Electronic Driver Log System

A full-stack ELD (Electronic Logging Device) platform for FMCSA-regulated property-carrying truck drivers. Replaces paper "Drivers Daily Log" forms with a digital system that enforces HOS rules, auto-syncs activity totals, manages co-driver workflows, plans multi-day trips, and gives fleet managers real-time visibility into all driver logs.

---

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Quick Start](#quick-start)
  - [Backend](#backend-setup)
  - [Frontend](#frontend-setup)
- [Environment Variables](#environment-variables)
- [API Overview](#api-overview)
- [HOS Rules Implemented](#hos-rules-implemented)
- [Co-Driver Workflow](#co-driver-workflow)
- [Trip Planning Pipeline](#trip-planning-pipeline)
- [Automatic Totals Sync](#automatic-totals-sync)
- [Running Tests](#running-tests)
- [User Roles](#user-roles)
- [Design System](#design-system)
- [Frontend Architecture](#frontend-architecture)

---

## Features

### For Drivers

- **Daily Log Management** — Create electronic daily logs mirroring the paper ELD form, with a 24-hour SVG activity grid
- **Activity Segments** — Add activity entries with 15-minute boundary enforcement and automatic overlap prevention
- **Automatic Hour Totals** — Driving, on-duty, off-duty, and sleeper hours update instantly via Django signals whenever an activity changes
- **Co-Driver Workflow** — Fill your own log, flag yourself as co-driver, select the main driver's log, and submit for their approval
- **Trip Planner** — Enter current location, pickup, and dropoff; the system geocodes the route, applies all FMCSA HOS rules, and generates complete ELD logs automatically

### For Managers

- **Driver Overview** — All drivers with total log counts in a master list
- **Period Filtering** — Filter any driver's logs by today, this week, this month, this year, or specific date/week/month
- **Full Log Detail** — Open any driver's log with the 24-hour SVG activity grid and all individual segments
- **Read-only Access** — Managers view but cannot modify driver logs

### System

- **JWT Authentication** — Secure login with access + refresh tokens
- **Role Enforcement** — Driver and Manager roles are mutually exclusive, enforced at the API layer
- **Signup Code Gate** — Registration requires a server-side signup code
- **Password Security** — Complexity validation, common password rejection, Django AUTH_PASSWORD_VALIDATORS

---

## Tech Stack

| Layer             | Technology                               |
| ----------------- | ---------------------------------------- |
| Backend framework | Django 4.x + Django REST Framework       |
| Auth              | djangorestframework-simplejwt (JWT)      |
| Database          | PostgreSQL                               |
| Map / Routing API | OpenRouteService (ORS) — free tier       |
| Frontend          | React 18 (functional components + hooks) |
| Bundler           | Vite                                     |
| Fonts             | Syne + JetBrains Mono (Google Fonts)     |
| Styling           | Single CSS file (src/styles/global.css)  |
| Tests             | pytest (HOS engine — no DB required)     |

---

## Project Structure

```
trucklog/
├── backend/
│   ├── backend/                  Django project (settings, root urls)
│   ├── authApi/                  User model, JWT auth, profile, password/email
│   ├── logApi/                   DayLog, ActLog, co-driver workflow, manager views
│   │   ├── models.py
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── utils.py              Business logic + totals recompute
│   │   ├── signals.py            Auto-sync totals on ActLog save/delete
│   │   ├── exceptions.py
│   │   └── urls.py
│   └── tripApi/                  Trip planning, HOS engine, ELD log generation
│       ├── models.py
│       ├── hos.py                Pure-Python FMCSA HOS rules engine
│       ├── planner.py            Geocoding + routing + HOS → ELD log builder
│       ├── serializers.py
│       ├── views.py
│       ├── urls.py
│       └── tests/
│           └── test_hos.py       22 unit tests (no DB required)
│
└── frontend/
    └── src/
        ├── main.jsx              Entry point
        ├── App.jsx               Shell: auth gate · sidebar · topbar · page router
        ├── styles/
        │   └── global.css        All CSS: design tokens, layout, components
        ├── api/
        │   └── client.js         Token helpers + fetch wrapper + all API calls
        ├── hooks/
        │   └── utils.js          fmtDate · fmtTime · fmtHours · errorMsg · useAsync
        ├── components/
        │   ├── Icons.jsx          Inline SVG icon set
        │   ├── Modal.jsx          Reusable modal wrapper
        │   └── ActivityGrid.jsx   SVG 24-hour ELD graph-line component
        └── pages/
            ├── auth/AuthPage.jsx
            ├── logs/LogsPage.jsx      + LogDetailModal, CreateLogModal, AddActModal
            ├── codriver/CoDriverPage.jsx
            ├── trips/TripPage.jsx     + TripDetail, PlanTripModal
            ├── manager/ManagerPage.jsx
            └── profile/ProfilePage.jsx
```

---

## Quick Start

### Backend Setup

**1. Clone and create virtualenv**

```bash
git clone https://github.com/your-org/trucklog.git
cd trucklog/backend
python -m venv venv && source venv/bin/activate
```

**2. Install dependencies**

```bash
pip install django djangorestframework djangorestframework-simplejwt \
            psycopg2-binary django-cors-headers requests
```

**3. Configure settings.py**

```python
INSTALLED_APPS = [
    ...
    'corsheaders',
    'rest_framework',
    'rest_framework_simplejwt',
    'authApi',
    'logApi.apps.LogApiConfig',   # must use AppConfig (wires signals)
    'tripApi.apps.TripApiConfig',
]

AUTH_USER_MODEL = 'authApi.User'

REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
}

MIDDLEWARE = ['corsheaders.middleware.CorsMiddleware', ...other middleware...]
CORS_ALLOWED_ORIGINS = ['http://localhost:5173']

import os
code        = os.environ.get('SIGNUP_CODE', 'changeme')
ORS_API_KEY = os.environ.get('ORS_API_KEY', '')
```

**4. Run migrations and start**

```bash
python manage.py makemigrations authApi logApi tripApi
python manage.py migrate
python manage.py runserver
```

---

### Frontend Setup

**1. Scaffold with Vite**

```bash
npm create vite@latest trucklog-frontend -- --template react
cd trucklog-frontend
```

**2. Replace src/**

Copy the provided `frontend/src/` directory over the generated `src/`.

**3. Create .env**

```
VITE_API_URL=http://localhost:8000
```

**4. Start dev server**

```bash
npm run dev   # → http://localhost:5173
```

---

## Environment Variables

### Backend

| Variable       | Required | Description                                                                                          |
| -------------- | -------- | ---------------------------------------------------------------------------------------------------- |
| `SECRET_KEY`   | Yes      | Django secret key                                                                                    |
| `DATABASE_URL` | Yes      | PostgreSQL connection string                                                                         |
| `SIGNUP_CODE`  | Yes      | Registration gate code                                                                               |
| `ORS_API_KEY`  | Yes      | OpenRouteService API key (free at [openrouteservice.org](https://openrouteservice.org/dev/#/signup)) |
| `DEBUG`        | No       | `True` for dev, `False` for production                                                               |

### Frontend

| Variable       | Default                 | Description          |
| -------------- | ----------------------- | -------------------- |
| `VITE_API_URL` | `http://localhost:8000` | Backend API base URL |

---

## API Overview

All endpoints except `/auth/signup/` and `/auth/login/` require:

```
Authorization: Bearer <access_token>
```

### Auth `/auth/`

| Method | Path                    | Description                     |
| ------ | ----------------------- | ------------------------------- |
| POST   | `/auth/signup/`         | Register                        |
| POST   | `/auth/login/`          | Login → access + refresh tokens |
| GET    | `/auth/profile/`        | Get profile                     |
| PATCH  | `/auth/profile/`        | Update profile                  |
| POST   | `/auth/password-reset/` | Change password                 |
| POST   | `/auth/change-email/`   | Change email                    |

### Daily Logs `/log/`

| Method | Path                   | Description                                                                                |
| ------ | ---------------------- | ------------------------------------------------------------------------------------------ |
| GET    | `/log/logs/`           | List logs. Filter: `?period=today\|this_week\|this_month\|this_year` or `?date=YYYY-MM-DD` |
| POST   | `/log/logs/`           | Create log                                                                                 |
| GET    | `/log/logs/<id>/`      | Log detail with act_logs                                                                   |
| PATCH  | `/log/logs/<id>/`      | Update log                                                                                 |
| DELETE | `/log/logs/<id>/`      | Delete log + acts                                                                          |
| GET    | `/log/logs/<id>/acts/` | List acts                                                                                  |
| POST   | `/log/logs/<id>/acts/` | Add act                                                                                    |
| GET    | `/log/acts/<id>/`      | Act detail                                                                                 |
| PATCH  | `/log/acts/<id>/`      | Update act                                                                                 |
| DELETE | `/log/acts/<id>/`      | Delete act                                                                                 |

### Co-Driver `/log/`

| Method | Path                                            | Description              |
| ------ | ----------------------------------------------- | ------------------------ |
| POST   | `/log/logs/<co_log_id>/submit-co-driver/`       | Submit for approval      |
| PATCH  | `/log/logs/<primary_log_id>/approve-co-driver/` | Approve or reject        |
| GET    | `/log/logs/pending-co-drivers/`                 | List pending submissions |

### Manager `/log/`

| Method | Path                               | Description                       |
| ------ | ---------------------------------- | --------------------------------- |
| GET    | `/log/managers/drivers/`           | All drivers with log counts       |
| GET    | `/log/managers/drivers/<id>/logs/` | Driver logs (same period filters) |

### Trips `/trip/`

| Method | Path                       | Description        |
| ------ | -------------------------- | ------------------ |
| GET    | `/trip/trips/`             | List trips         |
| POST   | `/trip/trips/`             | Plan a trip        |
| GET    | `/trip/trips/<id>/`        | Full trip detail   |
| DELETE | `/trip/trips/<id>/`        | Delete trip        |
| POST   | `/trip/trips/<id>/replan/` | Re-run the planner |

---

## HOS Rules Implemented

| Rule                             | Value             |
| -------------------------------- | ----------------- |
| Maximum driving per shift        | 11 hours          |
| Maximum on-duty window per shift | 14 hours          |
| Mandatory rest break after       | 8 hours driving   |
| Mandatory break duration         | 30 minutes        |
| Off-duty/sleeper reset           | 10 hours          |
| Cycle limit                      | 70 hours / 8 days |
| Fuel stop interval               | ≤ 1,000 miles     |
| Pickup on-duty time              | 1 hour            |
| Dropoff on-duty time             | 1 hour            |
| Assumed average speed            | 55 mph            |

---

## Co-Driver Workflow

```
1. Co-driver fills their own DayLog for the shared work day

2. POST /log/logs/<co_log_id>/submit-co-driver/
   { "primary_log_id": <id> }
   → co_driver_approved = null (pending)

3. Main driver checks GET /log/logs/pending-co-drivers/

4. Main driver reviews the co-driver's log + 24-hr grid

5. PATCH /log/logs/<primary_log_id>/approve-co-driver/
   { "co_driver_log_id": <id>, "approve": true }
   → co_driver_approved = true
   → primary_log.co_driver = co_driver.user
```

---

## Trip Planning Pipeline

```
POST /trip/trips/   { current_location, pickup, dropoff, cycle_used, departure }
         ↓
  Geocode 3 locations         (ORS /geocode/search)
         ↓
  Fetch driving route         (ORS /v2/directions/driving-hgv — truck routing)
         ↓
  HOS Engine (hos.py)
  Walk route inserting:
    • 30-min rest break    (after 8 hrs driving)
    • 10-hr sleeper reset  (after 11-hr or 14-hr limit)
    • Fuel stop            (every ≤ 1,000 miles)
    • 1-hr pickup          (on-duty)
    • 1-hr dropoff         (on-duty)
         ↓
  Save TripStops + build ELD Logs
    DayLog.get_or_create() per calendar day
    ActLog.create() per segment
    Signals fire → totals auto-recomputed
         ↓
  Trip.status = 'computed'
  Response: stops timeline + ELD day logs with 24-hr grid data
```

---

## Automatic Totals Sync

`DayLog` stores pre-computed hour totals for fast reads. They stay in sync automatically:

```python
# logApi/signals.py
@receiver(post_save, sender=ActLog)
def actlog_saved(sender, instance, **kwargs):
    recompute_day_log_totals(instance.day_log)

@receiver(post_delete, sender=ActLog)
def actlog_deleted(sender, instance, **kwargs):
    recompute_day_log_totals(instance.day_log)
```

`recompute_day_log_totals()` issues one `SELECT` + one `UPDATE`. It never calls `DayLog.save()` so no re-entrancy risk.

For backfilling after a data migration:

```python
from logApi.utils import recompute_all_day_log_totals
count = recompute_all_day_log_totals()
```

---

## Running Tests

```bash
# HOS engine — no database, no API keys needed
pip install pytest
pytest tripApi/tests/test_hos.py -v

# Django tests
python manage.py test
```

22 HOS tests cover: stop structure, 30-min break rule, 11-hr driving limit, 14-hr window, 10-hr reset, fuel stops, pickup/dropoff, cycle exhaustion, stop ordering.

---

## User Roles

| Role    | is_driver | is_manager | Access                              |
| ------- | --------- | ---------- | ----------------------------------- |
| Driver  | ✓         | ✗          | Own logs, trips, co-driver workflow |
| Manager | ✗         | ✓          | All driver logs (read-only)         |
| Admin   | —         | —          | Django admin panel                  |

Roles are **mutually exclusive** — enforced at signup, profile update, and the API layer.

---

## Design System

Industrial / gauge aesthetic — built for trucking dispatchers and drivers.

| Element          | Choice                  | Rationale                                  |
| ---------------- | ----------------------- | ------------------------------------------ |
| Heading font     | Syne 800                | Bold, distinctive                          |
| Data font        | JetBrains Mono          | All times/miles/hours aligned, scannable   |
| Background       | `#0e0f11` deep charcoal | Dashboard darkness, low-light cab friendly |
| Primary accent   | `#f5a623` amber         | Gauge/instrument cluster reference         |
| Activity colours | Amber/Blue/Green/Purple | Distinct, match paper form conventions     |

The SVG 24-hour grid renders 96 quarter-hour slots across 4 activity rows with a continuous graph line and red transition dots — directly matching the paper Drivers Daily Log form visual.

---

## Frontend Architecture

The frontend is organized by **separation of concerns** across six layers:

| Layer      | Location                | Responsibility                                  |
| ---------- | ----------------------- | ----------------------------------------------- |
| Styles     | `src/styles/global.css` | All CSS — tokens, layout, components            |
| API client | `src/api/client.js`     | Token management, fetch wrapper, every endpoint |
| Utilities  | `src/hooks/utils.js`    | Formatters, errorMsg, useAsync hook             |
| Shared UI  | `src/components/`       | Icons, Modal, ActivityGrid                      |
| Pages      | `src/pages/<feature>/`  | One directory per feature; collocated modals    |
| Shell      | `src/App.jsx`           | Auth gate, sidebar, topbar, page switching      |

**Key design decisions:**

- `LogDetailModal` is a named export from `logs/LogsPage.jsx` and reused in `ManagerPage.jsx` — the only cross-page component dependency
- No global state library; state is colocated and communicated via props/callbacks
- No React Router; navigation is a `page` string in `App.jsx`
- `api/client.js` exports individual named functions (not an API object) for tree-shakeable, explicit imports

---

## License

MIT License. See LICENSE for details.

---

_Built for FMCSA compliance. Always verify HOS calculations against official FMCSA regulations before use in production fleet operations._
