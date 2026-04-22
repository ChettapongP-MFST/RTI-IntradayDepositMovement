# Workshop 02 — Eventhouse & KQL Tables

Create the Eventhouse, the business table `DepositMovement`, and the audit table `ProcessedFiles`. Enable streaming ingestion for low-latency.

**Prerequisite:** [Workshop 01](../01-provision-adls-gen2/) complete
**Next:** [Workshop 03 — Trusted Workspace Access](../03-trusted-workspace-access/)

---

## 2.1 Create the Eventhouse

1. Open the Fabric workspace (from Workshop 00.3).
2. **+ New item** → **Eventhouse** → name it `eh-rti-deposit`.
3. Inside the Eventhouse, the default KQL Database `eh-rti-deposit` is created. Create (or rename to) a KQL Database named `DepositMovement`.

## 2.2 Create the business table

Open the KQL Database → **Query** pane and run:

- [kql/01-create-DepositMovement.kql](kql/01-create-DepositMovement.kql)

Schema:

| Category | Columns |
|---|---|
| Grain | `Date`, `Time` |
| Dimensions | `Product`, `Channel`, `Channel_Group`, `Transaction_Type` |
| Measures | `Credit_Amount`, `Debit_Amount`, `Net_Amount`, `Credit_Txn`, `Debit_Txn`, `Total_Txn` |
| Lineage | `load_ts`, `file_name`, `pipeline_name`, `pipeline_runid` |

## 2.3 Create the audit/control table

- [kql/02-create-ProcessedFiles.kql](kql/02-create-ProcessedFiles.kql)

Schema:

| Column | Type | Purpose |
|---|---|---|
| `FileName` | string | Natural key for dedup |
| `IngestedAtUtc` | datetime | When the row was written |
| `RowCount` | long | Rows copied by the pipeline |
| `Status` | string | `Success` / `Failed` / `Skipped-Duplicate` |
| `PipelineName` | string | `@pipeline().Pipeline` |
| `PipelineRunId` | string | `@pipeline().RunId` |
| `RunAsUser` | string | Trigger type + name |
| `ErrorMsg` | string | Copy Activity error (if any) |

## 2.4 Enable streaming ingestion

Already included in the KQL scripts above; verify with:

```kusto
.show database DepositMovement policy streamingingestion
.show table DepositMovement policy streamingingestion
.show table ProcessedFiles policy streamingingestion
```

## ✅ Exit Criteria

- [ ] `DepositMovement` table exists with 16 columns + `DepositMovement_mapping`
- [ ] `ProcessedFiles` table exists with 8 columns + `ProcessedFiles_mapping`
- [ ] Streaming ingestion enabled on both

→ Proceed to **[Workshop 03 — Trusted Workspace Access](../03-trusted-workspace-access/)**
