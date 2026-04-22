# Workshop 06 — Simulate Real-Time Ingestion

Replay the 16 mock CSVs from `resources/datasets/` into ADLS Gen2 — either at the **real 10-minute cadence** or in **accelerated mode** for quick end-to-end tests.

**Prerequisite:** [Workshop 05](../05-event-trigger/) complete
**Next:** [Workshop 07 — Power BI Report](../07-powerbi-report/)

---

## 6.1 Prerequisites

- Your IP is allow-listed on the storage firewall (Workshop 01.4), **or** you have another signed-in upload path.
- You are signed into Azure (`az login`).

## 6.2 Run the simulator

Script: [scripts/06-simulate-upload.ps1](scripts/06-simulate-upload.ps1)

### Real 10-minute cadence (production-realistic)

```powershell
./workshops/06-simulate-ingestion/scripts/06-simulate-upload.ps1 `
    -StorageAccount <sa> `
    -ResourceGroup  <rg>
```
Total duration: ~2.5 hours for 16 files.

### Accelerated mode (30 s between files)

```powershell
./workshops/06-simulate-ingestion/scripts/06-simulate-upload.ps1 `
    -StorageAccount <sa> `
    -ResourceGroup  <rg> `
    -Accelerated
```
Total duration: ~8 minutes.

### Custom cadence

```powershell
./workshops/06-simulate-ingestion/scripts/06-simulate-upload.ps1 `
    -StorageAccount <sa> -ResourceGroup <rg> `
    -IntervalSeconds 60
```

## 6.3 Monitor during replay

**Fabric Monitor hub** → Pipeline runs (updates per file drop).

**KQL quick check:**

```kusto
ProcessedFiles
| summarize Files=count(), Rows=sum(RowCount) by Status
```

Expected after full replay: 16 `Success`, 0 `Failed`, 0 `Skipped-Duplicate`.

## ✅ Exit Criteria

- [ ] All 16 files uploaded
- [ ] `ProcessedFiles` shows 16 × `Success`
- [ ] `DepositMovement` contains rows for every 30-min slot

→ Proceed to **[Workshop 07 — Power BI Report](../07-powerbi-report/)**
