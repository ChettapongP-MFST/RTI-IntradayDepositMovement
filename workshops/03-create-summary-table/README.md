# Workshop 03 — Create the Summary Table

Create the **Gold aggregation layer** — a pre-aggregated summary table that stores daily channel-level summaries of deposit movements.

```
Bronze (DepositMovement table) ──► Stored Procedure / Materialized View ──► Gold (Summary_Alert_Channel)
```

There are **two options** to build this. Choose one:

| | Option A — Stored Function | Option B — Materialized View |
|---|---|---|
| **Mechanism** | Pipeline calls `.set-or-append` with a stored function after each ingestion | KQL engine auto-aggregates as new data arrives |
| **Trigger** | Explicit — pipeline must call `.set-or-append <| sp_...()` | Automatic — runs in the background, no pipeline step needed |
| **Pipeline change** | Requires a "KQL Activity" step in the pipeline (Workshop 04) | No pipeline change needed |
| **Latency** | Seconds after pipeline calls the function | Near-real-time (KQL processes new extents automatically) |
| **Custom logic** | Full KQL flexibility (windowing, filtering, complex joins) | Limited to `summarize` aggregation functions |
| **Ops overhead** | Must ensure pipeline calls the function on every run | Zero — KQL manages it autonomously |
| **Best for** | Complex transformation logic, conditional recalculation | Simple aggregations that should always stay up to date |

> 💡 **Workshop default:** This workshop uses **Option A** in the pipeline (Workshop 04). If you prefer Option B, you can skip the "KQL Activity" step in the pipeline and let the materialized view handle it automatically.

**Prerequisite:** [Workshop 02](../02-eventhouse-kql-tables/) complete (Eventhouse + KQL Database + `DepositMovement` table exist)
**Next:** [Workshop 04 — Data Pipeline](../04-data-pipeline/)

---

## 3.1 Gold table schema (Summary_Alert_Channel)

Both options produce the same Gold table. While `DepositMovement` stores **granular, row-level data** (per product, per channel, per time slot), this Gold table stores **daily channel-level summaries** — pre-aggregated for:

- **Power BI reports** — dashboards query this table instead of scanning millions of raw rows, resulting in faster report load times
- **Activator alerts** (Workshop 08) — threshold-based alerting on daily net amounts or transaction counts per channel

| Column | Type | Purpose |
|---|---|---|
| `Date` | datetime | Business date (e.g., 2026-04-24) |
| `Channel` | string | Channel dimension |
| `Credit_Total` | real | Sum of Credit_Amount for that date+channel |
| `Debit_Total` | real | Sum of Debit_Amount for that date+channel |
| `Net_Amount` | real | Net (Credit - Debit) |
| `Txn_Count` | real | Count of transactions |
| `UpdatedAtUtc` | datetime | When the summary was last recalculated |

---

## Option A — Stored Function (Incremental Recalculation)

### 3.A1 Create the Gold table

The table is **not populated during creation** — it will be filled by the stored function (step 3.A2), which the Data Pipeline calls after each ingestion.

Run in the KQL Database → **Query** pane:

- [kql/03-create-Summary_Alert_Channel.kql](kql/03-create-Summary_Alert_Channel.kql)

### 3.A2 Create the Stored Function

This stored function is the **engine behind the Gold table**. Rather than re-aggregating the entire `DepositMovement` table every time (which would be expensive), it uses an **incremental approach**:

```
New CSV file arrives
  └─► Pipeline ingests into DepositMovement (Bronze)
       └─► Pipeline calls .set-or-append with this function
            └─► Function finds which dates were just loaded (last 15 min)
                 └─► Re-aggregates ONLY those dates → appended to Summary_Alert_Channel (Gold)
```

**Why incremental?**
- As data grows, a full re-aggregation would scan millions of rows every 30 minutes
- Incremental recalculation touches only the affected dates, keeping execution fast and resource-efficient

### Step-by-step walkthrough

#### Step 1 — Identify which dates need recalculation

```kql
let RecentDates = DepositMovement
    | where IngestedAtUtc >= ago(15m)
    | distinct Date;
```

| Part | What it does |
|---|---|
| `let RecentDates =` | Stores the result as a reusable variable |
| `where IngestedAtUtc >= ago(15m)` | Filters to rows ingested in the **last 15 minutes** — this catches the batch that just landed |
| `distinct Date` | Extracts the unique business dates from those rows |

**Example:** If the pipeline just ingested a file containing rows for `2026-04-24` and `2026-04-25`, `RecentDates` will contain exactly those two dates.

**Why 15 minutes?** The pipeline runs every 10–30 minutes. A 15-minute window provides enough buffer to capture the current batch without picking up stale data from much earlier runs.

#### Step 2 — Re-aggregate only those dates

```kql
RecentDates
| join kind=inner DepositMovement on Date
```

| Part | What it does |
|---|---|
| `join kind=inner` | Joins `RecentDates` back to the **full** `DepositMovement` table |
| `on Date` | Match condition — only rows whose `Date` is in the recent batch |

**Why join back to the full table?** Because we want to re-aggregate **all rows for those dates** (not just the new rows). If `2026-04-24` already had data from earlier time slots and we just added `08:00-08:30`, the summary should reflect the entire day so far.

#### Step 3 — Aggregate by Date + Channel

```kql
| summarize 
    Credit_Total = sum(Credit_Amount),
    Debit_Total = sum(Debit_Amount),
    Net_Amount = sum(Net_Amount),
    Txn_Count = sum(Total_Txn)
    by Date, Channel
```

This collapses all granular rows (per product, per time slot, per transaction type) into **one row per Date + Channel**:

| Before (Bronze — multiple rows) | After (Gold — one row) |
|---|---|
| `2026-04-24, ATM, Fixed, On-Us, 00:00-00:30` | `2026-04-24, ATM` → totals |
| `2026-04-24, ATM, Fixed, Off-Us, 00:00-00:30` | *(merged into above)* |
| `2026-04-24, ATM, Savings, On-Us, 00:30-01:00` | *(merged into above)* |

#### Step 4 — Add timestamp and return

```kql
| extend UpdatedAtUtc = now()
```

Stamps each aggregated row with the current UTC time, so you can tell **when** the Gold table was last refreshed for that Date + Channel.

> **Important — Kusto design principle:** The function body is a **pure query** — it returns a result set but does not write anything. Fabric Eventhouse does not support `.create procedure` or `insert into` inside function bodies. The write happens externally via `.set-or-append` (see below).

### How the function is called

The function alone **returns** the aggregated rows but does not write them. To append the results into the Gold table:

```kusto
.set-or-append Summary_Alert_Channel <| sp_Recalculate_Summary_Alert_Channel()
```

| Part | What it does |
|---|---|
| `.set-or-append` | Management command that writes a query's result set into a table (creates it if it doesn't exist) |
| `Summary_Alert_Channel` | Target Gold table |
| `<\|` | "Pipe from query" operator — feeds the function's output into the write command |
| `sp_Recalculate_Summary_Alert_Channel()` | The function call — returns the aggregated rows |

> **Note:** This is an **append**, not an upsert/merge. Each recalculation appends new summary rows. If the same Date + Channel is recalculated multiple times, multiple rows will exist — the latest one (by `UpdatedAtUtc`) is the most current. Downstream queries/reports should filter by the latest `UpdatedAtUtc` per Date + Channel, or the table should be periodically deduplicated.

### Visual flow

```
Pipeline ingests mock_0800_0830.csv (contains Date = 2026-04-24)
  │
  ▼
Step 1: RecentDates = [2026-04-24]
  │
  ▼
Step 2: Join back → get ALL rows for 2026-04-24 (00:00 through 08:30)
  │
  ▼
Step 3: Summarize → one row per Channel (ATM, BCMS, ENET, ...)
  │
  ▼
Step 4: Stamp UpdatedAtUtc = 2026-04-24T08:31:00Z
  │
  ▼
Function returns result set → .set-or-append writes to Summary_Alert_Channel (Gold)
```

### Design rationale

| Concern | How it's handled |
|---|---|
| **Performance** | Only recalculates affected dates, not the entire history |
| **Correctness** | Re-aggregates the full day (not just new rows), so totals are always accurate |
| **Simplicity** | Single function, called once per pipeline run via `.set-or-append` |
| **Testability** | Call `sp_Recalculate_Summary_Alert_Channel()` alone to preview results without writing |
| **Freshness tracking** | `UpdatedAtUtc` lets Power BI / Activator know when data was last refreshed |

### Run the script

Open the KQL Database → **Query** pane and run:

- [kql/04-sp-Recalculate-Summary_Alert_Channel.kql](kql/04-sp-Recalculate-Summary_Alert_Channel.kql)

**Test manually:**

```kusto
// Preview what would be inserted (no write)
sp_Recalculate_Summary_Alert_Channel()

// Actually append into the Gold table
.set-or-append Summary_Alert_Channel <| sp_Recalculate_Summary_Alert_Channel()

// Check results
Summary_Alert_Channel | order by Date desc, Channel | limit 20
```

---

## Option B — Materialized View (Automatic Aggregation)

A **materialized view** is a KQL object that automatically and incrementally aggregates data from a source table. Every time new data is ingested into `DepositMovement`, the KQL engine processes **only the new extents (data batches)** and updates the materialized view — no pipeline step or stored function call needed.

```
New CSV file arrives
  └─► Pipeline ingests into DepositMovement (Bronze)
       └─► KQL engine detects new extents automatically
            └─► Materialized view incrementally aggregates new data
                 └─► Summary_Alert_Channel_MV is always up to date
```

### How it differs from Option A

| Aspect | Option A (Stored Function) | Option B (Materialized View) |
|---|---|---|
| **When does it run?** | Only when the pipeline calls `.set-or-append <\| sp_...()` | Automatically after every ingestion |
| **What does it process?** | All rows for the affected dates (full-day re-aggregation) | Only new extents (truly incremental) |
| **Deduplication** | Appends rows — needs `UpdatedAtUtc` filtering | Maintains a single row per `Date` + `Channel` |
| **Pipeline dependency** | Pipeline must include a KQL Activity step | No pipeline change needed |
| **Failure recovery** | If the pipeline step fails, Gold table is stale | KQL retries automatically |

### 3.B1 Create the Materialized View

Run in the KQL Database → **Query** pane:

- [kql/05-create-Summary_Alert_Channel_MV.kql](kql/05-create-Summary_Alert_Channel_MV.kql)

The script creates:

```kql
.create materialized-view with (backfill=true) Summary_Alert_Channel_MV on table DepositMovement
{
    DepositMovement
    | summarize 
        Credit_Total = sum(Credit_Amount),
        Debit_Total  = sum(Debit_Amount),
        Net_Amount   = sum(Net_Amount),
        Txn_Count    = sum(Total_Txn)
        by Date, Channel
}
```

#### Key parts explained

| Part | What it does |
|---|---|
| `.create materialized-view` | Creates a persistent aggregated view managed by KQL |
| `with (backfill=true)` | Processes **all existing data** in `DepositMovement` immediately (not just future ingestions). Remove this if the table is empty at creation time. |
| `on table DepositMovement` | Binds the view to the source table — KQL watches this table for new data |
| `summarize ... by Date, Channel` | The aggregation query — same logic as the stored procedure, but KQL runs it automatically |

#### How KQL processes it internally

1. **Initial backfill** — When created with `backfill=true`, KQL aggregates all existing rows in `DepositMovement` into the view
2. **Incremental updates** — After each ingestion, KQL identifies the new **extents** (data batches) and runs the `summarize` query on only those rows
3. **Merge** — New aggregations are merged with existing results. For `sum()`, this means adding the new values to the existing totals for the same `Date` + `Channel`
4. **Single row per key** — Unlike Option A (which appends), the materialized view maintains exactly **one row per `Date` + `Channel`**

#### No `UpdatedAtUtc` column

The materialized view does not include `UpdatedAtUtc` because:
- KQL manages the freshness internally — you can check the view's materialization lag
- Adding `now()` inside a materialized view would prevent proper merging (each extent would produce a different timestamp)

To check the view's materialization status:

```kusto
.show materialized-view Summary_Alert_Channel_MV
```

The `MaterializedTo` column shows the last timestamp up to which data has been processed.

### 3.B2 Query the materialized view

Query it just like a regular table:

```kusto
Summary_Alert_Channel_MV
| order by Date desc, Channel
| limit 20
```

To check materialization health and lag:

```kusto
// View status (MaterializedTo, IsHealthy, etc.)
.show materialized-view Summary_Alert_Channel_MV

// Check how far behind the view is
.show materialized-view Summary_Alert_Channel_MV statistics
```

### When to choose Option B

- You want a **zero-ops** Gold layer — no pipeline step to manage
- Your aggregation is a straightforward `summarize` (sum, count, min, max, avg)
- You prefer a single row per key (no deduplication needed)
- You want the Gold table to update even during ad-hoc ingestions (not just pipeline runs)

### When to stick with Option A

- You need **complex transformation logic** beyond simple aggregation (e.g., conditional recalculation, windowing, multi-table joins)
- You want explicit control over when the Gold table updates
- You need `UpdatedAtUtc` for freshness tracking in downstream reports
- You want to log/audit each recalculation run

---

## ✅ Exit Criteria

**If you chose Option A:**
- [ ] Gold table `Summary_Alert_Channel` exists with 7 columns
- [ ] Stored function `sp_Recalculate_Summary_Alert_Channel` exists (verify: `.show functions sp_Recalculate_Summary_Alert_Channel`)

**If you chose Option B:**
- [ ] Materialized view `Summary_Alert_Channel_MV` exists and is healthy
- [ ] `backfill=true` processed existing data (if any)

→ Proceed to **[Workshop 04 — Data Pipeline](../04-data-pipeline/)**
