# DKA Hotspot Analysis

This project investigates where diabetic ketoacidosis (DKA) occurs at the first
manifestation of type 1 diabetes in children and adolescents. The goal is to
identify regional hotspots and support targeted awareness campaigns. The pilot
covers Tübingen, Reutlingen and Zollernalbkreis in Baden-Württemberg.

## What the app does

The app imports case data that have already been pseudonymized by participating
clinics and calculates DKA severity from pH and bicarbonate. It maps cases around
postcode centroids and provides analyses by time, age, sex, district and GISD
deprivation. Clinic and paediatric-practice locations can be displayed for
geographic context.

## Data sources

- **Clinical case data** — provided in pseudonymized form by the participating
  diabetes clinics in Tübingen and Reutlingen.
- **Socioeconomic deprivation** — postcode-level GISD data derived from the
  [Robert Koch Institute GISD dataset](https://robert-koch-institut.github.io/German_Index_of_Socioeconomic_Deprivation_GISD/).
- **District boundaries** —
  [BKG Administrative Areas 1:250,000 (VG250)](https://gdz.bkg.bund.de/index.php/default/open-data/wfs-verwaltungsgebiete-1-250-000-stand-01-01-wfs-vg250.html).
- **Postcode coordinates** — generated using the
  [Geoapify Geocoding API](https://www.geoapify.com/geocoding-api/).
- **Paediatric practices** — scraped from the public
  [Kassenärztliche Vereinigung Baden-Württemberg physician search](https://www.arztsuche-bw.de/)
  on 13 August 2026.
- **Hospitals** — extracted from the
  [Bundes-Klinik-Atlas Open Data](https://bundes-klinik-atlas.de/open-data/).

## Quick start

To try the app locally with synthetic data:

1. Install the dependencies and create your `.env` file:

   ```bash
   uv sync
   cp .env.example .env
   ```

2. Generate a session secret and paste it after `NICEGUI_STORAGE_SECRET=` in
   `.env`. Edit that line; a second one added below it would be ignored.

   ```bash
   python3 -c "import secrets; print(secrets.token_urlsafe(48))"
   ```

3. Create an account. The script asks for a username, a role (enter `admin`)
   and a password of at least 12 characters:

   ```bash
   uv run scripts/create_user.py
   ```

4. Load the 500 synthetic cases and start the app. `--replace` deletes any cases
   already in the database.

   ```bash
   uv run scripts/import_cases.py src/data/dka_synthetic_patients_plz5.csv --replace
   uv run src/main.py
   ```

5. Open <http://localhost:8081> and log in.

## Installation

1. If you're using NixOS, enter the development shell first. It provides Python,
   uv, ruff and sqlite. NixOS also needs the `nix-ld` setting described under
   [Developer requirements](#developer-requirements).

   ```bash
   nix-shell shell.nix
   ```

2. Create or update the environment with uv:

   ```bash
   uv sync
   ```

3. Activate the environment:

   ```bash
   source .venv/bin/activate
   ```

## Environment variables

Copy `.env.example` to `.env` and set:

- **`NICEGUI_STORAGE_SECRET`** (required) signs the session cookie. Set it in
  development too
- **`DKA_ENV`** is `development` (default) or `production`. 
- **`DKA_PORT`** defaults to `8081`.
- **`GEOAPIFY_API_KEY`** is only needed by `scripts/build_plz5_coordinates.py`.

## Database

Everything is stored in the SQLite file `src/data/app.db`, created automatically
on first use.

### Create the first admin

A new database has no users. Create the first one with:

```bash
uv run scripts/create_user.py
```

Further users can then be created in the app under **Users**.

### Roles

- **user** sees the overview map and the analysis page.
- **scientist** also sees the case map and the **Data** page for importing
  cases.
- **admin** also manages users (create, change role, reset password,
  deactivate) and sees the audit trail.

### Load data

The synthetic demo data is loaded as shown in the [Quick start](#quick-start).
Real pseudonymized case data is uploaded as a CSV file on the **Data** page,
which shows the expected columns, or imported with `scripts/import_cases.py`
(`--replace` deletes all existing cases first). New files in `src/data` are
gitignored by default.

### Backups

```bash
uv run scripts/backup_db.py
```

This writes a verified snapshot to `backups/` (gitignored) and keeps the 14
most recent. To restore one, stop the app, delete `src/data/app.db-wal` and
`src/data/app.db-shm`, and copy the backup over `src/data/app.db`.

### Start over

> [!WARNING]
> This permanently deletes every case record, user account and audit-log entry.
> Without a backup (see [Backups](#backups)) they cannot be recovered.

Stop the app first, then delete the database and its two SQLite side files:

```bash
rm -f src/data/app.db src/data/app.db-wal src/data/app.db-shm
```

The next start creates an empty database; create the first admin again.

## Start the web app

1. Make sure `NICEGUI_STORAGE_SECRET` is set in `.env` and at least one user
   exists (see [Environment variables](#environment-variables) and
   [Create the first admin](#create-the-first-admin)).

2. Run the main Python file:

   ```bash
   uv run src/main.py
   ```

3. Open <http://localhost:8081>, or the port set in `DKA_PORT`, and log in.

## Developer requirements

- **Python 3.11 or newer** (CI tests 3.11 and 3.13).
- **[uv](https://docs.astral.sh/uv/).** `uv sync` also installs the developer
  tools (pytest, pytest-cov, ruff)
- **NixOS:** set `programs.nix-ld.enable = true;` in `configuration.nix`. uv
  installs prebuilt wheels (numpy, scipy, pandas, statsmodels).

## Running the tests

Run all the tests:

```bash
uv run pytest
```