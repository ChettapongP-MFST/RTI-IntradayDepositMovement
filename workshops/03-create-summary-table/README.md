# Workshop 03 — Create the Summary Table

Create the **Gold aggregation layer** — a pre-aggregated summary table that stores per-time-window channel-level summaries of deposit movements.

```
Bronze (DepositMovement table) ──► Stored Procedure / Materialized View ──► Gold (Summary_Alert_Channel)
```

There are **two options** to build this. Choose one:

| | Option A — Stored Function | Option B — Materialized View |
|---|---|---|
| **Mechanism** | Pipeline calls `.set-or-append` with a stored function | KQL auto-aggregates as new data arrives |
| **Gold table name** | `Summary_Alert_Channel` (regular table) | `Summary_Alert_Channel_MV` (view) |
| **Schema** | 8 columns (incl. `Time` + `UpdatedAtUtc` via `now()`) | 8 columns (incl. `Time` + `UpdatedAtUtc` via `max(load_ts)`) |
| **Trigger** | Explicit — pipeline must call `.set-or-append <\| sp_...()` | Automatic — runs in the background, no pipeline step needed |
| **Pipeline change** | Requires a "KQL Activity" step (Workshop 04) | No pipeline change needed |
| **Rows per Date+Time+Channel** | Multiple (appends each run — needs dedup) | Single (auto-merged) |
| **Freshness tracking** | `UpdatedAtUtc = now()` — exact recalc time | `UpdatedAtUtc = max(load_ts)` — latest pipeline load time |
| **Custom logic** | Full KQL flexibility (windowing, filtering, complex joins) | Limited to `summarize` aggregation functions |
| **Ops overhead** | Must ensure pipeline calls function on every run | Zero — KQL manages it autonomously |
| **Best for** | Complex transformation logic, conditional recalculation | Simple aggregations that should always stay up to date |

### What the Gold table looks like (after two pipeline runs)

Assume the pipeline has run twice: **07:00-07:30** then **08:00-08:30**. Here's what each option produces:

#### Option A — Stored Function (appends rows each run)

The table **grows** with each pipeline run. Stale rows from earlier runs remain; downstream queries must filter by the latest `UpdatedAtUtc`.

```
Summary_Alert_Channel (regular table)
┌──────────┬─────────────┬─────────┬──────────────┬──────────────┐
│  Date    │ Time        │ Channel │ Credit_Total │ UpdatedAtUtc │
├──────────┼─────────────┼─────────┼──────────────┼──────────────┤
│  Day 5   │ 00:00-00:30 │ ATM     │       50,000 │ 07:31 (stale)│  ← from 07:00-07:30 run
│  Day 5   │ 00:00-00:30 │ BCMS    │       30,000 │ 07:31 (stale)│
│  Day 5   │ 00:00-00:30 │ ENET    │       20,000 │ 07:31 (stale)│
│  Day 5   │ 00:00-00:30 │ ATM     │       65,000 │ 08:31 (latest) ✅│  ← from 08:00-08:30 run
│  Day 5   │ 00:00-00:30 │ BCMS    │       38,000 │ 08:31 (latest) ✅│
│  Day 5   │ 00:00-00:30 │ ENET    │       27,000 │ 08:31 (latest) ✅│
└──────────┴─────────────┴─────────┴──────────────┴──────────────┘
                                                    6 rows (grows every run)
```

> ⚠️ To get the correct current totals, downstream queries must pick the **latest row** per Date+Time+Channel:
> ```kusto
> Summary_Alert_Channel
> | summarize arg_max(UpdatedAtUtc, *) by Date, Time, Channel
> ```

#### Option B — Materialized View (single row, with timestamp)

The view **auto-merges** — always one row per Date+Time+Channel. No stale rows, no dedup needed. `UpdatedAtUtc` tracks the latest pipeline load time.

```
Summary_Alert_Channel_MV (materialized view)
┌──────────┬─────────────┬─────────┬──────────────┬──────────────────────┐
│  Date    │ Time        │ Channel │ Credit_Total │ UpdatedAtUtc         │
├──────────┼─────────────┼─────────┼──────────────┼──────────────────────┤
│  Day 5   │ 00:00-00:30 │ ATM     │       65,000 │ 08:30 (latest load)  │  ← auto-merged (50k + 15k)
│  Day 5   │ 00:00-00:30 │ BCMS    │       38,000 │ 08:30 (latest load)  │  ← auto-merged (30k + 8k)
│  Day 5   │ 00:00-00:30 │ ENET    │       27,000 │ 08:30 (latest load)  │  ← auto-merged (20k + 7k)
└──────────┴─────────────┴─────────┴──────────────┴──────────────────────┘
                           3 rows (always)
```
```

> 💡 **Workshop default:** This workshop uses **Option A** in the pipeline (Workshop 04). If you prefer Option B, skip the "KQL Activity" step in the pipeline and let the materialized view handle it automatically.

**Prerequisite:** [Workshop 02](../02-eventhouse-kql-tables/) complete (Eventhouse + KQL Database + `DepositMovement` table exist)
**Next:** [Workshop 04 — Data Pipeline](../04-data-pipeline/)

---

## 3.1 Gold table schema (Summary_Alert_Channel)

Both options produce the same Gold table. While `DepositMovement` stores **granular, row-level data** (per product, per channel, per time slot), this Gold table stores **per-time-window channel-level summaries** — pre-aggregated for:

- **Power BI reports** — dashboards query this table instead of scanning millions of raw rows, resulting in faster report load times
- **Activator alerts** (Workshop 08) — threshold-based alerting on net amounts or transaction counts per time window per channel

| Column | Type | Purpose |
|---|---|---|
| `Date` | datetime | Business date (e.g., 2026-04-24) |
| `Time` | string | Time window (e.g., `00:00-00:30`) |
| `Channel` | string | Channel dimension |
| `Credit_Total` | real | Sum of Credit_Amount for that date+time+channel |
| `Debit_Total` | real | Sum of Debit_Amount for that date+time+channel |
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
  └─► Pipeline captures vLoadTs = @utcNow()
       └─► Pipeline ingests into DepositMovement (Bronze) with load_ts = vLoadTs
            └─► Pipeline calls .set-or-append with this function, passing vLoadTs
                 └─► Function finds which dates have load_ts = vLoadTs
                      └─► Re-aggregates ONLY those dates → appended to Summary_Alert_Channel (Gold)
```

**Why incremental?**
- As data grows, a full re-aggregation would scan millions of rows every 30 minutes
- Incremental recalculation touches only the affected dates, keeping execution fast and resource-efficient

**Why parameterized?**
- The pipeline passes the exact `load_ts` it stamped on the ingested rows — no guessing with time windows like `ago(15m)`
- Works regardless of pipeline schedule (every 10 min, hourly, or on-demand)
- Eliminates the risk of missing data if the pipeline runs slower than expected

### Step-by-step walkthrough

#### Step 1 — Identify which dates need recalculation

```kql
let RecentDates = DepositMovement
    | where load_ts == pipeline_load_ts
    | distinct Date;
```

| Part | What it does |
|---|---|
| `pipeline_load_ts` | Function parameter — the exact timestamp the pipeline stamped on the rows during ingestion |
| `let RecentDates =` | Stores the result as a reusable variable |
| `where load_ts == pipeline_load_ts` | Filters to rows whose `load_ts` matches the pipeline's timestamp exactly — pinpoints the batch that just landed |
| `distinct Date` | Extracts the unique business dates from those rows |

**Example:** If the pipeline just ingested a file containing rows for `2026-04-24` and `2026-04-25` with `load_ts = 2026-04-24T08:31:00Z`, `RecentDates` will contain exactly those two dates.

**Why exact match instead of `ago(15m)`?** The pipeline passes the same `@utcNow()` value it used as `load_ts` during ingestion. This makes the function **schedule-independent** — it works whether the pipeline runs every 10 minutes, every hour, or on-demand. No risk of missing data if the pipeline runs slower than expected.

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

#### Step 3 — Aggregate by Date + Time + Channel

```kql
| summarize 
    Credit_Total = sum(Credit_Amount),
    Debit_Total = sum(Debit_Amount),
    Net_Amount = sum(Net_Amount),
    Txn_Count = sum(Total_Txn)
    by Date, Time, Channel
```

This collapses all granular rows (per product, per time slot, per transaction type) into **one row per Date + Time + Channel**:

| Before (Bronze — multiple rows) | After (Gold — one row) |
|---|---|
| `2026-04-24, 00:00-00:30, ATM, Fixed, On-Us` | `2026-04-24, 00:00-00:30, ATM` → totals |
| `2026-04-24, 00:00-00:30, ATM, Fixed, Off-Us` | *(merged into above)* |
| `2026-04-24, 00:00-00:30, ATM, Savings, On-Us` | *(merged into above)* |

#### Step 4 — Add timestamp and return

```kql
| extend UpdatedAtUtc = now()
```

Stamps each aggregated row with the current UTC time, so you can tell **when** the Gold table was last refreshed for that Date + Time + Channel.

> **Important — Kusto design principle:** The function body is a **pure query** — it returns a result set but does not write anything. Fabric Eventhouse does not support `.create procedure` or `insert into` inside function bodies. The write happens externally via `.set-or-append` (see below).

### How the function is called

The function alone **returns** the aggregated rows but does not write them. To append the results into the Gold table:

```kusto
.set-or-append Summary_Alert_Channel <| sp_Recalculate_Summary_Alert_Channel(datetime(2026-04-24T08:31:00Z))
```

| Part | What it does |
|---|---|
| `.set-or-append` | Management command that writes a query's result set into a table (creates it if it doesn't exist) |
| `Summary_Alert_Channel` | Target Gold table |
| `<\|` | "Pipe from query" operator — feeds the function's output into the write command |
| `sp_Recalculate_Summary_Alert_Channel(...)` | The function call with the pipeline's `load_ts` timestamp — returns the aggregated rows |

In the Data Pipeline (Workshop 04), the KQL Activity passes the pipeline variable:

```kusto
.set-or-append Summary_Alert_Channel <| sp_Recalculate_Summary_Alert_Channel(datetime(@{variables('vLoadTs')}))
```

> **Note:** This is an **append**, not an upsert/merge. Each recalculation appends new summary rows. If the same Date + Channel is recalculated multiple times, multiple rows will exist — the latest one (by `UpdatedAtUtc`) is the most current. Downstream queries/reports should filter by the latest `UpdatedAtUtc` per Date + Channel, or the table should be periodically deduplicated.

### Visual flow

```
Pipeline sets vLoadTs = 2026-04-24T08:31:00Z
  │
  ▼
Pipeline ingests mock_0800_0830.csv with load_ts = vLoadTs
  │
  ▼
Pipeline calls sp_Recalculate_Summary_Alert_Channel(vLoadTs)
  │
  ▼
Step 1: RecentDates = rows where load_ts == vLoadTs → distinct Date = [2026-04-24]
  │
  ▼
Step 2: Join back → get ALL rows for 2026-04-24 (00:00 through 08:30)
  │
  ▼
Step 3: Summarize → one row per Time + Channel (ATM 00:00-00:30, BCMS 00:00-00:30, ...)
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
| **Testability** | Call `sp_Recalculate_Summary_Alert_Channel(load_ts)` alone to preview results without writing |
| **Freshness tracking** | `UpdatedAtUtc` lets Power BI / Activator know when data was last refreshed |
| **Schedule-independent** | Works with any pipeline frequency — no hardcoded time window |

### Run the script

Open the KQL Database → **Query** pane and run:

- [kql/04-sp-Recalculate-Summary_Alert_Channel.kql](kql/04-sp-Recalculate-Summary_Alert_Channel.kql)

**Test manually** (replace the datetime with an actual `load_ts` from your data):

```kusto
// Find a load_ts to test with
DepositMovement | summarize by load_ts | order by load_ts desc | limit 5

// Preview what would be inserted (no write)
sp_Recalculate_Summary_Alert_Channel(datetime(2026-04-24T08:31:00Z))

// Actually append into the Gold table
.set-or-append Summary_Alert_Channel <| sp_Recalculate_Summary_Alert_Channel(datetime(2026-04-24T08:31:00Z))

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
                 └─► Summary_Alert_Channel_MV is always up to date (with UpdatedAtUtc)
```

### How it differs from Option A

| Aspect | Option A (Stored Function) | Option B (Materialized View) |
|---|---|---|
| **When does it run?** | Only when the pipeline calls `.set-or-append <\| sp_...()` | Automatically after every ingestion |
| **What does it process?** | All rows for the affected dates (full-day re-aggregation) | Only new extents (truly incremental) |
| **Deduplication** | Appends rows — needs `UpdatedAtUtc` filtering | Maintains a single row per `Date` + `Time` + `Channel` |
| **`UpdatedAtUtc`** | `now()` — exact recalculation time | `max(load_ts)` — latest pipeline load time |
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
        Txn_Count    = sum(Total_Txn),
        UpdatedAtUtc = max(load_ts)
        by Date, Time, Channel
}
```

#### Key parts explained

| Part | What it does |
|---|---|
| `.create materialized-view` | Creates a persistent aggregated view managed by KQL |
| `with (backfill=true)` | Processes **all existing data** in `DepositMovement` immediately (not just future ingestions). Remove this if the table is empty at creation time. |
| `on table DepositMovement` | Binds the view to the source table — KQL watches this table for new data |
| `max(load_ts)` | Tracks the most recent pipeline load timestamp per Date+Time+Channel (freshness proxy) |
| `summarize ... by Date, Time, Channel` | The aggregation query — same logic as the stored function, but KQL runs it automatically |

#### Why `max(load_ts)` instead of `now()`?

| Approach | Works in materialized view? | Why? |
|---|---|---|
| `now()` | ❌ No | Each extent is processed at a different time — `now()` would produce different values, preventing proper merge |
| `max(load_ts)` | ✅ Yes | `load_ts` is a column value (set by the pipeline), and `max()` is a valid aggregation — KQL can merge it correctly |

**What `max(load_ts)` tells you:** "The most recent data contributing to this Date+Time+Channel aggregation was loaded at this time." This is slightly different from Option A's `now()` (which says "the recalculation happened at this time"), but serves the same purpose for freshness tracking.

#### How KQL processes it internally

1. **Initial backfill** — When created with `backfill=true`, KQL aggregates all existing rows in `DepositMovement` into the view
2. **Incremental updates** — After each ingestion, KQL identifies the new **extents** (data batches) and runs the `summarize` query on only those rows
3. **Merge** — New aggregations are merged with existing results. For `sum()`, this means adding the new values to the existing totals. For `max()`, it picks the latest `load_ts`.
4. **Single row per key** — Unlike Option A (which appends), the materialized view maintains exactly **one row per `Date` + `Time` + `Channel`**

#### How the merge works

```
Existing state (before 08:00-08:30):
  Day 5 + 00:00-00:30 + ATM → Credit_Total=50,000, UpdatedAtUtc=2026-04-24T07:30:00Z

New extent (08:00-08:30):
  Day 5 + 00:00-00:30 + ATM → sum(Credit_Amount)=15,000, max(load_ts)=2026-04-24T08:30:00Z

After merge:
  Day 5 + 00:00-00:30 + ATM → Credit_Total=65,000, UpdatedAtUtc=2026-04-24T08:30:00Z
                               (sum adds up)          (max picks the latest)
```

Both `sum()` and `max()` are **mergeable aggregation functions** — KQL can combine partial results without re-reading old data.

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
- You want `UpdatedAtUtc` for freshness tracking without managing a pipeline step
- Your aggregation is a straightforward `summarize` (sum, count, min, max, avg)
- You prefer a single row per key (no deduplication needed)
- You want the Gold table to update even during ad-hoc ingestions (not just pipeline runs)
- Your data is **append-only** (no deletes or updates to existing rows)

### When to stick with Option A

- You need **complex transformation logic** beyond simple aggregation (e.g., conditional recalculation, windowing, multi-table joins)
- You want explicit control over when the Gold table updates
- You want to log/audit each recalculation run

---

## ✅ Exit Criteria

**If you chose Option A:**
- [ ] Gold table `Summary_Alert_Channel` exists with 8 columns
- [ ] Stored function `sp_Recalculate_Summary_Alert_Channel` exists (verify: `.show function sp_Recalculate_Summary_Alert_Channel`)

**If you chose Option B:**
- [ ] Materialized view `Summary_Alert_Channel_MV` exists and is healthy (8 columns including `Time` and `UpdatedAtUtc`)
- [ ] `backfill=true` processed existing data (if any)

→ Proceed to **[Workshop 04 — Data Pipeline](../04-data-pipeline/)**

---

## 📚 KQL Reference Links

| Concept | Documentation |
|---|---|
| `.set-or-append` command | [.set-or-append](https://learn.microsoft.com/kusto/management/data-ingestion/ingest-from-query?view=microsoft-fabric) |
| `.create function` (stored function) | [.create function](https://learn.microsoft.com/kusto/management/create-function?view=microsoft-fabric) |
| `.create materialized-view` | [Materialized views](https://learn.microsoft.com/kusto/management/materialized-views/materialized-view-overview?view=microsoft-fabric) |
| `summarize` operator | [summarize operator](https://learn.microsoft.com/kusto/query/summarize-operator?view=microsoft-fabric) |
| `join` operator | [join operator](https://learn.microsoft.com/kusto/query/join-operator?view=microsoft-fabric) |
| `arg_max()` aggregation | [arg_max()](https://learn.microsoft.com/kusto/query/arg-max-aggregation-function?view=microsoft-fabric) |
| `extend` operator | [extend operator](https://learn.microsoft.com/kusto/query/extend-operator?view=microsoft-fabric) |
| `distinct` operator | [distinct operator](https://learn.microsoft.com/kusto/query/distinct-operator?view=microsoft-fabric) |
| Materialized view `backfill` | [Materialized views — backfill](https://learn.microsoft.com/kusto/management/materialized-views/materialized-view-create-or-alter?view=microsoft-fabric) |
| KQL quick reference | [KQL quick reference](https://learn.microsoft.com/kusto/query/kql-quick-reference?view=microsoft-fabric) |
