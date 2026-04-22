# Workshop 08 — Data Activator Alerts

Configure Activator (Reflex) rules that query KQL directly and post notifications to Microsoft Teams on business or operational events.

**Prerequisite:** [Workshop 07](../07-powerbi-report/) complete
**Next:** [Workshop 09 — Validate & Monitor](../09-validate-monitor/)

---

## 8.1 Create the Activator item

Workspace → **+ New item** → **Activator** → name `act-deposit-alerts`.

## 8.2 Add an event source (KQL)

- **Source type:** Eventhouse / KQL DB `DepositMovement`.
- **Sample query — large net outflow:**
  ```kusto
  DepositMovement
  | where load_ts > ago(15m)
  | summarize Net = sum(Net_Amount), Rows = count() by bin(load_ts, 30m), Channel
  ```

## 8.3 Define rules

| Rule | Condition | Action |
|---|---|---|
| **Large net outflow** | `Net < -1,000,000` (per Channel per 30-min bin) | Post to Teams channel `#rti-alerts` |
| **Ingestion failure** | `ProcessedFiles` — any `Status == "Failed"` in last 10 min | Email on-call + Teams |
| **Missing file (SLA breach)** | `max(IngestedAtUtc) < ago(15m)` during operating hours | Teams @channel |

## 8.4 Connect Teams

Action → **Microsoft Teams** → sign in → select team and channel. Use dynamic placeholders in the message body: file name, channel, net amount, pipeline run ID.

## 8.5 Test

- Drop a file that would breach the threshold (or lower the threshold temporarily).
- Confirm a Teams message lands within ~30 s of trigger.
- Rename a file to a missing path and re-run the pipeline to trigger the Failed rule.

## ✅ Exit Criteria

- [ ] Activator item running (green)
- [ ] At least one test alert delivered to Teams for each of the 3 rules

→ Proceed to **[Workshop 09 — Validate & Monitor](../09-validate-monitor/)**
