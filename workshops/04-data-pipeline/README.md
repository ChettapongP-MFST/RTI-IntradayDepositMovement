# Workshop 04 — Data Pipeline (Hardened & Idempotent)

Build the Fabric Data Pipeline that ingests one CSV per run into the KQL table `DepositMovement`, with duplicate protection and full audit written to the **Warehouse** table `wh_control_framework.dbo.ProcessedFiles`.

**Prerequisite:** [Workshop 03](../03-create-summary-table/) complete
**Next:** [Workshop 05 — Event Trigger](../05-event-trigger/)

---

## 4.0 What we're building and why

Before clicking anything in Fabric, let's understand every component you'll create and **why** it exists.

### Pipeline-level components

| Component | What it is | Why we need it |
|---|---|---|
| **Pipeline parameters** (`pFileName`, `pFolder`) | Inputs passed *into* the pipeline by the caller (trigger or manual run) | The pipeline needs to know **which file** to process and **where** it is. Without parameters, you'd have to hard-code file names — impossible for an event-driven pipeline. |
| **Pipeline variable** (`vLoadTs`) | A value computed *during* the pipeline run | We need a **single timestamp** shared across multiple activities (Copy + KQL). If each activity called `utcNow()` separately, they'd get different timestamps — and the KQL function wouldn't find the rows it just ingested. |

### Activities (in execution order)

| # | Activity | Type | Purpose |
|---|---|---|---|
| **0** | `Set vLoadTs` | Set Variable | **Freeze the clock.** Captures `@utcNow()` once so every downstream activity uses the exact same timestamp. Without this, Copy and KQL would have different `load_ts` values. |
| **1** | `Get Metadata` | Get Metadata | **Defensive check — does the file actually exist?** Returns `exists`, `size`, `lastModified`. Catches race conditions where the trigger fires but the file isn't fully written yet. Also provides retry (2 × 30s) for transient storage hiccups. |
| **2** | `Lookup ProcessedFiles` | Lookup | **Duplicate guard.** Queries the Warehouse audit table: *"Has this file already been successfully processed?"* Returns one row (duplicate) or empty (new file). This is the **application-level idempotency** check. |
| **3** | `If Condition` | If Condition | **Router.** Evaluates `@empty(Lookup.output.firstRow)` — `true` = new file (go load it), `false` = duplicate (skip and audit). Splits the pipeline into two branches. |

### True branch (new file)

| # | Activity | Type | Purpose |
|---|---|---|---|
| **3a** | `Copy CSV to Eventhouse` | Copy Data | **The actual data ingestion.** Reads CSV from ADLS Gen2, injects 4 lineage columns (`load_ts`, `file_name`, `pipeline_name`, `pipeline_runid`), writes to KQL `DepositMovement` table. The `ingest-by` tag provides a **server-side dedup** safety net in KQL. |
| **3b** | `Append Success` | Script | **Audit trail — success.** Writes a row to `ProcessedFiles` with `Status = 'Success'` and the row count. This is what `Lookup ProcessedFiles` checks in future runs to prevent duplicates. |
| **3c** | `Append Failed` | Script | **Audit trail — failure.** Fires only if Copy fails (red arrow). Writes `Status = 'Failed'` with the error message. A failed file is **not** marked as processed, so the next trigger retry will attempt it again. |
| **3d** | `Recalculate Gold Summary` | KQL Activity | **Gold layer refresh** (Option A only). Calls the stored function with the exact `vLoadTs` to re-aggregate only the affected dates. Skipped if you use Option B (materialized view). |

### False branch (duplicate)

| # | Activity | Type | Purpose |
|---|---|---|---|
| **3e** | `Append Skipped-Duplicate` | Script | **Audit trail — skip.** Writes `Status = 'Skipped-Duplicate'` so you have a record that the pipeline ran but correctly decided not to re-ingest. Useful for monitoring and debugging. |

### How they work together

```
Trigger fires with file name
        │
        ▼
   [Parameters receive file name]
        │
        ▼
   [Set vLoadTs] ─── freeze timestamp for consistency
        │
        ▼
   [Get Metadata] ── does file exist? (defensive)
        │
        ▼
   [Lookup] ──────── already processed? (idempotency)
        │
        ▼
   [If Condition]
    ├─ New file:   Copy → Audit Success → Recalculate Gold
    │                └─ On Failure → Audit Failed (allows retry)
    └─ Duplicate:  Audit Skipped (no data touched)
```

> **The design goal:** the pipeline can be triggered **any number of times** for the same file and will produce the **exact same result** — one copy of the data, one success audit row, and zero errors. This is what "**idempotent**" means.

---

## 4.1 Create the pipeline

1. Open your **Fabric workspace**.
2. Click **+ New item** → search or scroll to **Data pipeline**.
3. Name: `pl_ingest_DepositMovement` → **Create**.

You'll land on an empty pipeline canvas.

---

## 4.2 Pipeline parameters & variables

Before building activities, set up the parameters and variables the pipeline will use.

### 4.2.1 Create pipeline parameters

1. Click anywhere on the **canvas background** (not on an activity).
2. In the bottom pane, click the **Parameters** tab.
3. Click **+ New** and create two parameters:

| Name | Type | Default Value |
|---|---|---|
| `pFileName` | String | *(leave empty)* |
| `pFolder` | String | `incoming` |

### 4.2.2 Create pipeline variables

1. In the same bottom pane, click the **Variables** tab.
2. Click **+ New** and create one variable:

| Name | Type | Default Value |
|---|---|---|
| `vLoadTs` | String | *(leave empty)* |

> `vLoadTs` will capture `@utcNow()` at the start of each run. The same timestamp is used as `load_ts` in the Copy activity and passed to the Gold recalculation function — ensuring they always match.

---

## 4.3 Activity flow (overview)

Here's the complete pipeline flow you'll build:

```
[Set vLoadTs]
      │
      ▼
[Get Metadata]
      │
      ▼
[Lookup ProcessedFiles]
      │
      ▼
[If Condition: @empty(Lookup.output.firstRow)]
      │
      ├─ True (new file)
      │     │
      │     ▼
      │   [Copy CSV to Eventhouse]
      │     │
      │     ├─ On Success → [Append Success audit] → [Recalculate Gold Summary]
      │     └─ On Failure → [Append Failed audit]
      │
      └─ False (duplicate)
            │
            ▼
          [Append Skipped-Duplicate audit]
```

---

## 4.4 Build the activities (step-by-step)

### 4.4.0 Activity: `Set vLoadTs`

Captures a single UTC timestamp for the entire pipeline run.

1. On the canvas, go to the **Activities** tab (top ribbon).
2. Click **Set variable** (under the "General" group, or search for it).
3. A "Set variable" activity appears on the canvas.

**General tab:**

| Setting | Value |
|---|---|
| Name | `Set vLoadTs` |

**Settings tab:**

| Setting | Value |
|---|---|
| Variable type | Pipeline variable |
| Name | `vLoadTs` |
| Value | Click the text box → click **Add dynamic content** (or press `Alt+Shift+D`) → type: `@utcNow()` → **OK** |

---

### 4.4.1 Activity: `Get Metadata`

Verifies the file exists in ADLS Gen2 before attempting ingestion.

1. **Activities** tab → click **Get metadata**.
2. Drag a **green arrow** (On Success) from `Set vLoadTs` → `Get Metadata`.

**General tab:**

| Setting | Value |
|---|---|
| Name | `Get Metadata` |
| Retry | `2` |
| Retry interval (sec) | `30` |

**Settings tab:**

You need a connection to ADLS Gen2. If this is your first time:

1. Click **Connection** → **+ New**.
2. Search for **Azure Data Lake Storage Gen2** → select it.
3. Fill in:

   | Setting | Value |
   |---|---|
   | URL | `https://<YOUR-STORAGE-ACCOUNT>.dfs.core.windows.net` |
   | Authentication kind | **Workspace Identity** |

4. Click **Test connection** → must show ✅ **Connection successful**.
   > If it fails, revisit [Workshop 00, sections 0.5–0.8](../00-prerequisites/) to verify Workspace Identity, RBAC, and resource instance rules.
5. Click **Create**.

After the connection is created:

| Setting | Value |
|---|---|
| Connection | *(the ADLS Gen2 connection you just created)* |
| File path — Container | `intraday-deposits` |
| File path — Directory | Click text box → **Add dynamic content** → `@pipeline().parameters.pFolder` |
| File path — File name | Click text box → **Add dynamic content** → `@coalesce(pipeline()?.TriggerEvent?.FileName, pipeline().parameters.pFileName)` |
| Field list | Click **+ New** three times and select: `exists`, `size`, `lastModified` |

> **Why `coalesce(...)`?** When the pipeline is triggered by an event (Workshop 05), the file name comes from `pipeline()?.TriggerEvent?.FileName`. For manual runs, it falls back to the `pFileName` parameter.

---

### 4.4.2 Activity: `Lookup ProcessedFiles`

Checks the Warehouse audit table to see if this file was already processed.

1. **Activities** tab → click **Lookup**.
2. Drag a **green arrow** (On Success) from `Get Metadata` → `Lookup ProcessedFiles`.

**General tab:**

| Setting | Value |
|---|---|
| Name | `Lookup ProcessedFiles` |

**Settings tab:**

1. Click **Connection** → **+ New** → search for **Warehouse** → select your `wh_control_framework` warehouse.
2. Fill in:

| Setting | Value |
|---|---|
| Connection | `wh_control_framework` |
| Use query | **Query** |
| Query | *(see below)* |
| First row only | ✅ Checked |

**Query** (click the text box → **Add dynamic content**):

```sql
SELECT TOP (1) FileName
FROM dbo.ProcessedFiles
WHERE FileName = '@{coalesce(pipeline()?.TriggerEvent?.FileName, pipeline().parameters.pFileName)}'
  AND Status   = 'Success';
```

> This returns one row if the file was already successfully processed, or empty if it's new.

---

### 4.4.3 Activity: `If Condition`

Routes the pipeline to either "load the file" or "skip as duplicate".

1. **Activities** tab → click **If condition**.
2. Drag a **green arrow** (On Success) from `Lookup ProcessedFiles` → `If Condition`.

**General tab:**

| Setting | Value |
|---|---|
| Name | `If Condition` |

**Activities tab:**

| Setting | Value |
|---|---|
| Expression | Click the text box → **Add dynamic content** → `@empty(activity('Lookup ProcessedFiles').output.firstRow)` |

> `@empty(...)` returns `true` if the Lookup found no matching row (file is new), `false` if a row exists (duplicate).

Now click into the **True** and **False** branches to add activities inside each.

---

### 4.4.3a True branch: `Copy CSV to Eventhouse`

Click the ✏️ **pencil icon** on the **True** branch to open it.

1. **Activities** tab → **Copy data** → **Add copy data activity** (the third option — you need the full activity, not the wizard or copy job).

**General tab:**

| Setting | Value |
|---|---|
| Name | `Copy CSV to Eventhouse` |
| Retry | `3` |
| Retry interval (sec) | `60` |

**Source tab:**

| Setting | Value |
|---|---|
| Connection | *(select the ADLS Gen2 connection created in 4.4.1)* |
| File path — Container | `intraday-deposits` |
| File path — Directory | **Add dynamic content** → `@pipeline().parameters.pFolder` |
| File path — File name | **Add dynamic content** → `@coalesce(pipeline()?.TriggerEvent?.FileName, pipeline().parameters.pFileName)` |
| File format | **DelimitedText** |
| First row as header | ✅ Checked |

**Additional columns** (scroll down in the Source tab → **Additional columns** section → click **+ New** four times):

| Name | Value |
|---|---|
| `load_ts` | **Add dynamic content** → `@variables('vLoadTs')` |
| `file_name` | **Add dynamic content** → `@coalesce(pipeline()?.TriggerEvent?.FileName, pipeline().parameters.pFileName)` |
| `pipeline_name` | **Add dynamic content** → `@pipeline().Pipeline` |
| `pipeline_runid` | **Add dynamic content** → `@pipeline().RunId` |

> These four columns are **not** in the CSV — they're injected by the pipeline to provide lineage. Every row ingested will have these values.

**Destination tab:**

| Setting | Value |
|---|---|
| Connection | Click **+ New** → search for **KQL Database** → select your `DepositMovement` KQL database |
| Table | `DepositMovement` (select from the dropdown) |
| Ingestion mapping name | Type `DepositMovement_mapping` (this is a **free-text field** below the Advanced section — not a dropdown. Type the name exactly.) |

> 💡 **Optional — `ingest-by` tag:** The Additional properties section (`+ New`) can accept a KQL `ingest-by` tag as a third dedup layer. This is an advanced optimization — skip it for now. The pipeline already has two dedup layers (Lookup + If Condition), which are sufficient. You can add `ingest-by` later if needed.

**Mapping tab:**

> **Skip this tab.** Since you specified `DepositMovement_mapping` in the Destination tab, KQL handles column mapping server-side. The **Import schemas** button will fail here because the Source file path uses dynamic expressions that can't be resolved at design time — this is normal. Leave the Mapping tab empty.

**Settings tab:**

> No changes needed on this tab. Leave defaults.

---

### 4.4.3b True branch: `Append Success` (audit on Copy success)

Still inside the **True** branch:

1. **Activities** tab → click **Script** (not "Stored procedure").
2. Drag a **green arrow** (On Success) from `Copy CSV to Eventhouse` → `Append Success`.

**General tab:**

| Setting | Value |
|---|---|
| Name | `Append Success` |

**Settings tab:**

| Setting | Value |
|---|---|
| Connection | Select the **Warehouse** connection → `wh_control_framework` |
| Script type | **NonQuery** |
| Script | **Add dynamic content** → paste the following: |

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

---

### 4.4.3c True branch: `Append Failed` (audit on Copy failure)

1. **Activities** tab → click **Script**.
2. Drag a **red arrow** (On Failure) from `Copy CSV to Eventhouse` → `Append Failed`.

   > To create a failure dependency: click the **green arrow** from Copy, then in the arrow's dropdown change the condition from **On Success** to **On Failure** (red).

**General tab:**

| Setting | Value |
|---|---|
| Name | `Append Failed` |

**Settings tab:**

| Setting | Value |
|---|---|
| Connection | `wh_control_framework` |
| Script type | **NonQuery** |
| Script | **Add dynamic content** → paste the following: |

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
    '@{replace(activity(''Copy CSV to Eventhouse'').error.message,'''','''''')}'
);
```

---

### 4.4.3d True branch: `Recalculate Gold Summary` (KQL Activity, Option A only)

> **Skip this activity if you chose Option B** (materialized view) in Workshop 03 — the KQL engine handles Gold aggregation automatically.

1. **Activities** tab → click **KQL** (or search for "KQL").
2. Drag a **green arrow** (On Success) from `Append Success` → `Recalculate Gold Summary`.

**General tab:**

| Setting | Value |
|---|---|
| Name | `Recalculate Gold Summary` |

**Settings tab:**

| Setting | Value |
|---|---|
| Connection | Click **+ New** → **KQL Database** → select your `DepositMovement` KQL database |
| Command type | **KQL Command** |
| Command | **Add dynamic content** → paste: |

```kusto
.set-or-append Summary_Alert_Channel <| sp_Recalculate_Summary_Alert_Channel(datetime(@{variables('vLoadTs')}))
```

> This passes the exact `vLoadTs` timestamp to the stored function. The function finds rows with that `load_ts`, gets their distinct dates, and re-aggregates only those dates into the Gold table.

Now click the **← Back** arrow (top-left of the True branch) to return to the main canvas.

---

### 4.4.3e False branch: `Append Skipped-Duplicate`

Click the ✏️ **pencil icon** on the **False** branch to open it.

1. **Activities** tab → click **Script**.

**General tab:**

| Setting | Value |
|---|---|
| Name | `Append Skipped-Duplicate` |

**Settings tab:**

| Setting | Value |
|---|---|
| Connection | `wh_control_framework` |
| Script type | **NonQuery** |
| Script | **Add dynamic content** → paste the following: |

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

Click **← Back** to return to the main canvas.

> 💡 **Why Script, not Stored Procedure?** The Fabric **Script** activity lets you run inline SQL directly. **Stored Procedure** activity requires a pre-created proc in the Warehouse. Since each audit is a single INSERT statement, inline Script is simpler — no extra Warehouse objects to manage.

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

---

## Appendix A — Why `@utcNow()` and not Thailand time?

`@utcNow()` returns **UTC** (Coordinated Universal Time), which is **Thailand time − 7 hours**.

| Time zone | Example |
|---|---|
| **UTC** (`@utcNow()`) | `2026-04-25T10:00:00Z` |
| **Thailand** (ICT, UTC+7) | `2026-04-25T17:00:00` |

You *could* use `@addHours(utcNow(), 7)` to store Thailand time, but **don't** — here's why:

| Concern | `@utcNow()` (UTC) ✅ | `@addHours(utcNow(), 7)` (Thailand) ❌ |
|---|---|---|
| **KQL `datetime` functions** | Work correctly — KQL assumes UTC | **Wrong** — KQL treats the value as UTC, so `bin(load_ts, 1d)` groups by Thailand midnight but KQL thinks it's UTC midnight |
| **`ago(1h)` in KQL queries** | Correct | **Off by 7 hours** — KQL compares against real UTC `now()` |
| **Cross-system joins** | Matches other Fabric timestamps | **Mismatches** — Fabric internals (pipeline start time, audit logs) are all UTC |
| **Power BI time intelligence** | Easy to shift for display | Already shifted — risk of **double-shift** if someone adds +7 again in DAX |

### Best practice: store UTC, display local

Keep the pipeline as-is (`@utcNow()`). In your **Power BI report**, convert to Thailand time at the presentation layer:

**DAX calculated column:**

```dax
ThailandTime = [load_ts] + TIME(7, 0, 0)
```

**KQL query (ad-hoc):**

```kusto
DepositMovement
| extend ThailandTime = load_ts + 7h
```

This way your data is clean and correct everywhere, and Thailand time is shown only where humans read it.

---

## Appendix B — Parameters vs Variables

| | **Parameters** | **Variables** |
|---|---|---|
| **Set by** | Caller (trigger, manual run, parent pipeline) | Activities inside the pipeline (`Set Variable`) |
| **When** | Before the run starts — **immutable** once running | During the run — **can be updated** multiple times |
| **Direction** | Input from outside → pipeline | Internal to the pipeline |
| **Use case** | `pFileName`, `pFolder` — values the trigger passes in | `vLoadTs` — computed at runtime via `@utcNow()` |

**Simple rule:** outside value → **parameter**, pipeline computes it → **variable**.

### In this pipeline

| Name | Type | Why |
|---|---|---|
| `pFileName` | Parameter | The event trigger (or manual run) tells the pipeline *which file* to process. Read-only during execution. |
| `pFolder` | Parameter | The trigger tells the pipeline *which folder* to look in. Defaults to `incoming`. |
| `vLoadTs` | Variable | The pipeline captures `@utcNow()` at the start via the `Set vLoadTs` activity, then reuses that same timestamp in Copy (`load_ts` column) and KQL (`sp_Recalculate_Summary_Alert_Channel`) — ensuring they always match. |

---

## Appendix C — Timezone Strategy (UTC vs Thailand Time)

### Does Fabric have a workspace-level timezone setting?

**No.** Fabric has **no workspace-level timezone configuration**. All internal timestamps — pipeline run times, audit logs, refresh history, KQL `now()` — are **always UTC**. This cannot be changed.

### What if I store `load_ts` as UTC+7 (Thailand time)?

You *could* change `vLoadTs` from `@utcNow()` to `@addHours(utcNow(), 7)`, but it causes cascading issues across the workshops:

| Module | Impact | Severity |
|---|---|---|
| **Workshop 02 — KQL `DepositMovement`** | `load_ts` stores UTC+7, but KQL treats it as UTC. `ago(1h)` queries return wrong results. | **Breaking** |
| **Workshop 03A — Stored function** | Exact match still works, but Gold table timestamps are UTC+7 while KQL `now()` is UTC. Any `where load_ts > ago(...)` query breaks. | **Breaking** |
| **Workshop 03B — Materialized view** | `max(load_ts)` as `UpdatedAtUtc` now stores UTC+7 — column name is misleading. Freshness comparisons against `now()` are off by 7 hours. | **Confusing** |
| **Workshop 04 — ProcessedFiles audit** | `IngestedAtUtc` (from `SYSUTCDATETIME()`) is real UTC, but `load_ts` in KQL is UTC+7. Two different "times" for the same event. | **Confusing** |
| **Workshop 07 — Power BI** | Timestamps display as Thailand time (good!), but if someone adds +7 in DAX (standard practice), they get UTC+14. | **Breaking** |
| **Workshop 08 — Activator alerts** | Alert conditions comparing against KQL `now()` are off by 7 hours. Alerts fire late or early. | **Breaking** |
| **Workshop 09 — Monitoring** | Cross-referencing pipeline run times (UTC) with `load_ts` (UTC+7) creates confusion during incident triage. | **Confusing** |

### Recommended approach: store UTC, convert at display

Keep the pipeline as-is (`@utcNow()`). Convert to Thailand time only where humans read it:

**Power BI (Workshop 07) — DAX calculated column:**

```dax
ThailandTime = [load_ts] + TIME(7, 0, 0)
```

Use `ThailandTime` in visuals; keep `load_ts` for relationships and calculations.

**KQL queries (ad-hoc exploration):**

```kusto
DepositMovement
| extend ThailandTime = load_ts + 7h
| project ThailandTime, AccountNo, Channel, Amount_THB
```

**Activator alert messages (Workshop 08):**

```kusto
// Inside Activator KQL condition
| extend AlertTime_TH = format_datetime(load_ts + 7h, 'yyyy-MM-dd HH:mm')
```

> **Rule of thumb:** Store UTC everywhere → convert to `+7h` only where humans see it. This keeps all 9 workshops consistent and avoids cascading bugs.
