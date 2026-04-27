# Workshop 08 — Data Activator Alerts (Teams Notification)

Configure **Data Activator (Reflex)** to monitor the intraday cumulative `Net_Amount` from the `DepositMovement` KQL table and send **tiered alerts to Microsoft Teams** when thresholds are breached — with Channel-level breakdown in every notification.

**Prerequisite:** [Workshop 07](../07-powerbi-report/) complete
**Next:** [Workshop 09 — Validate & Monitor](../09-validate-monitor/)

---

## 8.0 Alert requirement

Monitor `SUM(Net_Amount)` for **today's date** (intraday). When the cumulative net outflow crosses a threshold, fire an alert to Microsoft Teams.

### Three alert tiers

| Tier | Threshold (Million Baht) | Flag | Severity color |
|---|---|---|---|
| 🟡 **Low** | ≤ −5,000 M | `Low` | Yellow |
| 🟠 **Medium** | ≤ −10,000 M | `Medium` | Orange |
| 🔴 **High** | ≤ −15,000 M | `High` | Red |

### Teams notification must include

- **Alert flag** (Low / Medium / High)
- **Cumulative Net Amount** (today's running total)
- **Channel breakdown** — which channels (`ATM`, `BCMS`, `ENET`, `TELL`) are driving the outflow
- **Date** and **Latest time slot**
- **Timestamp** of the alert

---

## 8.1 Create the Activator item

1. Open your Fabric workspace.
2. **+ New item** → search for **Activator** (also called **Reflex**) → name it `act-deposit-alerts`.
3. Click **Create**.

> 💡 If you don't see "Activator", ensure your workspace has a Fabric capacity (F2 or higher) and that Activator is enabled in the admin portal.

---

## 8.2 Prepare the KQL query for the event source

Before wiring up Activator, let's validate the query that will power the alerts. Run this in the **KQL Database query editor** to confirm it returns the expected shape:

### 8.2.1 Intraday cumulative net by Channel

```kusto
// Intraday cumulative net with channel breakdown — the Activator event source
DepositMovement
| where Date == startofday(now())
| summarize 
    Net_Amount = sum(Net_Amount),
    Credit_Total = sum(Credit_Amount),
    Debit_Total = sum(Debit_Amount),
    Txn_Count = sum(Total_Txn)
    by Channel, Time
| order by Channel asc, Time asc
| extend Cum_Net = row_cumsum(Net_Amount)
| summarize 
    Cum_Net_Channel = sum(Cum_Net),
    arg_max(Time, *)
    by Channel
```

### 8.2.2 Intraday cumulative net total (for threshold check)

```kusto
// Overall intraday cumulative net — used for threshold comparison
DepositMovement
| where Date == startofday(now())
| summarize Cum_Net_Total = sum(Net_Amount)
| extend Alert_Flag = case(
    Cum_Net_Total <= -15000000000, "High",
    Cum_Net_Total <= -10000000000, "Medium",
    Cum_Net_Total <=  -5000000000, "Low",
    "Normal"
  )
| extend Alert_Time = now()
```

> ⚠ **Units**: The raw data is in **Baht** (not millions). So −5,000 M Baht = `−5,000,000,000` in the KQL filter.

### 8.2.3 Combined query — alert with channel detail

This is the query you will use as the Activator event source. It produces one row per evaluation with the cumulative total, alert flag, and a summary of channel contributions:

```kusto
// Combined: threshold check + channel breakdown for Teams notification
let today = startofday(now());
let cum_total = toscalar(
    DepositMovement
    | where Date == today
    | summarize sum(Net_Amount)
);
let alert_flag = case(
    cum_total <= -15000000000, "🔴 High",
    cum_total <= -10000000000, "🟠 Medium",
    cum_total <=  -5000000000, "🟡 Low",
    "✅ Normal"
);
let latest_time = toscalar(
    DepositMovement
    | where Date == today
    | summarize max(Time)
);
let channel_detail = 
    DepositMovement
    | where Date == today
    | summarize 
        Net = sum(Net_Amount),
        Credit = sum(Credit_Amount),
        Debit = sum(Debit_Amount)
        by Channel
    | order by Net asc
    | extend Net_Mil = round(Net / 1000000, 1)
    | project Channel, Net_Mil;
channel_detail
| extend 
    Cum_Net_Total = round(cum_total / 1000000, 1),
    Alert_Flag = alert_flag,
    Latest_Time = latest_time,
    Alert_Time = now(),
    Date = today
```

**Expected output** (example):

| Channel | Net_Mil | Cum_Net_Total | Alert_Flag | Latest_Time | Alert_Time | Date |
|---|---|---|---|---|---|---|
| ATM | −3,200.5 | −10,245.6 | 🟠 Medium | 10:30-11:00 | 2026-04-28T10:35:00Z | 2026-04-28 |
| BCMS | −4,100.2 | −10,245.6 | 🟠 Medium | 10:30-11:00 | 2026-04-28T10:35:00Z | 2026-04-28 |
| ENET | −1,800.0 | −10,245.6 | 🟠 Medium | 10:30-11:00 | 2026-04-28T10:35:00Z | 2026-04-28 |
| TELL | −1,144.9 | −10,245.6 | 🟠 Medium | 10:30-11:00 | 2026-04-28T10:35:00Z | 2026-04-28 |

---

## 8.3 Set up the Activator event source

1. Open `act-deposit-alerts` in Fabric.
2. Click **Select a data source** → choose **Eventhouse / KQL Database**.
3. Select database: `DepositMovement`.
4. Paste the **combined query** from section 8.2.3 into the query editor.
5. Set the **evaluation frequency**:
   - Recommended: **Every 5 minutes** (balances latency vs. KQL cost).
   - For testing: **Every 1 minute**.
6. Click **Connect** → verify the preview shows rows with `Alert_Flag`, `Cum_Net_Total`, and `Channel` columns.

---

## 8.4 Create the alert rules

### Rule 1 — 🟡 Low Alert (≤ −5,000 M)

1. In the Activator canvas, click **+ New rule**.
2. **Name**: `Low — Net Outflow ≤ -5,000M`
3. **Monitor**: `Cum_Net_Total` column.
4. **Condition**: `Cum_Net_Total` **is less than or equal to** `−5000`.
   > (The query outputs in millions, so −5,000 M = `−5000` in the `Cum_Net_Total` column.)
5. **Additional filter**: `Alert_Flag` **contains** `Low`
6. **Action**: Microsoft Teams (see section 8.5).

### Rule 2 — 🟠 Medium Alert (≤ −10,000 M)

1. **+ New rule** → name: `Medium — Net Outflow ≤ -10,000M`
2. **Condition**: `Cum_Net_Total` **≤** `−10000`
3. **Additional filter**: `Alert_Flag` **contains** `Medium`
4. **Action**: Microsoft Teams.

### Rule 3 — 🔴 High Alert (≤ −15,000 M)

1. **+ New rule** → name: `High — Net Outflow ≤ -15,000M`
2. **Condition**: `Cum_Net_Total` **≤** `−15000`
3. **Additional filter**: `Alert_Flag` **contains** `High`
4. **Action**: Microsoft Teams.

### De-duplication

Each rule should fire **only once per breach** (not every evaluation cycle). Configure:
- **Trigger**: **When condition first becomes true** (not "each time").
- This ensures you get one Teams message per tier crossing, not repeated alerts every 5 minutes.

---

## 8.5 Configure the Microsoft Teams action

For each rule, configure the Teams notification:

### 8.5.1 Connect to Teams

1. In the rule's **Action** section → select **Microsoft Teams**.
2. **Sign in** with your Microsoft 365 account.
3. Select the **Team** and **Channel** where alerts should land (e.g., `#rti-alerts`).

### 8.5.2 Message template

Use **dynamic content** placeholders from the query output columns. Format the message as follows:

**Subject line:**
```
⚠ Deposit Alert {Alert_Flag} — Cumulative Net: {Cum_Net_Total} M
```

**Message body:**
```
🏦 Intraday Deposit Movement Alert
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🚨 Alert Level:    {Alert_Flag}
📅 Date:           {Date}
🕐 Latest Slot:    {Latest_Time}
⏰ Alert Time:     {Alert_Time}

💰 Cumulative Net: {Cum_Net_Total} M Baht

📊 Channel Breakdown:
┌─────────┬────────────┐
│ Channel │  Net (M)   │
├─────────┼────────────┤
│ ATM     │ {Net_Mil}  │
│ BCMS    │ {Net_Mil}  │
│ ENET    │ {Net_Mil}  │
│ TELL    │ {Net_Mil}  │
└─────────┴────────────┘

Action Required:
• Low (-5,000M): Monitor closely
• Medium (-10,000M): Escalate to Treasury
• High (-15,000M): Immediate management action

Dashboard: [Open Power BI Report]
```

> 💡 The actual placeholders depend on the Activator UI — use the **Insert dynamic content** dropdown to map each `{field}` to the corresponding query column. The channel breakdown appears because the query returns one row per channel.

### 8.5.3 Alternative — Adaptive Card (richer format)

For a more visually appealing Teams message, use the **Custom action** → **Power Automate flow** option:

1. Rule action → **Run a Power Automate flow**.
2. In Power Automate, use the **Post adaptive card in a chat or channel** action.
3. Design the card with color-coded sections based on alert tier.

> This is optional for the workshop — the standard Teams message works fine for testing.

---

## 8.6 Test the alerts

### Option A — Use existing mock data

If your mock data already breaches thresholds (check in KQL):

```kusto
DepositMovement
| where Date == startofday(now())
| summarize Cum_Net_Mil = round(sum(Net_Amount) / 1000000, 1)
```

If `Cum_Net_Mil ≤ −5000`, the Low rule should fire automatically.

### Option B — Lower thresholds temporarily for testing

If data doesn't breach −5,000 M, temporarily adjust the rule thresholds:

| Tier | Production threshold | **Test threshold** |
|---|---|---|
| Low | −5,000 M | **−100 M** |
| Medium | −10,000 M | **−500 M** |
| High | −15,000 M | **−1,000 M** |

1. Edit each rule → change the condition value.
2. Wait for the next evaluation cycle (1–5 minutes).
3. Confirm a Teams message arrives.
4. **Reset thresholds** back to production values after testing.

### Option C — Simulate ingestion (Workshop 06)

1. Drop a CSV file into the ADLS container that would push the cumulative net below −5,000 M.
2. The pipeline ingests it → Activator evaluates on the next cycle → Teams alert fires.

### Verification checklist

After testing, confirm in Teams:

- [ ] Message arrived within 5 minutes of threshold breach
- [ ] Alert flag shows correct tier (Low / Medium / High)
- [ ] Cumulative net amount is displayed
- [ ] **Channel breakdown** is included (ATM, BCMS, ENET, TELL with individual net amounts)
- [ ] Date and time slot are correct

---

## 8.7 Monitor and manage rules

### View rule status

In the Activator item:
- **Green indicator** = rule is active and evaluating.
- **Gray** = rule is paused or disabled.
- **Red** = rule has errors (check the event source query).

### Pause/resume

- To stop alerts temporarily: select a rule → **Pause**.
- Resume when ready.

### Alert history

- Each rule shows a **history** of when it fired.
- Use this to verify de-duplication (should fire once per tier crossing, not repeatedly).

---

## ✅ Exit Criteria

- [ ] Activator item `act-deposit-alerts` exists and is running (green)
- [ ] **3 rules** configured: Low (−5,000 M), Medium (−10,000 M), High (−15,000 M)
- [ ] Each rule targets a **Microsoft Teams** channel
- [ ] Teams notification includes: **Alert flag**, **Cumulative Net**, **Channel breakdown**, **Date/Time**
- [ ] At least **one test alert** successfully delivered to Teams
- [ ] Rules fire **once per breach** (not repeatedly every evaluation cycle)

→ Proceed to **[Workshop 09 — Validate & Monitor](../09-validate-monitor/)**

---

## 📚 Reference Links

| Concept | Documentation |
|---|---|
| Data Activator overview | [What is Data Activator?](https://learn.microsoft.com/fabric/data-activator/data-activator-introduction) |
| Create Activator rules | [Create rules in Data Activator](https://learn.microsoft.com/fabric/data-activator/data-activator-create-triggers-design-mode) |
| Activator + KQL event source | [Get data from Eventhouse](https://learn.microsoft.com/fabric/data-activator/data-activator-get-data-eventstreams) |
| Teams notification action | [Send Teams notifications](https://learn.microsoft.com/fabric/data-activator/data-activator-teams-notifications) |
| Power Automate adaptive cards | [Post adaptive card to Teams](https://learn.microsoft.com/power-automate/create-adaptive-cards-teams) |
| KQL `row_cumsum()` | [row_cumsum()](https://learn.microsoft.com/kusto/query/row-cumsum-function?view=microsoft-fabric) |
| KQL `case()` | [case()](https://learn.microsoft.com/kusto/query/case-function?view=microsoft-fabric) |
| KQL `toscalar()` | [toscalar()](https://learn.microsoft.com/kusto/query/toscalar-function?view=microsoft-fabric) |
