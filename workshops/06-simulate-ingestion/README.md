# Workshop 06 — Simulate Real-Time Ingestion (Portal)

Replay the 16 mock CSVs into ADLS Gen2 so the pipeline fires on each file and you can see dashboards update live. Use the **Azure Portal Storage browser** — no command line required.

**Prerequisite:** [Workshop 05](../05-event-trigger/) complete
**Next:** [Workshop 07 — Power BI Report](../07-powerbi-report/)

---

## 6.1 Prerequisites

- Your public IP is allow-listed on the storage firewall (done in Workshop 01.2 step 4).
- You're signed into **[portal.azure.com](https://portal.azure.com)** with rights to upload blobs.
- Your local clone of this repo contains the 16 files in `resources/datasets/`.

## 6.2 Upload files via Azure Portal Storage browser

### Option A — Quick smoke test (upload all 16 at once)

1. Azure Portal → storage account → **Storage browser** (left nav) → **Blob containers** → `intraday-deposits` → `incoming/`.
2. Toolbar → **Upload**.
3. **Browse for files** → multi-select all 16 `mock_*.csv` files → **Upload**.
4. Switch to Fabric Monitor hub. You'll see 16 pipeline runs queue up and complete within a minute or two.

### Option B — Realistic cadence (one file every 10 min)

For a more life-like demo, upload one file at a time with a timer:

1. Same navigation path as above.
2. **Upload** → pick `mock_0000_0030.csv` → **Upload**.
3. Wait 10 minutes (or accelerated to 30 s for a short demo).
4. Repeat for the next file `mock_0030_0100.csv`, and so on.
5. Keep the Fabric dashboard open to watch values tick up.

### Option C — Drag & drop in the Containers blade

If you prefer the classic UI: Storage account → **Containers** → `intraday-deposits` → click into `incoming/` → simply **drag CSVs from Windows Explorer** onto the browser window.

## 6.3 Monitor during replay

- **Fabric Portal → Monitor hub → Pipeline runs** — one row per file, updates live.
- In the Fabric KQL Database `DepositMovement`, run this query to confirm:
  ```kusto
  ProcessedFiles
  | summarize Files=count(), Rows=sum(RowCount) by Status
  ```
- Expected after all 16 files: **16 Success, 0 Failed, 0 Skipped-Duplicate**.

## ✅ Exit Criteria

- [ ] All 16 files visible under `intraday-deposits/incoming/` in the Storage browser
- [ ] `ProcessedFiles` shows 16 × `Success`
- [ ] `DepositMovement` contains rows for every 30-min slot

→ Proceed to **[Workshop 07 — Power BI Report](../07-powerbi-report/)**

> ℹ️ A bulk replay script `scripts/06-simulate-upload.ps1` is also provided for automation engineers; analysts can skip it.
