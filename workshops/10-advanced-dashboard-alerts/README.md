# Workshop 10 — Advanced Dashboard & Alerts (Gold Layer)

Build a production-grade **near real-time dashboard** and a comprehensive set of **Activator alert rules** driven by the `Summary_Alert_Channel` Gold table created in Workshop 02 and 03.

This workshop supersedes the basic reports in Workshop 07 and alert rules in Workshop 08 with richer KPIs, multi-page layout, and business-aligned thresholds.

**Prerequisite:** [Workshop 09](../09-validate-monitor/) complete (full pipeline running end-to-end)
**Next:** You've completed the full workshop series! 🎉

---

## Data Sources Used in This Workshop

| Source | Type | Purpose |
|---|---|---|
| `DepositMovement` | KQL DB (Bronze) | Transaction-level detail — channel drill-down |
| `Summary_Alert_Channel` | KQL DB (Gold) | Pre-aggregated daily × channel summaries — fast KPIs |
| `wh_control_framework.dbo.ProcessedFiles` | Fabric Warehouse | Pipeline health & audit |

---

## 10.1 Update the Gold Table for Alert-Ready Columns

Before building the dashboard, enrich the stored procedure to include ratio columns that make Activator thresholds simple.

Open the KQL Database → **Query** pane and run:

```kusto
// Drop and recreate the procedure with ratio columns
.drop procedure sp_Recalculate_Summary_Alert_Channel ifexists

.create procedure sp_Recalculate_Summary_Alert_Channel()
{
    let RecentDates = DepositMovement
        | where IngestedAtUtc >= ago(15m)
        | distinct Date;

    RecentDates
    | join kind=inner DepositMovement on Date
    | summarize
        Credit_Total     = sum(Credit_Amount),
        Debit_Total      = sum(Debit_Amount),
        Net_Amount       = sum(Net_Amount),
        Txn_Count        = sum(Total_Txn),
        Credit_Txn_Total = sum(Credit_Txn),
        Debit_Txn_Total  = sum(Debit_Txn)
        by Date, Channel
    | extend
        UpdatedAtUtc      = now(),
        OffUs_Ratio       = todouble(Debit_Txn_Total) / iff(Txn_Count == 0, 1.0, todouble(Txn_Count)),
        Debit_Credit_Ratio = todouble(Debit_Total) / iff(Credit_Total == 0, 1.0, todouble(Credit_Total))
    | project Date, Channel, Credit_Total, Debit_Total, Net_Amount, Txn_Count,
              Credit_Txn_Total, Debit_Txn_Total, OffUs_Ratio, Debit_Credit_Ratio, UpdatedAtUtc
    | getorcreate table Summary_Alert_Channel_v2 (
        Date:datetime, Channel:string,
        Credit_Total:real, Debit_Total:real, Net_Amount:real,
        Txn_Count:long, Credit_Txn_Total:long, Debit_Txn_Total:long,
        OffUs_Ratio:real, Debit_Credit_Ratio:real, UpdatedAtUtc:datetime)
    | insert into Summary_Alert_Channel_v2 (T)
}
```

> The updated table is named `Summary_Alert_Channel_v2` to preserve the existing Gold table while you migrate.

Verify:

```kusto
exec sp_Recalculate_Summary_Alert_Channel;
Summary_Alert_Channel_v2 | order by Date desc, Channel | limit 20
```

---

## 10.2 Create the Power BI Report (4 Pages)

### 10.2.1 Create the semantic model

1. Open the KQL Database `DepositMovement` in Fabric.
2. **Explore your data** → **Build Power BI report** → **DirectQuery**.
3. Add **both** tables: `DepositMovement` and `Summary_Alert_Channel_v2`.
4. Also add `wh_control_framework.dbo.ProcessedFiles` from Warehouse (Import mode is fine for audit data).

### 10.2.2 Define relationships

In Power BI model view:

| From | To | Cardinality |
|---|---|---|
| `DepositMovement[Date]` | `Summary_Alert_Channel_v2[Date]` | Many-to-One |
| `DepositMovement[Channel]` | `Summary_Alert_Channel_v2[Channel]` | Many-to-One |

### 10.2.3 DAX Measures

```DAX
-- Volume KPIs (from Bronze for real-time accuracy)
Total Credit          = SUM('DepositMovement'[Credit_Amount])
Total Debit           = SUM('DepositMovement'[Debit_Amount])
Net Position          = SUM('DepositMovement'[Net_Amount])
Total Transactions    = SUM('DepositMovement'[Total_Txn])

-- Trend KPIs
Net Position (Gold)   = SUM('Summary_Alert_Channel_v2'[Net_Amount])
Debit Credit Ratio    = AVERAGE('Summary_Alert_Channel_v2'[Debit_Credit_Ratio])
OffUs Ratio           = AVERAGE('Summary_Alert_Channel_v2'[OffUs_Ratio])

-- Pipeline health (from Warehouse)
Last Ingested         = MAX('ProcessedFiles'[IngestedAtUtc])
Minutes Since Load    = DATEDIFF([Last Ingested], UTCNOW(), MINUTE)
Files Today           = CALCULATE(COUNTROWS('ProcessedFiles'), 'ProcessedFiles'[Status] = "Success")
Failed Files Today    = CALCULATE(COUNTROWS('ProcessedFiles'), 'ProcessedFiles'[Status] = "Failed")
```

---

## 10.3 Report Pages

### Page 1 — Real-Time Overview

The **command centre** view — one glance shows the full intraday picture.

| Visual | Type | Data |
|---|---|---|
| **Intraday Net Position** | KPI card (green > 0 / red < 0) | `Net Position` measure |
| **Total Transactions Today** | Card | `Total Transactions` |
| **Total Credit Volume** | Card | `Total Credit` |
| **Total Debit Volume** | Card | `Total Debit` |
| **Net Position trend** | Area / line chart | `Net Position` by `Time` (30-min slots), per Channel |
| **Online vs. Offline split** | Donut chart | `Total Transactions` by `Channel_Group` |
| **On-Us vs. Off-Us split** | Donut chart | `Total Transactions` by `Transaction_Type` |

**APR:** Format page → Page refresh → 30 seconds.

---

### Page 2 — Channel Drill-Down

Deep-dive into which channels are driving flows.

| Visual | Type | Data |
|---|---|---|
| **Net Position by Channel** | Clustered bar chart | `Net Position` per Channel (ATM / BCMS / ENET / TELL) |
| **Transaction Volume by Channel** | Bar chart | `Total Transactions` per Channel |
| **Channel Activity Heatmap** | Matrix | Rows = Channel, Columns = Time slot, Values = `Total Transactions` |
| **Off-Us Ratio per Channel** | 100% stacked bar | On-Us vs. Off-Us Txn split per Channel |
| **Debit/Credit Ratio by Channel** | Bar chart | `Debit Credit Ratio` per Channel (threshold line at 2.0) |

**Slicer:** `Date` and `Channel_Group` (Online / Offline).

---

### Page 3 — Product Analysis

Understand which product line drives the net position.

| Visual | Type | Data |
|---|---|---|
| **Net Position by Product** | Gauge | `Net Position` sliced by `Product` (Fixed / Saving / Current) |
| **Credit vs. Debit by Product** | Clustered column chart | `Total Credit` and `Total Debit` side-by-side per Product |
| **Transaction mix by Product × Channel** | Matrix table | Rows = Product, Columns = Channel, Values = `Total Transactions` |
| **Intraday trend by Product** | Line chart | `Net Position` by 30-min slot, one line per Product |

---

### Page 4 — Data Freshness & Pipeline Health

Operational view for the data engineering / ops team.

| Visual | Type | Data |
|---|---|---|
| **Last File Ingested** | Card | `Last Ingested` |
| **Pipeline Lag (minutes)** | KPI card (red if > 35 min) | `Minutes Since Load` |
| **Files Loaded Today** | Card | `Files Today` |
| **Failed Files** | Card (red if > 0) | `Failed Files Today` |
| **ProcessedFiles log** | Table | All rows from `dbo.ProcessedFiles` ordered by `IngestedAtUtc DESC` |
| **Status breakdown** | Stacked bar | Count by Status over time |

---

## 10.4 Publish the Report

1. **File** → **Publish** → select your Fabric workspace.
2. Share with:
   - Operations team: **Viewer**
   - Data engineers: **Contributor**
3. Set **Sensitivity label** if required by your organisation.

---

## 10.5 Create the Activator Item

Workspace → **+ New item** → **Activator** → name `act-deposit-alerts-v2`.

> If an existing `act-deposit-alerts` exists from Workshop 08, create a new one so both can run in parallel during testing.

---

## 10.6 Define Alert Rules

### Rule 1 — Intraday Net Outflow per Channel

**Source:** `Summary_Alert_Channel_v2` (KQL)

```kusto
Summary_Alert_Channel_v2
| where UpdatedAtUtc >= ago(15m)
| where Net_Amount < -2000000
| project Channel, Net_Amount, Date, UpdatedAtUtc
```

**Trigger:** Row returned → any Channel with net outflow > 2M
**Action:** Teams channel `#rti-alerts`
**Message:**
```
⚠️ Net Outflow Alert
Channel: {Channel}
Net Amount: {Net_Amount}
Date: {Date}
Updated: {UpdatedAtUtc}
```

---

### Rule 2 — ATM Cash Drain (High Debit/Credit Ratio)

**Source:** `Summary_Alert_Channel_v2` (KQL)

```kusto
Summary_Alert_Channel_v2
| where UpdatedAtUtc >= ago(15m)
| where Channel == "ATM"
| where Debit_Credit_Ratio > 3.0
| project Channel, Debit_Credit_Ratio, Debit_Total, Credit_Total, UpdatedAtUtc
```

**Trigger:** ATM `Debit_Credit_Ratio` exceeds 3.0
**Action:** Teams `#rti-alerts` + Email on-call
**Message:**
```
🏧 ATM Cash Drain Alert
Debit/Credit Ratio: {Debit_Credit_Ratio}
Debit Total: {Debit_Total}  |  Credit Total: {Credit_Total}
Updated: {UpdatedAtUtc}
```

---

### Rule 3 — Off-Us Volume Spike

**Source:** `Summary_Alert_Channel_v2` (KQL)

```kusto
Summary_Alert_Channel_v2
| where UpdatedAtUtc >= ago(15m)
| where OffUs_Ratio > 0.70
| project Channel, OffUs_Ratio, Txn_Count, UpdatedAtUtc
```

**Trigger:** Off-Us transactions exceed 70% of total for any Channel
**Action:** Teams `#rti-alerts`
**Message:**
```
📊 Off-Us Volume Spike
Channel: {Channel}
Off-Us Ratio: {OffUs_Ratio:.0%}
Total Transactions: {Txn_Count}
Updated: {UpdatedAtUtc}
```

---

### Rule 4 — Intraday Net Negative (Cumulative)

**Source:** `Summary_Alert_Channel_v2` (KQL)

```kusto
Summary_Alert_Channel_v2
| where Date == startofday(now())
| summarize Cumulative_Net = sum(Net_Amount)
| where Cumulative_Net < 0
```

**Trigger:** Total cumulative net position for the day goes negative
**Action:** Teams `#rti-executive` + Email executive team
**Message:**
```
🚨 Intraday Net Position Negative
Cumulative Net: {Cumulative_Net}
As of: [now]
Immediate attention required.
```

---

### Rule 5 — Channel Silence (Possible Outage)

**Source:** `DepositMovement` (KQL)

```kusto
let ExpectedChannels = datatable(Channel:string)["ATM","BCMS","ENET","TELL"];
let ActiveChannels = DepositMovement
    | where IngestedAtUtc >= ago(35m)
    | distinct Channel;
ExpectedChannels
| join kind=leftanti ActiveChannels on Channel
```

**Trigger:** Any expected channel missing from last 35 minutes of data
**Action:** Teams `#rti-alerts` + Email ops
**Message:**
```
🔕 Channel Silence Detected
Missing Channel: {Channel}
No transactions received in the last 35 minutes.
Check pipeline and source system.
```

---

### Rule 6 — Pipeline SLA Breach

**Source:** `wh_control_framework.dbo.ProcessedFiles` (Warehouse — via Power BI semantic model measure)

**Condition in Activator (via Power BI):**
- Measure `Minutes Since Load` > 35

**Trigger:** File not ingested within 35 minutes of previous
**Action:** Email ops team
**Message:**
```
⏰ Pipeline SLA Breach
Last file ingested: {Last Ingested}
Minutes since last load: {Minutes Since Load}
Expected cadence: every 10 minutes.
```

---

## 10.7 Connect Microsoft Teams

For each rule:

1. **Action** → **Microsoft Teams**.
2. Sign in with your Microsoft 365 account.
3. Select **Team** and **Channel** per the table below:

| Rule | Team | Channel |
|---|---|---|
| Rules 1, 2, 3, 5 | RTI Operations | `#rti-alerts` |
| Rule 4 | Executive | `#rti-executive` |
| Rule 6 | Data Engineering | `#rti-ops` |

Use **dynamic placeholders** in message body (field names in `{braces}` above).

---

## 10.8 Test All Rules

| Test | How to trigger | Expected outcome |
|---|---|---|
| Rule 1 | Lower threshold to `-1` temporarily → re-run pipeline | Teams alert in `#rti-alerts` |
| Rule 2 | Lower ATM ratio threshold to `0.5` | Teams alert |
| Rule 3 | Lower Off-Us threshold to `0.3` | Teams alert |
| Rule 4 | Lower cumulative threshold to any positive | Teams + Email |
| Rule 5 | Drop a file with 3 channels only (exclude ATM rows) | Teams alert for ATM |
| Rule 6 | Pause the event trigger for 40 minutes | Email ops |

After verifying each rule, restore original thresholds.

---

## ✅ Exit Criteria

- [ ] `Summary_Alert_Channel_v2` table exists with 11 columns including ratio columns
- [ ] Stored procedure updated and tested (15-min incremental recalculation)
- [ ] Power BI report published with 4 pages, APR = 30 seconds
- [ ] All DAX measures return values matching KQL queries
- [ ] Activator item `act-deposit-alerts-v2` running (green)
- [ ] All 6 alert rules defined and tested
- [ ] At least one test alert delivered per rule to Teams
- [ ] Stakeholder access confirmed (Viewer/Contributor)

---

## Reference KQL Queries for Ad-Hoc Validation

```kusto
// Current intraday net position by channel
Summary_Alert_Channel_v2
| where Date == startofday(now())
| project Channel, Net_Amount, Txn_Count, OffUs_Ratio, Debit_Credit_Ratio
| order by Net_Amount asc

// Top outflow channels in last 2 hours
DepositMovement
| where IngestedAtUtc >= ago(2h)
| summarize Net = sum(Net_Amount) by Channel, bin(IngestedAtUtc, 30m)
| order by IngestedAtUtc desc, Net asc

// Pipeline health check
// (Run in Warehouse SQL query pane)
-- SELECT TOP (10) * FROM dbo.ProcessedFiles ORDER BY IngestedAtUtc DESC;
```
