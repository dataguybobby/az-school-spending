# Handoff

AZ School Spending is in the public GitHub repository https://github.com/dataguybobby/az-school-spending on the `master` branch. Phoenix Dataworks publishes the site. It was not deployed. Connecting Vercel is a separate step, documented in README.md. `http://127.0.0.1:43127` only works on the machine that starts the server.

## Run the screened index offline

From the unzipped folder, after Node and Python are installed:

```bash
python3 -m pip install -r requirements.txt
cd web && npm install
cd ..
cd web && npx next dev -p 43127 -H 127.0.0.1
```

`npm install` needs network the first time. After that, the app reads `data/public/ledger.sqlite` and does not need the original PDFs. Open `http://127.0.0.1:43127` in a browser on that same machine.

## Re-ingest the official reports

Needs network unless the PDFs are already in `data/raw/<sha256>.pdf`:

```bash
python3 -m pipeline ingest
```

That downloads nine public document URLs, checks SHA-256, and rebuilds the public database. Raw PDFs and the private database stay in `data/`, which is gitignored and is not in this zip.

## Tests

```bash
python3 -m pytest tests/test_ledger.py tests/test_enrollment.py tests/test_dictionary.py -q
```

October 1 enrollment is a separate comparison in the public database. `python3 -m pipeline enrollment` reloads it. A full `python3 -m pipeline ingest` reloads it after rebuilding spending and does not change screened line amounts.

Synthetic privacy, overlap, revision, and duplicate-line tests run without PDFs. Official-PDF assertions skip when `data/raw` is absent. Checks against `data/public/ledger.sqlite` run when that file is present.

## What the default total is

The spending total is the sum of screened public lines on the selected date basis. It is not unique spend and it is not a printed report total. Withheld rows are excluded. The September 18–October 27 and October 27–November 13 Scottsdale headers share October 27, and the parsed check dates are disjoint, so those documents stay in the default sum. Identical lines on different dates are not collapsed. A shared check date would be kept in the private ledger and omitted from the default total, charts, and CSV.

Paradise Valley is `parsed_zero` with a null printed total. It is not shown as zero spending.
