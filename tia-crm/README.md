# TIA CRM

A small-team CRM: companies, contacts, deals/pipeline, tasks, and a unified activity timeline
(calls, emails, meetings, notes). Built as a Flask API + a plain HTML/JS frontend, using
SQLAlchemy so the same code runs against SQLite locally and Postgres (Neon) in production —
no dialect-specific SQL to maintain.

## What's new vs the old Dial Sheet cold-call tracker
- **Companies** replace flat "clients" — each has multiple **Contacts**, not just one.
- **Deals** — a real pipeline: Lead → Qualified → Proposal Sent → Negotiation → Won/Lost,
  with value and expected close date. Kanban board under **Pipeline**.
- **Tasks** — anything with a due date, not just call follow-ups.
- **Activities** — calls (with outcome), emails, meetings, and notes all show up in one timeline
  per company. Logging a call still auto-updates the company's status like before.
- **Roles**: `admin` (full access, manages users, resets passwords), `manager` (sees everything,
  can't manage users), `agent` (only sees companies/deals/tasks assigned to or created by them).
- **Database**: Postgres via `DATABASE_URL` (e.g. Neon) — no persistent disk needed, unlike the
  SQLite version. Falls back to a local SQLite file if `DATABASE_URL` isn't set, so you can run
  it locally with zero setup.

## Project structure
```
app.py              # app factory: DB config, blueprint registration, admin bootstrap
models.py            # SQLAlchemy models: User, Company, Contact, Deal, Task, Activity
routes/
  auth.py             # login/logout/register/session, role_required decorator
  companies.py         # companies + nested contacts
  deals.py              # deals + /api/pipeline (kanban board grouped by stage)
  tasks.py               # tasks
  activities.py            # unified timeline (calls/emails/meetings/notes)
  dashboard.py              # summary stats
static/
  index.html, css/style.css, js/app.js
```

## Run locally
```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

export ADMIN_EMAIL=you@company.com
export ADMIN_PASSWORD=changeme123
export SECRET_KEY=some-random-string
# DATABASE_URL not set -> uses a local dev.db (SQLite) automatically

python3 app.py
```
Visit http://localhost:5000 and log in with the admin credentials above.
Once logged in, use **Team → + Add team member** to add the rest of your callers
(only admins can create accounts).

## Deploy to Render + Neon (matches your TIA Ticketing setup)
1. Create a free Postgres database at neon.tech, copy its connection string.
2. On Render, use the "New + Blueprint" flow pointed at this repo (picks up `render.yaml`),
   or set up manually:
   - **Build command:** `pip install -r requirements.txt`
   - **Start command:** `gunicorn app:app`
   - **Env vars:** `SECRET_KEY` (generate), `FLASK_ENV=production`, `ADMIN_EMAIL`,
     `ADMIN_PASSWORD`, `DATABASE_URL` (your Neon connection string)
3. No disk needed this time — Neon handles persistence, so redeploys are safe.

## Roles cheat sheet
| Role    | Sees                          | Can manage users | Can delete companies |
|---------|-------------------------------|-------------------|----------------------|
| admin   | everything                    | yes                | yes                   |
| manager | everything                    | no                  | yes                    |
| agent   | only their own assigned/created records | no      | only their own          |

## Migrating your old spreadsheet or the previous Dial Sheet tracker data
Export to CSV and match columns to `companies` (`name, industry, source, status`) and,
if you have per-contact info, `contacts` (`company_id, name, title, phone, email`).
Happy to write a one-off import script once you share the column headers.
