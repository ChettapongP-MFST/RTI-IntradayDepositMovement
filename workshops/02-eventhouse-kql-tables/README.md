# Workshop 02 — Eventhouse (KQL) + Warehouse (Control Table)

Create two Fabric items:

1. An **Eventhouse / KQL Database** for the hot-path business table `DepositMovement` (low-latency ingestion & query).
2. A **Fabric Warehouse** for the audit/control table `dbo.ProcessedFiles` (T-SQL friendly, easy to join in Power BI, decoupled from the hot path).

**Prerequisite:** [Workshop 01](../01-provision-adls-gen2/) complete
**Next:** [Workshop 03 — Trusted Workspace Access](../03-trusted-workspace-access/)

---

## 2.1 Create the Eventhouse

1. Open the Fabric workspace (from Workshop 00.3).
2. **+ New item** → **Eventhouse** → name it `eh-rti-deposit`.
3. Inside the Eventhouse, the default KQL Database is created. Create (or rename to) a KQL Database named `DepositMovement`.

## 2.2 Create the business table (KQL)

Open the KQL Database → **Query** pane and run:

- [kql/01-create-DepositMovement.kql](kql/01-create-DepositMovement.kql)

This script does **three things**. Let's walk through each one before you execute.

### 2.2.1 Table creation (16 columns)

The table has 16 columns split into **data columns** (from the CSV) and **system columns** (injected by the pipeline):

| Category | Type | Columns | Description |
|---|---|---|---|
| Grain | **Data column** | `Date`, `Time` | Business date and 30-minute time slot (e.g., `00:00-00:30`) |
| Dimensions | **Data column** | `Product`, `Channel`, `Channel_Group`, `Transaction_Type` | Slicing attributes for analysis |
| Measures | **Data column** | `Credit_Amount`, `Debit_Amount`, `Net_Amount`, `Credit_Txn`, `Debit_Txn`, `Total_Txn` | Numeric values for aggregation |
| Lineage | **System column** | `load_ts`, `file_name`, `pipeline_name`, `pipeline_runid` | Metadata injected by the Data Pipeline — not in the source CSV |

### 2.2.2 CSV ingestion mapping (`DepositMovement_mapping`)

The mapping tells KQL **which CSV column position (ordinal) maps to which table column**. This is necessary because:

- **The source CSV files have only 12 data columns**, but the table has 16 (12 data + 4 system).
- **The 4 system columns** (`load_ts`, `file_name`, `pipeline_name`, `pipeline_runid`) don't exist in the CSV — they are **appended by the Data Pipeline's Copy Activity** (Workshop 04) using "Additional columns".
- The mapping ensures:
  - **Ordinals 0–11** → **data columns** (from the CSV file)
  - **Ordinals 12–15** → **system columns** (injected by the pipeline)

| Ordinal | Column | Type | Source |
|---|---|---|---|
| 0–11 | `Date` … `Total_Txn` | Data column | CSV file content |
| 12 | `load_ts` | System column | Pipeline expression `utcNow()` |
| 13 | `file_name` | System column | `$$FILEPATH` (source blob path) |
| 14 | `pipeline_name` | System column | `@pipeline().Pipeline` |
| 15 | `pipeline_runid` | System column | `@pipeline().RunId` |

Without this mapping, KQL would auto-infer column positions and types, causing the 4 system columns to fail silently or land in wrong columns.

The mapping is saved as `'DepositMovement_mapping'` — this name is referenced later in the Copy Activity sink configuration (Workshop 04).

### 2.2.3 Streaming ingestion policy

```
.alter-merge database DepositMovement policy streamingingestion '{ "IsEnabled": true }'
.alter table DepositMovement policy streamingingestion enable
```

By default, KQL uses **batched ingestion** which buffers rows for 1–5 minutes before they become queryable. Enabling **streaming ingestion** makes data available in **seconds**.

| | Batched (default) | Streaming (enabled) |
|---|---|---|
| **Latency** | 1–5 minutes | Seconds |
| **Use case** | Bulk historical loads | Real-time dashboards & alerts |

Two commands are needed because streaming must be enabled at both the **database level** (prerequisite) and the **table level**.

This is critical for the workshop — you want intraday deposit data to appear in Power BI and Activator alerts as soon as each 30-minute file is ingested.

### 2.2.4 Retention & caching policy

```
.alter table DepositMovement policy retention '{ "SoftDeletePeriod": "365.00:00:00", "Recoverability": "Enabled" }'
.alter table DepositMovement policy caching hot = 90d
```

These policies control **how long data lives** and **how fast queries run**:

| Policy | Setting | Effect |
|---|---|---|
| **Retention** | `SoftDeletePeriod: 365 days` | Data older than 1 year is auto-deleted. `Recoverability: Enabled` allows recovery within a grace period. |
| **Caching** | `hot = 90d` | Last 90 days kept in **hot cache** (SSD/RAM) for fast queries. Older data moves to **cold storage** (slower but still queryable). |

**Data lifecycle:**

```
Today ◄─── 90 days ───► Hot cache (fast queries)
       ◄── 365 days ──► Cold storage (slower, still accessible)
       Beyond 365 days → Deleted automatically
```

> 💡 **Tune to your needs** — for a workshop/POC, these defaults work well. In production, adjust based on query patterns and cost requirements.


1. Fabric workspace → **+ New item** → **Warehouse** → name it `wh_control_framework` → **Create**.
2. Once provisioned, open the Warehouse and click **New SQL query**.

## 2.4 Create the audit/control table (T-SQL)

This table acts as a **deduplication and audit log** for the Data Pipeline. Every time a CSV file is ingested, the pipeline writes a row here recording:
- **Which file** was processed (`FileName`)
- **When** it was ingested (`IngestedAtUtc`)
- **How many rows** were copied (`RowCount_`)
- **Whether it succeeded or failed** (`Status`)
- **Pipeline metadata** for traceability

Before ingesting a new file, the pipeline checks this table to see if the file has already been processed — preventing duplicate loads. If a run fails, the error message is captured in `ErrorMsg` for troubleshooting.

Paste and run the script:

- [sql/02-create-ProcessedFiles.sql](sql/02-create-ProcessedFiles.sql)

Schema:

| Column | Type | Purpose |
|---|---|---|
| `FileName` | VARCHAR(260) | Natural key for dedup |
| `IngestedAtUtc` | DATETIME2(3) | When the row was written |
| `RowCount_` | BIGINT | Rows copied by the pipeline *(trailing `_` — `ROWCOUNT` is reserved in T-SQL)* |
| `Status` | VARCHAR(32) | `Success` / `Failed` / `Skipped-Duplicate` |
| `PipelineName` | VARCHAR(200) | `@pipeline().Pipeline` |
| `PipelineRunId` | VARCHAR(64) | `@pipeline().RunId` |
| `RunAsUser` | VARCHAR(200) | Trigger type + name |
| `ErrorMsg` | VARCHAR(4000) | Copy Activity error (if any) |

Verify:

```sql
SELECT TOP (1) * FROM dbo.ProcessedFiles;
SELECT COUNT(*) AS Rows_ FROM dbo.ProcessedFiles;
```

## 2.5 Verify streaming ingestion is enabled

After running the script in step 2.2, streaming ingestion should already be enabled. Use these commands to **confirm** it was applied correctly:

In the KQL Database query pane:

```kusto
.show database DepositMovement policy streamingingestion
.show table DepositMovement policy streamingingestion
```

(Warehouses don't have a streaming-ingestion policy — writes via pipeline `Script` / `Stored procedure` activity are sufficient for a per-file audit row.)

## 2.6 Create the Gold table (Summary_Alert_Channel)

This is the **aggregated "Gold" layer** in a Medallion Architecture pattern:

```
Bronze (DepositMovement table) ──► Stored Procedure / Policy ──► Gold (Summary_Alert_Channel)
```

While `DepositMovement` stores **granular, row-level data** (per product, per channel, per time slot), this Gold table stores **daily channel-level summaries** — pre-aggregated for:

- **Power BI reports** — dashboards query this table instead of scanning millions of raw rows, resulting in faster report load times
- **Activator alerts** (Workshop 08) — threshold-based alerting on daily net amounts or transaction counts per channel

The table is **not populated during creation** — it will be filled by the stored procedure below (step 2.7), which the Data Pipeline calls after each ingestion.

Run in the KQL Database → **Query** pane:

- [kql/03-create-Summary_Alert_Channel.kql](kql/03-create-Summary_Alert_Channel.kql)

Schema:

| Column | Type | Purpose |
|---|---|---|
| `Date` | datetime | Business date (e.g., 2026-04-24) |
| `Channel` | string | Channel dimension |
| `Credit_Total` | real | Sum of Credit_Amount for that date+channel |
| `Debit_Total` | real | Sum of Debit_Amount for that date+channel |
| `Net_Amount` | real | Net (Credit - Debit) |
| `Txn_Count` | real | Count of transactions |
| `UpdatedAtUtc` | datetime | When the summary was last recalculated |

## 2.7 Create the Stored Procedure (Incremental Recalculation)

This stored procedure is the **engine behind the Gold table**. Rather than re-aggregating the entire `DepositMovement` table every time (which would be expensive), it uses an **incremental approach**:

```
New CSV file arrives
  └─► Pipeline ingests into DepositMovement (Silver)
       └─► Pipeline calls this stored procedure
            └─► Procedure finds which dates were just loaded (last 15 min)
                 └─► Re-aggregates ONLY those dates into Summary_Alert_Channel (Gold)
```

**Why incremental?**
- As data grows, a full re-aggregation would scan millions of rows every 30 minutes
- Incremental recalculation touches only the affected dates, keeping execution fast and resource-efficient

**How it works step by step:**

1. **Find recent dates** — Queries `DepositMovement` for records with `IngestedAtUtc >= ago(15m)` and extracts the distinct `Date` values
2. **Aggregate by Channel** — For each of those dates, sums up `Credit_Amount`, `Debit_Amount`, `Net_Amount`, and `Total_Txn` grouped by `Date` + `Channel`
3. **Upsert into Gold** — Inserts (or updates) the aggregated rows into `Summary_Alert_Channel` with a fresh `UpdatedAtUtc` timestamp

Run in the KQL Database → **Query** pane:

- [kql/04-sp-Recalculate-Summary_Alert_Channel.kql](kql/04-sp-Recalculate-Summary_Alert_Channel.kql)

**Logic:**

1. Find distinct dates from records ingested in the **last 15 minutes** (`IngestedAtUtc >= ago(15m)`)
2. For each of those dates, aggregate `DepositMovement` by `Channel`
3. Upsert the result into `Summary_Alert_Channel` (Gold table)

**Test manually:**

```kusto
// Run the procedure
exec sp_Recalculate_Summary_Alert_Channel;

// Check results
Summary_Alert_Channel | order by Date desc, Channel | limit 20
```

## ✅ Exit Criteria

- [ ] Eventhouse + KQL Database `DepositMovement` exist, with the 16-column `DepositMovement` table + `DepositMovement_mapping`
- [ ] Streaming ingestion enabled on `DepositMovement`
- [ ] Warehouse `wh_control_framework` exists
- [ ] Table `dbo.ProcessedFiles` exists with 8 columns; empty `SELECT` returns no rows
- [ ] Gold table `Summary_Alert_Channel` exists with 7 columns
- [ ] Stored procedure `sp_Recalculate_Summary_Alert_Channel` exists

→ Proceed to **[Workshop 03 — Trusted Workspace Access](../03-trusted-workspace-access/)**
