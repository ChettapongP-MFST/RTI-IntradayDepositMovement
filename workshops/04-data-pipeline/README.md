# Workshop 04 — Data Pipeline (Hardened & Idempotent)

Build the Fabric Data Pipeline that ingests one CSV per run into the KQL table `DepositMovement`, with duplicate protection and full audit written to the **Warehouse** table `wh_control_framework.dbo.ProcessedFiles`.

**Prerequisite:** [Workshop 03](../03-trusted-workspace-access/) complete
**Next:** [Workshop 05 — Event Trigger](../05-event-trigger/)

---

## 4.1 Create the pipeline

Fabric workspace → **+ New item** → **Data pipeline** → name: `pl_ingest_DepositMovement`.

## 4.2 Create the ADLS Gen2 connection (Workspace Identity)

1. Canvas → **Copy data** → **New connection** → **Azure Data Lake Storage Gen2**.
2. URL: `https://<STORAGE-ACCOUNT>.dfs.core.windows.net`
3. Authentication: **Workspace Identity**.
4. **Test connection** → must succeed. (If it fails, revisit Workshop 03.)

## 4.3 Pipeline parameters

| Name | Type | Default |
|---|---|---|
| `pFileName` | String | *(empty — used for manual runs)* |
| `pFolder` | String | `incoming` |

## 4.4 Activity flow

```
[Get Metadata]
      │
      ▼
[Lookup ProcessedFiles]
      │
      ▼
[If Condition: @empty(Lookup.output.firstRow)]
      │
      ├─ True  →  [Copy CSV to Eventhouse]  ──success──▶ [Append Success audit]
      │                                     ──failure──▶ [Append Failed audit]      │                   │
      │                   └────────────────▶ [Recalculate Gold Summary]      │
      └─ False →  [Append Skipped-Duplicate audit]
```

### 4.4.1 `Get Metadata` — verify file landed

- **Dataset:** ADLS Gen2 / DelimitedText (no schema).
- **File path:** container `intraday-deposits`, folder `@pipeline().parameters.pFolder`,
  file `@coalesce(pipeline()?.TriggerEvent?.FileName, pipeline().parameters.pFileName)`
- **Field list:** `exists`, `size`, `lastModified`.
- **Retry:** 2 × 30 s.

> On ADLS Gen2 (HNS), `BlobCreated` fires only on `FlushWithClose` (file fully written). Get Metadata is a defensive second check.

### 4.4.2 `Lookup ProcessedFiles` — dedup check

- Source: **Warehouse** `wh_control_framework` via workspace identity (Fabric-native connection picker: **+ New** → **Warehouse** → select `wh_rti_control`).
- Query (T-SQL):
  ```sql
  SELECT TOP (1) FileName
  FROM dbo.ProcessedFiles
  WHERE FileName = '@{coalesce(pipeline()?.TriggerEvent?.FileName, pipeline().parameters.pFileName)}'
    AND Status   = 'Success';
  ```
- **First row only** ✅.

### 4.4.3 `If Condition`

Expression: `@empty(activity('Lookup ProcessedFiles').output.firstRow)`

#### True branch — load the file

**a) `Copy CSV to Eventhouse`**

- Source: ADLS Gen2 DelimitedText, first row as header.
- **Additional columns** (projected at source):
  | Name | Value |
  |---|---|
  | `load_ts` | `@utcNow()` |
  | `file_name` | `@coalesce(pipeline()?.TriggerEvent?.FileName, pipeline().parameters.pFileName)` |
  | `pipeline_name` | `@pipeline().Pipeline` |
  | `pipeline_runid` | `@pipeline().RunId` |
- Sink: KQL DB → `DepositMovement`, mapping `DepositMovement_mapping`.
- **Ingestion properties (advanced):**
  - Tag: `ingest-by:@{coalesce(pipeline()?.TriggerEvent?.FileName, pipeline().parameters.pFileName)}`
  - `ingestIfNotExists = ["FileName"]`  *(server-side dedup safety net)*
- Retry: 3 × 60 s.

**b) `Append Success` (Script activity → Warehouse `wh_control_framework`, on Copy Success):**

```sql
INSERT INTO dbo.ProcessedFiles
    (FileName, IngestedAtUtc, RowCount_, Status, PipelineName, PipelineRunId, RunAsUser, ErrorMsg)
VALUES (
    '@{coalesce(pipeline()?.TriggerEvent?.FileName, pipeline().parameters.pFileName)}',
    SYSUTCDATETIME(),
    @{activity('Copy CSV to Eventhouse').output.rowsCopied},
    'Success',
    '@{pipeline().Pipeline}',
    '@{pipeline().RunId}',
    '@{concat(pipeline().TriggerType,'':'',coalesce(pipeline().TriggerName,''manual''))}',
    NULL
);
```

**c) `Append Failed` (Script activity → Warehouse, on Copy Failure dependency):**

```sql
INSERT INTO dbo.ProcessedFiles
    (FileName, IngestedAtUtc, RowCount_, Status, PipelineName, PipelineRunId, RunAsUser, ErrorMsg)
VALUES (
    '@{coalesce(pipeline()?.TriggerEvent?.FileName, pipeline().parameters.pFileName)}',
    SYSUTCDATETIME(),
    0,
    'Failed',
    '@{pipeline().Pipeline}',
    '@{pipeline().RunId}',
    '@{concat(pipeline().TriggerType,'':'',coalesce(pipeline().TriggerName,''manual''))}',
    '@{replace(activity('Copy CSV to Eventhouse').error.message,'''','''''')}'
);
```

#### False branch — skip and audit

**`Append Skipped-Duplicate` (Script activity → Warehouse):**

```sql
INSERT INTO dbo.ProcessedFiles
    (FileName, IngestedAtUtc, RowCount_, Status, PipelineName, PipelineRunId, RunAsUser, ErrorMsg)
VALUES (
    '@{coalesce(pipeline()?.TriggerEvent?.FileName, pipeline().parameters.pFileName)}',
    SYSUTCDATETIME(),
    0,
    'Skipped-Duplicate',
    '@{pipeline().Pipeline}',
    '@{pipeline().RunId}',
    '@{concat(pipeline().TriggerType,'':'',coalesce(pipeline().TriggerName,''manual''))}',
    NULL
);
```

> 💡 Use the Fabric **Script** activity (not **Stored procedure**) and point it at the `wh_control_framework` Warehouse connection. Each audit branch is a single statement so there's no transaction concern.

### 4.4.4 `Recalculate Gold Summary` (Script activity → KQL Database)

After the audit row is written, call the stored procedure to recalculate **only** the dates present in the newly ingested file.

- **Connection:** KQL Database `DepositMovement` (via workspace identity)
- **Script:**

```kusto
exec sp_Recalculate_Summary_Alert_Channel
```

> This runs the stored procedure created in Workshop 02.7. It finds distinct dates from records ingested in the last 15 minutes and recalculates only those dates in the `Summary_Alert_Channel` Gold table.

## 4.5 Save and test manually

1. Upload one CSV (e.g. `mock_0000_0030.csv`) to `intraday-deposits/incoming/` (using the temporarily-allow-listed IP from Workshop 01.4).
2. Run the pipeline with `pFileName = mock_0000_0030.csv` and `pFolder = incoming`.
3. Verify:
   - `DepositMovement` (KQL) has new rows with the 4 lineage columns populated — `DepositMovement | count`.
   - `dbo.ProcessedFiles` (Warehouse) has **1** `Success` row — `SELECT TOP (5) * FROM dbo.ProcessedFiles ORDER BY IngestedAtUtc DESC;`.
   - `Summary_Alert_Channel` (KQL Gold) has aggregated data — `Summary_Alert_Channel | count`.
4. Re-run the same pipeline — verify **no new data rows**, just a new `Skipped-Duplicate` audit row.

## ✅ Exit Criteria

- [ ] Pipeline succeeds end-to-end
- [ ] Idempotency proven (re-run = Skipped-Duplicate)
- [ ] Failure path tested (missing file = Failed audit row with `ErrorMsg`)
- [ ] Gold table `Summary_Alert_Channel` updated after each successful ingestion

→ Proceed to **[Workshop 05 — Event Trigger](../05-event-trigger/)**

---

### Reference

A reference `pipeline.json` export is stored in [`pipeline/pl_ingest_DepositMovement.json`](pipeline/pl_ingest_DepositMovement.json) once you export it from Fabric (File → Export → Pipeline JSON).
