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

## 9.3 Housekeeping

```powershell
# Remove personal IP from storage firewall
az storage account network-rule remove -g $rg -n $sa --ip-address $myIp
```

Enable soft-delete on the container (if not already on), review rotation policy for keys.

Retention & caching policies on the KQL table:

```kusto
.alter table DepositMovement policy retention '{ "SoftDeletePeriod": "365.00:00:00", "Recoverability": "Enabled" }'
.alter table DepositMovement policy caching hot = 90d
```

## 9.4 Commit artifacts

```powershell
git add .
git commit -m "Complete Pattern B workshop artifacts"
git push
```

## ✅ Project Done Criteria

- [ ] All 9 workshops pass their exit criteria
- [ ] Artifacts committed to GitHub
- [ ] Operations team has access to Power BI report and Teams alerts
