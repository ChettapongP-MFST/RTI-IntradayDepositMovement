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

> ⏰ **Timezone note** — The `Date` column is stored in **ICT (UTC+7, Bangkok)**. KQL's `now()` returns UTC+0, so every query must offset by **+7 h** to match the data: `let now_bkk = now() + 7h;`

### 8.2.1 Intraday cumulative net by Channel

```kusto
// Intraday cumulative net with channel breakdown — the Activator event source
let now_bkk = now() + 7h;   // ⏰ UTC → ICT (Bangkok)
let today = startofday(now_bkk);
DepositMovement
| where Date == today
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
| extend Date = format_datetime(today, 'yyyy-MM-dd')
```

**Column explanation:**

| Column | Meaning |
|---|---|
| `Channel` | Banking channel: `ATM`, `BCMS`, `ENET`, `TELL` |
| `Net_Amount` | Sum of `Net_Amount` (Credit − Debit) per channel per time slot, in **Baht** |
| `Credit_Total` | Sum of credit (inflow) per channel per time slot |
| `Debit_Total` | Sum of debit (outflow) per channel per time slot |
| `Txn_Count` | Total transaction count per channel per time slot |
| `Time` | Latest 30-min time slot for that channel (via `arg_max`) |
| `Cum_Net` | Running cumulative net within each channel, ordered by time — shows how the channel's balance builds through the day |
| `Cum_Net_Channel` | Total cumulative net for the channel across all time slots |
| `Date` | Filtered date in ICT (Bangkok) — verify this equals today's date |

### 8.2.2 Intraday cumulative net total (for threshold check)

```kusto
// Overall intraday cumulative net — used for threshold comparison
let now_bkk = now() + 7h;   // ⏰ UTC → ICT (Bangkok)
let today = startofday(now_bkk);
DepositMovement
| where Date == today
| summarize Cum_Net_Total = sum(Net_Amount)
| extend
    Date = format_datetime(today, 'yyyy-MM-dd'),
    Alert_Flag = case(
        Cum_Net_Total <= -15000000000, "High",
        Cum_Net_Total <= -10000000000, "Medium",
        Cum_Net_Total <=  -5000000000, "Low",
        "Normal"
    ),
    Alert_Time = now_bkk
```

**Column explanation:**

| Column | Meaning |
|---|---|
| `Cum_Net_Total` | Grand total of `Net_Amount` across **all channels** for today, in **Baht** — the single number compared against alert thresholds |
| `Date` | Filtered date in ICT (Bangkok) — verify this equals today's date |
| `Alert_Flag` | Tier label based on `Cum_Net_Total`: `High` (≤ −15 B), `Medium` (≤ −10 B), `Low` (≤ −5 B), or `Normal` |
| `Alert_Time` | Current Bangkok time — when this check was evaluated |

> ⚠ **Units**: The raw data is in **Baht** (not millions). So −5,000 M Baht = `−5,000,000,000` in the KQL filter.

### 8.2.3 Combined query — alert with channel detail

This is the query you will use as the Activator event source. It produces one row per evaluation with the cumulative total, alert flag, and a summary of channel contributions.

The query has **6 phases** — scalars are computed first, then attached to the channel breakdown table:

```
┌──────────────────────────────────────────────────────┐
│  Phase 1   Set up time context (UTC → Bangkok)       │
│  Phase 2   Calculate grand total (single scalar)     │
│  Phase 3   Determine alert tier (case logic)         │
│  Phase 4   Get latest time slot (single scalar)      │
│  Phase 5   Build channel breakdown (4-row table)     │
│  Phase 6   Combine scalars + table → final output    │
└──────────────────────────────────────────────────────┘
```

```kusto
// ── Phase 1: Set up time context ────────────────────
// now() returns UTC. Add 7h → Bangkok time.
// startofday() truncates to midnight → matches the Date column in KQL.
let now_bkk = now() + 7h;   // ⏰ UTC → ICT (Bangkok)
let today = startofday(now_bkk);

// ── Phase 2: Calculate grand total (single scalar) ──
// toscalar() runs the inner query and returns ONE number (not a table).
// It sums Net_Amount across ALL channels, ALL time slots, ALL products for today.
// Example result: 6,100,000 (positive = net inflow) or -10,245,600,000 (net outflow).
let cum_total = toscalar(
    DepositMovement
    | where Date == today
    | summarize sum(Net_Amount)
);

// ── Phase 3: Determine alert tier ───────────────────
// case() works like if/else if/else — evaluates top to bottom, first match wins.
// Order matters: High (-15B) is checked FIRST.
// If cum_total = -12B → fails -15B check → hits -10B check → returns "🟠 Medium".
// Last argument "✅ Normal" is the default (else) when no threshold is breached.
let alert_flag = case(
    cum_total <= -15000000000, "🔴 High",
    cum_total <= -10000000000, "🟠 Medium",
    cum_total <=  -5000000000, "🟡 Low",
    "✅ Normal"
);

// ── Phase 4: Get latest time slot (single scalar) ───
// Returns one value: the most recent Time slot that has data today.
// Example: "23:30-24:00" (all 48 slots loaded) or "10:30-11:00" (partial day).
// Tells the Teams recipient "data is current up to this slot."
let latest_time = toscalar(
    DepositMovement
    | where Date == today
    | summarize max(Time)
);

// ── Phase 5: Build channel breakdown (4-row table) ──
// Produces 4 rows: ATM, BCMS, ENET, TELL.
// summarize ... by Channel → aggregates all time slots & products into one row per channel.
// order by Net asc → most negative (worst outflow) appears first.
// Net_Mil = round(Net / 1000000, 1) → converts Baht → millions with 1 decimal.
// project keeps only Channel and Net_Mil; drops raw Baht columns.
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

// ── Phase 6: Combine scalars + table → final output ─
// Takes the 4-row channel_detail table and appends 5 columns to every row using extend.
// All scalar values (cum_total, alert_flag, latest_time) repeat on every row
// so the Activator / Teams message can reference them from any row.
channel_detail
| extend 
    Cum_Net_Total = round(cum_total / 1000000, 1),
    Alert_Flag = alert_flag,
    Latest_Time = latest_time,
    Alert_Time = now_bkk,
    Date = format_datetime(today, 'yyyy-MM-dd')
```

> 💡 **Why scalars first, table last?** KQL cannot mix scalar and tabular results in one pipeline. So we compute single values (`cum_total`, `alert_flag`, `latest_time`) with `toscalar()`/`case()` in Phases 2–4, then attach them to the channel table in Phase 6 using `extend`.

> 💡 **Why one query, not three?** Activator runs ONE query per evaluation cycle. This single query gives the alert engine everything it needs — threshold check + channel detail + metadata — in one call.

**Expected output** (example):

| Channel | Net_Mil | Cum_Net_Total | Alert_Flag | Latest_Time | Alert_Time | Date |
|---|---|---|---|---|---|---|
| ATM | −3,200.5 | −10,245.6 | 🟠 Medium | 10:30-11:00 | 2026-04-28T17:35:00+07:00 | 2026-04-28 |
| BCMS | −4,100.2 | −10,245.6 | 🟠 Medium | 10:30-11:00 | 2026-04-28T17:35:00+07:00 | 2026-04-28 |
| ENET | −1,800.0 | −10,245.6 | 🟠 Medium | 10:30-11:00 | 2026-04-28T17:35:00+07:00 | 2026-04-28 |
| TELL | −1,144.9 | −10,245.6 | 🟠 Medium | 10:30-11:00 | 2026-04-28T17:35:00+07:00 | 2026-04-28 |

**Column explanation (8.2.3 combined query):**

| Column | Meaning |
|---|---|
| `Channel` | Banking channel — one row per channel |
| `Net_Mil` | Each channel's total `Net_Amount` today, converted to **millions of Baht** (`Net / 1,000,000`). Negative = net outflow |
| `Cum_Net_Total` | Grand total `Net_Amount` across **all 4 channels** today, in **millions of Baht**. Same value on every row — this is the number compared against alert thresholds |
| `Alert_Flag` | Tier label with emoji: ✅ Normal, 🟡 Low (≤ −5,000 M), 🟠 Medium (≤ −10,000 M), 🔴 High (≤ −15,000 M) |
| `Latest_Time` | The most recent 30-min time slot that has data today (e.g. `10:30-11:00`) |
| `Alert_Time` | Current Bangkok time (UTC+7) — when this evaluation ran |
| `Date` | The ICT (Bangkok) date being queried — verify this equals today |

> 💡 **Reading the output:** If `Cum_Net_Total` = −10,245.6 M and `Alert_Flag` = 🟠 Medium, it means the combined net across all channels has breached the −10,000 M threshold. The `Net_Mil` column shows which channels are driving the outflow (most negative at the top, sorted by `Net asc`).

---

## 8.3 Set up the Activator event source

The Activator continuously evaluates the KQL query on a schedule. Each evaluation fetches the latest data, checks whether thresholds are breached, and fires an alert if conditions are met.

> ⚠️ **Important**: You cannot connect an Eventhouse/KQL Database directly from inside the Activator's "Select a data source" dialog. Instead, start from the **KQL Queryset** side.

### Steps

1. Open your **KQL Queryset** in the Fabric workspace (the one connected to the `DepositMovement` database).
2. Paste the **combined query** from section 8.2.3 into the queryset editor.
   > The combined query returns one row per channel with `Cum_Net_Total`, `Alert_Flag`, and `Net_Mil` — everything the alert rules and Teams message need in a single query.
3. **Run** the query to verify it returns results.
   > If it returns **0 rows**, check: (a) there is data for today's date, (b) the UTC+7 offset is correct, (c) the `Date` column value matches today.
4. In the toolbar, click **More…** → **Add alert**.
   > This opens Data Activator with the KQL query already connected as the event source.
5. Name the Activator item `act-deposit-alerts` (or select an existing one).
6. Set the **evaluation frequency** — how often Activator re-runs the query:
   - Recommended: **Every 5 minutes** (balances alert latency vs. KQL compute cost).
   - For testing: **Every 1 minute** (faster feedback, but higher RU consumption).
   > 💡 Each evaluation sends the full KQL query to the Eventhouse. A 5-minute cycle means ~288 executions/day.
7. Verify the preview shows rows with `Alert_Flag`, `Cum_Net_Total`, and `Channel` columns.

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
let now_bkk = now() + 7h;   // ⏰ UTC → ICT (Bangkok)
DepositMovement
| where Date == startofday(now_bkk)
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

Use the pre-generated mock data in **`resources/datasets/extra-mock-up/`**.
Four dates (2026-04-27 → 2026-04-30) are designed to breach **all 3 tiers** within a single intraday.

#### Summary — Alert Breach Windows per Date

| Date | 🟡 Low ≤ −5,000 M | 🟠 Medium ≤ −10,000 M | 🔴 High ≤ −15,000 M | EOD Cumulative |
|---|---|---|---|---|
| **2026-04-27** | **10:00 – 10:30** | **14:30 – 15:00** | **19:00 – 19:30** | −16,500 M |
| **2026-04-28** | **09:30 – 10:00** | **13:00 – 13:30** | **17:30 – 18:00** | −17,000 M |
| **2026-04-29** | **11:00 – 11:30** | **15:30 – 16:00** | **20:30 – 21:00** | −16,800 M |
| **2026-04-30** | **08:30 – 09:00** | **12:00 – 12:30** | **16:00 – 16:30** | −17,200 M |

> 💡 Each date crosses all 3 thresholds at **different times** for a realistic demo.
> Upload CSVs from the target date one by one (in time order) to observe each tier fire sequentially.

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
