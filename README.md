# Plywood Pro

Stock, billing and profit tracking for a plywood shop. Windows desktop app (single `.exe`), built with Python and Qt (PySide6), data in a local SQLite file.

## What it does

- **Sales and purchases** as multi-item bills with customer or supplier, discount, part payments and a printable PDF invoice
- **Stock** that is always computed from the bills, so it cannot drift; physical stock counts; closing a day so its entries cannot be changed
- **Customers and suppliers** with what they owe you and what you owe them, payments and statements
- **Expenses**, and **profit** after cost and expenses for any period
- **Reports** on screen, as PDF and as Excel
- **Backups**: automatic on exit, manual to a file, safe restore
- **Automatic updates** from GitHub Releases, verified by checksum

## Run it on a Mac (or Linux)

```sh
./run.sh --demo     # sample data you can play with; your real data is not touched
./run.sh            # your real data, in data/plywoodpro.db
./run.sh test       # run the automated tests
```

The first run sets up a private Python environment in `.venv` (needs [uv](https://docs.astral.sh/uv/) or Python 3.11+).

To try the packaged app on a Mac: `.venv/bin/python tools/build.py`, then open `dist/Plywood Pro.app`.

## Build the Windows .exe

**From a Mac (no Windows PC needed):** GitHub builds it.

- Test build: on GitHub open *Actions → Build Windows app → Run workflow*. When it finishes, download `PlywoodPro-windows` from the run's *Artifacts*.
- Release: set `CURRENT_VERSION` in `utils/updater.py`, commit, then

  ```sh
  git tag v2.0.0 && git push origin v2.0.0
  ```

  GitHub runs the tests, builds the `.exe`, runs its self-test, and publishes a Release with the zip and its checksum. Installed copies offer the update the next time they start.

**On a Windows PC:** `build.bat` (build only) or `release.bat` (build, tag and publish).

Every build is checked with `"Plywood Pro.exe" --selftest`, which opens every screen on sample data, saves a sale and writes an invoice, reports and a backup.

## Where the data lives

Next to the `.exe`, in `data/plywoodpro.db`. Backups are in `data/backups/`. A v1 data file is upgraded automatically the first time v2 opens it, after a safety copy is saved in `data/backups/`.

## For developers

- `database/` connection and migrations · `models/` all business rules · `ui/` screens · `utils/` export, backup, updater
- `ui/GUIDE.md` explains how screens are built
- `tools/shot.py` renders any screen to a PNG without opening a window; `tools/seed_demo.py` creates sample data
