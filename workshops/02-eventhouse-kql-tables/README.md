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

Schema:

| Category | Columns |
|---|---|
| Grain | `Date`, `Time` |
| Dimensions | `Product`, `Channel`, `Channel_Group`, `Transaction_Type` |
| Measures | `Credit_Amount`, `Debit_Amount`, `Net_Amount`, `Credit_Txn`, `Debit_Txn`, `Total_Txn` |
| Lineage | `load_ts`, `file_name`, `pipeline_name`, `pipeline_runid` |

## 2.3 Create the Fabric Warehouse

1. Fabric workspace → **+ New item** → **Warehouse** → name it `wh_control_framework` → **Create**.
2. Once provisioned, open the Warehouse and click **New SQL query**.

## 2.4 Create the audit/control table (T-SQL)

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

## 2.5 Enable streaming ingestion on the KQL table

In the KQL Database query pane:

```kusto
.show database DepositMovement policy streamingingestion
.show table DepositMovement policy streamingingestion
```

(Warehouses don't have a streaming-ingestion policy — writes via pipeline `Script` / `Stored procedure` activity are sufficient for a per-file audit row.)

## 2.6 Create the Gold table (Summary_Alert_Channel)

This is the **aggregated target table** that stores daily channel-level summaries. It will be updated incrementally by the stored procedure below.

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

This stored procedure recalculates **only the dates present in the newly ingested data**. For example, if the new file contains records for dates 20260424 and 20260423, only those two dates will be aggregated and upserted into the Gold table.

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
