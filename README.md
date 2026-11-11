# Metro School Ledger

Local, read-only ledger of Phoenix-area public K-12 accounts payable and voucher lines. It starts from official Scottsdale, Higley, and Queen Creek PDFs. It does not claim every metro district is covered, and it does not turn voucher or AP lines into proof that a payment settled.

No scheduler is installed or enabled.

The GitHub repository is https://github.com/dataguybobby/az-school-spending. The app is on the `master` branch. GitHub still defaults to the placeholder `main` branch; this import did not have permission to change the default. Set the default branch to `master` before publishing.

## Setup

```bash
python3 -m pip install -r requirements.txt
python3 -m pip install pytest
cd web && npm install && cd ..
```

## Commands

Fetch, parse, classify, and index. The separate stage names all run the same idempotent ingest. A second run of the same bytes does not add duplicate lines.

```bash
python3 -m pipeline discover
python3 -m pipeline fetch
python3 -m pipeline extract
python3 -m pipeline normalize
python3 -m pipeline classify
python3 -m pipeline index
python3 -m pipeline ingest
python3 -m pipeline search "stress balls" --basis check_date
python3 -m pipeline export --out artifacts/sample.csv --q "stress balls" --basis check_date
python3 -m pytest tests/test_ledger.py -q
```

`discover` reads at most 8 registry discovery URLs, saves same-host anchors, and does not ingest them.

Local ingest writes `data/public/ledger.sqlite`. The Next app does not read that path at runtime. Copy the screened file into the web bundle, then start the app:

```bash
node web/scripts/prepare-public-db.mjs
cd web && npx next dev -p 43127 -H 127.0.0.1
```

`npm run build` runs the same check. It fails if `web/data` contains anything except that public database, or if the database has private tables, check-number columns, or withheld description text.

Raw PDFs and the private database stay in `data/`, which is gitignored. They are not part of the Next bundle. Check numbers and quarantined payee rows are not in the public database.

Production build, still local:

```bash
cd web && npm ci && npm run build && npx next start -p 43127 -H 127.0.0.1
```

## What the index contains

Indexed only when the parsed detail lines match the printed total:

- Five Scottsdale Unified accounts payable PDFs, July 1 through December 2, 2025. Windows are the printed report periods, not a continuous fiscal year. The September 18–October 27 and October 27–November 13 headers share October 27. Parsed check dates do not overlap: the earlier report's last check date is October 23 and the later report's first is October 29, with zero rows on October 27. Both stay in the default sum. Identical descriptions on different dates are separate lines.
- Higley voucher batch 1058, batch date November 20, 2024, fiscal year label 2024-2025. The batch date is not a check date.
- Queen Creek July voucher PDF, fiscal year label 2026-2027, several batch dates. A printed check number of 0 is stored only in the private database and is not treated as a payment.

Fetched and not indexed:

- Paradise Valley PDF matches the v2 SHA-256 and is a Canon paper-capture scan. The parser emitted no lines (`parsed_zero`). Its printed total is null, reason `no_printed_total_extracted_from_ocr_scan`, not a reported zero. It is not in spending charts.
- Chandler PDF matches the v2 SHA-256 and is also a paper-capture scan. Extracted lines did not reconcile, so they are not public and are not shown as zero spending.

Gilbert stays an indexed lead from a prior 403, not an ingested body. Mesa stays an aggregate lead, not transaction coverage. ADE's active-LEA spreadsheet was not acquired. The AZDOR 2026 list has 1,449 site rows and 395 CTDS holder IDs, including closed sites. County pages list 57 Maricopa and 21 Pinal names. None of those figures is a coverage denominator.

## Adapters

Implemented and exercised:

- `susd_ap_report_pdf` for the Scottsdale board accounts payable layout.
- `diligent_voucher_account_summary` for text-native Higley and Queen Creek voucher supplements.

Not implemented, because this run did not successfully parse them: BoardDocs PDF attachments, district-hosted HTML, CSV, and XLS, Govly purchase-order pages, and the ADE spreadsheet. Scanned paper-capture PDFs use the voucher parser only as a rejection path.

## Categories and privacy

Categories are inferred by `phoenix-k12-neutral-2026.11.06`. Amazon is a vendor. Unclassified is the default. Item text is weak evidence. Account titles on voucher rows are stronger and are still not a loaded USFR codebook. `registry/category_overrides.json` can replace a category by `line_id`.

A row is public only when the payee looks like a business and the description does not contain an email, phone, street address, long digit identifier, reimbursement or student context, an authorized user, an IEP or ESY reference, or medicaid/diagnosis/prescription language. Unknown payees are withheld. That also withholds some two- and three-word trade names. DAC text is kept as printed and is not treated as a school location. The default total is the sum of those screened lines. It is not unique spend and it is not the printed report total.

## Dates

Check date, voucher batch date, and the native fiscal-year label are separate. The spending page asks which date basis to filter and labels that basis on the total. A voucher batch date is not backfilled into the check date. Lines with no date on the selected basis are omitted from that filter rather than treated as zero.

## Network and offline

Needs network:

- `python3 -m pip install -r requirements.txt` and `cd web && npm install` on a fresh machine
- `python3 -m pipeline ingest` when `data/raw/<sha256>.pdf` is not already present. It downloads the nine public document URLs and checks SHA-256.

Works offline after dependencies are installed, including from the source zip. The zip contains `web/data/public/ledger.sqlite`.

- `cd web && npx next dev -p 43127 -H 127.0.0.1` reads that bundled database only
- `python3 -m pytest tests/test_ledger.py tests/test_bundled_public_db.py -q` runs synthetic cases and the bundled-database checks without PDFs. Official-PDF assertions skip when `data/raw` is absent.

This workspace did not deploy the site. There is no production URL from this change.

## Deploy on Vercel later

The source repository is https://github.com/dataguybobby/az-school-spending. Publish the `master` branch. This import did not deploy the site, add a Vercel project, set a custom domain, or enable GitHub Pages. Connect Vercel to that GitHub repository when you are ready to publish, and select `master`. If GitHub still shows `main` as the default branch, switch the default to `master` first.

In the Vercel project settings:

- Root Directory: `web`
- Framework preset: Next.js
- Node.js version: 22.x
- Install command: `npm ci`
- Build command: `npm run build`
- Production branch: `master`
- No environment variables and no database add-on

`web/vercel.json` records the same install and build commands. Python is not installed or run on Vercel. Re-ingest stays on a local machine: run `python3 -m pipeline ingest`, then `node web/scripts/prepare-public-db.mjs`, then commit the updated `web/data/public/ledger.sqlite` before the next Vercel deployment.

The hosted site is a read-only extract of screened lines. It is not an official government site, not a complete district census, and not proof that a payment settled.
