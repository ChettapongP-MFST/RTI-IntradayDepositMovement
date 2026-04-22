# RTI Intraday Deposit Movement

**Microsoft Fabric Real-Time Intelligence — Pattern B**
ADLS Gen2 → Fabric Data Pipeline (event-triggered) → Eventhouse (KQL DB) → Power BI → Activator → MS Teams

A modular, hands-on workshop series that builds a near-real-time intraday deposit monitoring solution on Microsoft Fabric using **Pattern B** (Eventhouse-centric RTI). Designed to be completed sequentially from Workshop 00 to Workshop 09.

---

## The Story

A retail bank needs **near real-time visibility** into intraday deposit movements (credits, debits, net flows) across channels (ATM, BCMS, ENET) and products. CSV extracts land in ADLS Gen2 every **10 minutes**. The operations team needs:

- Dashboards that refresh within a minute
- Automated alerts to Teams when large net outflows or ingestion failures occur
- Full auditability of which file produced which rows (lineage)

This workshop series walks through building that solution end-to-end.

---

## Workshop Modules

| # | Module | Fabric Component | Description |
|---|---|---|---|
| 00 | [Prerequisites](workshops/00-prerequisites/) | — | Azure / Fabric readiness checklist |
| 01 | [Provision ADLS Gen2](workshops/01-provision-adls-gen2/) | Azure Storage | Firewall-enabled storage account + container |
| 02 | [Eventhouse & KQL Tables](workshops/02-eventhouse-kql-tables/) | Eventhouse / KQL DB | `DepositMovement` + `ProcessedFiles` tables |
| 03 | [Trusted Workspace Access](workshops/03-trusted-workspace-access/) | Fabric Security | Workspace identity + resource instance rule |
| 04 | [Data Pipeline](workshops/04-data-pipeline/) | Data Factory | Hardened, idempotent ingestion pipeline |
| 05 | [Event Trigger](workshops/05-event-trigger/) | Eventstream + Reflex | `BlobCreated` → pipeline wire-up |
| 06 | [Simulate Ingestion](workshops/06-simulate-ingestion/) | PowerShell / AzCopy | Replay 16 CSVs (real or accelerated) |
| 07 | [Power BI Report](workshops/07-powerbi-report/) | Power BI (+ optional RTD) | DirectQuery KPI report with 30s refresh |
| 08 | [Activator Alerts](workshops/08-activator-alerts/) | Data Activator | KQL-driven Teams notifications |
| 09 | [Validate & Monitor](workshops/09-validate-monitor/) | Monitor hub | End-to-end checklist + housekeeping |

---

## Getting Started

### Prerequisites

- Microsoft Fabric **F-SKU** capacity (not Trial) — Trusted Workspace Access requires F-SKU
- Azure subscription with **Contributor** on the target resource group
- Role **User Access Administrator** or **Owner** on the storage account scope (for RBAC assignment)
- Azure CLI ≥ 2.60 and Az PowerShell ≥ 11
- Access to a Microsoft Teams channel (Workshop 08)

### How to Use

1. Clone this repository:
   ```bash
   git clone https://github.com/ChettapongP-MFST/RTI-IntradayDepositMovement.git
   ```
2. Start with [`workshops/00-prerequisites/`](workshops/00-prerequisites/) and complete modules in order (00 → 09).
3. Each workshop has its own `README.md` with step-by-step instructions, code snippets, and exit criteria.
4. Sample CSVs are in [`resources/datasets/`](resources/datasets/) (16 files × 30-min slots).

---

## Repository Structure

```
RTI-IntradayDepositMovement/
├── workshops/
│   ├── 00-prerequisites/
│   ├── 01-provision-adls-gen2/
│   │   └── scripts/
│   ├── 02-eventhouse-kql-tables/
│   │   └── kql/
│   ├── 03-trusted-workspace-access/
│   │   └── scripts/
│   ├── 04-data-pipeline/
│   │   └── pipeline/
│   ├── 05-event-trigger/
│   ├── 06-simulate-ingestion/
│   │   └── scripts/
│   ├── 07-powerbi-report/
│   ├── 08-activator-alerts/
│   └── 09-validate-monitor/
├── resources/
│   └── datasets/          # 16 mock CSVs (30-min intraday slots)
├── images/                # Architecture diagrams & screenshots
├── .gitignore
├── LICENSE
└── README.md
```

---

## Target Architecture

![Target architecture — ADLS Gen2 → Pipeline → Eventhouse → Power BI / Activator → MS Teams, all on OneLake](images/Target%20Architecture.png)

**Flow** — `Connect` (ADLS Gen2) → `Ingest & Process` (Fabric Data Pipeline, event-triggered) → `Analyse & Transform` (Eventhouse / KQL DB) → `Visualize & Act` (Power BI report + Activator) → `Get assisted & Interact` (MS Teams). All Fabric items are backed by **OneLake**.

Key design principles:

- **Event-driven**: `Microsoft.Storage.BlobCreated` triggers the pipeline immediately when a file lands.
- **Idempotent**: `ProcessedFiles` control table + KQL `ingest-by` tag prevent duplicate loads.
- **Traceable**: Every business row carries `load_ts`, `file_name`, `pipeline_name`, `pipeline_runid`.
- **Secured**: ADLS Gen2 firewalled; Fabric reaches it via **Trusted Workspace Access** (resource instance rule).

---

## Data Model

**`DepositMovement`** (business table, 16 columns):

| Category | Columns |
|---|---|
| Grain | `Date`, `Time` |
| Dimensions | `Product`, `Channel`, `Channel_Group`, `Transaction_Type` |
| Measures | `Credit_Amount`, `Debit_Amount`, `Net_Amount`, `Credit_Txn`, `Debit_Txn`, `Total_Txn` |
| Lineage | `load_ts`, `file_name`, `pipeline_name`, `pipeline_runid` |

**`ProcessedFiles`** (audit/control table, 8 columns):

`FileName`, `IngestedAtUtc`, `RowCount`, `Status` (Success / Failed / Skipped-Duplicate), `PipelineName`, `PipelineRunId`, `RunAsUser`, `ErrorMsg`

---

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.

## License

This project is licensed under the MIT License — see the [LICENSE](LICENSE) file for details.

## References

- [Microsoft Fabric Real-Time Intelligence](https://learn.microsoft.com/en-us/fabric/real-time-intelligence/)
- [Trusted Workspace Access for ADLS Gen2](https://learn.microsoft.com/en-us/fabric/security/security-trusted-workspace-access)
- [Pipeline storage event triggers](https://learn.microsoft.com/en-us/fabric/data-factory/pipeline-runs)
