# Workshop 09 — Validate, Monitor & Document

Finalize the solution: run end-to-end validation, set up monitoring, apply housekeeping, and commit artifacts.

**Prerequisite:** [Workshop 08](../08-activator-alerts/) complete

---

## 9.1 End-to-end validation checklist

- [ ] Drop a brand-new file → pipeline runs, row count matches file, audit row `Success`.
- [ ] Drop the same file again → no duplicate rows, audit row `Skipped-Duplicate`.
- [ ] Corrupt a file (break header) → pipeline fails, audit row `Failed` with `ErrorMsg`.
- [ ] Power BI auto-refresh shows new 30-min bucket within ≤ 1 minute.
- [ ] Teams alert delivered on threshold breach.

## 9.2 Monitoring locations

| What | Where |
|---|---|
| Pipeline runs | Fabric **Monitor hub** → Pipeline runs |
| Trigger (Reflex) | Workspace list → Reflex item → Run history |
| Ingestion health | KQL: `.show ingestion failures` / `.show commands-and-queries` |
| Audit | `ProcessedFiles` table + Power BI "Data freshness" page |
| Storage event delivery | Storage Account → **Events** → Event Subscriptions → Metrics |

## 9.3 Housekeeping (Portal)

**Remove your personal IP from the storage firewall:**

1. **[portal.azure.com](https://portal.azure.com)** → storage account → **Security + networking** → **Networking**.
2. Under **Firewall**, click the **🗑** icon next to your IP entry → **Save**.

**Enable soft-delete (portal):**

1. Storage account → **Data management** → **Data protection**.
2. Enable **Blob soft delete** and **Container soft delete** → set retention 7–30 days → **Save**.

**Retention & caching on the KQL table** — run these in the Fabric KQL queryset UI:

```kusto
.alter table DepositMovement policy retention '{ "SoftDeletePeriod": "365.00:00:00", "Recoverability": "Enabled" }'
.alter table DepositMovement policy caching hot = 90d
```

## 9.4 Save artifacts

- Fabric items (pipeline, Eventhouse, Power BI report, Activator) are auto-saved in the workspace.
- If you want to snapshot the pipeline JSON: Fabric → pipeline → **…** → **Export** → commit the file under `workshops/04-data-pipeline/pipeline/`.
- For git users: use the **Source Control** view in VS Code (left sidebar) to stage, commit, and push — no command line needed.

## ✅ Project Done Criteria

- [ ] All 9 workshops pass their exit criteria
- [ ] Personal IP removed from storage firewall
- [ ] Soft-delete enabled on storage and retention policies applied to KQL
- [ ] Operations team has access to Power BI report and Teams alerts
