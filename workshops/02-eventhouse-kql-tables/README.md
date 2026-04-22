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

1. Fabric workspace → **+ New item** → **Warehouse** → name it `wh_rti_control` → **Create**.
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

## ✅ Exit Criteria

- [ ] Eventhouse + KQL Database `DepositMovement` exist, with the 16-column `DepositMovement` table + `DepositMovement_mapping`
- [ ] Streaming ingestion enabled on `DepositMovement`
- [ ] Warehouse `wh_rti_control` exists
- [ ] Table `dbo.ProcessedFiles` exists with 8 columns; empty `SELECT` returns no rows

→ Proceed to **[Workshop 03 — Trusted Workspace Access](../03-trusted-workspace-access/)**
