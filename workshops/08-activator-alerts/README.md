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

### 8.2.3 Combined query — alert with channel detail (single-row pivot)

This is the query you will use as the Activator event source. It produces **one row** per evaluation with the cumulative total, alert flag, and each channel's net pivoted into separate columns.

The query has **5 phases** — scalars are computed first, then channels are pivoted into a single row:

```
┌──────────────────────────────────────────────────────┐
│  Phase 1   Set up time context (UTC → Bangkok)       │
│  Phase 2   Calculate grand total (single scalar)     │
│  Phase 3   Determine alert tier (case logic)         │
│  Phase 4   Get latest time slot (single scalar)      │
│  Phase 5   Pivot channels into ONE row + metadata    │
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

// ── Phase 5: Pivot channels into ONE row + metadata ─
// First: summarize Net per Channel (4 rows).
// Then: take_anyif() picks the value for each specific channel → collapses into 1 row.
// Finally: extend attaches scalars (cum_total, alert_flag, etc.) to the single row.
// Result: ONE row with ATM_Net, BCMS_Net, ENET_Net, TELL_Net + alert metadata.
DepositMovement
| where Date == today
| summarize Net = round(sum(Net_Amount) / 1000000, 1) by Channel
| summarize
    ATM_Net  = take_anyif(Net, Channel == "ATM"),
    BCMS_Net = take_anyif(Net, Channel == "BCMS"),
    ENET_Net = take_anyif(Net, Channel == "ENET"),
    TELL_Net = take_anyif(Net, Channel == "TELL")
| extend
    Cum_Net_Total = round(cum_total / 1000000, 1),
    Alert_Flag    = alert_flag,
    Latest_Time   = latest_time,
    Alert_Time    = now_bkk,
    Date          = format_datetime(today, 'yyyy-MM-dd')
```

> 💡 **Why pivot into one row?** Activator sends **one Teams message per row**. With 4 rows (one per channel), you'd get 4 duplicate messages. By pivoting, we get **1 message** that includes all channel values via `{ATM_Net}`, `{BCMS_Net}`, `{ENET_Net}`, `{TELL_Net}` placeholders.

> 💡 **Why one query, not three?** Activator runs ONE query per evaluation cycle. This single query gives the alert engine everything it needs — threshold check + channel detail + metadata — in one call.

**Expected output** (1 row):

| ATM_Net | BCMS_Net | ENET_Net | TELL_Net | Cum_Net_Total | Alert_Flag | Latest_Time | Alert_Time | Date |
|---|---|---|---|---|---|---|---|---|
| −523.6 | −570.9 | −534.5 | −548.7 | −2,177.8 | ✅ Normal | 05:30-06:00 | 2026-05-01T10:57:… | 2026-05-01 |

**Column explanation:**

| Column | Meaning |
|---|---|
| `ATM_Net` | ATM channel's total `Net_Amount` today in **millions of Baht**. Negative = net outflow |
| `BCMS_Net` | BCMS channel's total `Net_Amount` today in **millions of Baht** |
| `ENET_Net` | ENET channel's total `Net_Amount` today in **millions of Baht** |
| `TELL_Net` | TELL channel's total `Net_Amount` today in **millions of Baht** |
| `Cum_Net_Total` | Grand total `Net_Amount` across **all 4 channels** today in **millions of Baht** — this is the number compared against alert thresholds |
| `Alert_Flag` | Tier label with emoji: ✅ Normal, 🟡 Low (≤ −5,000 M), 🟠 Medium (≤ −10,000 M), 🔴 High (≤ −15,000 M) |
| `Latest_Time` | The most recent 30-min time slot that has data today (e.g. `10:30-11:00`) |
| `Alert_Time` | Current Bangkok time (UTC+7) — when this evaluation ran |
| `Date` | The ICT (Bangkok) date being queried — verify this equals today |

> 💡 **Reading the output:** If `Cum_Net_Total` = −10,245.6 M and `Alert_Flag` = 🟠 Medium, it means the combined net across all channels has breached the −10,000 M threshold. Compare `ATM_Net`, `BCMS_Net`, `ENET_Net`, `TELL_Net` to see which channels are driving the outflow.

---

## 8.3 Set up the Activator event source

The Activator continuously evaluates the KQL query on a schedule. Each evaluation fetches the latest data, checks whether thresholds are breached, and fires an alert if conditions are met.

> ⚠️ **Important**: You cannot connect an Eventhouse/KQL Database directly from inside the Activator's "Select a data source" dialog. Instead, start from the **KQL Queryset** side.

### Steps

1. Open your **KQL Queryset** in the Fabric workspace (the one connected to the `DepositMovement` database).
2. Paste the **combined query** from section 8.2.3 into the queryset editor.
   > The combined query returns **one row** with `Cum_Net_Total`, `Alert_Flag`, and per-channel columns (`ATM_Net`, `BCMS_Net`, `ENET_Net`, `TELL_Net`) — everything the alert rule and Teams message need in a single query.
3. **Run** the query to verify it returns results.
   > If it returns **0 rows**, check: (a) there is data for today's date, (b) the UTC+7 offset is correct, (c) the `Date` column value matches today.
4. In the toolbar, click **More…** → **Add alert**.
5. In the **Add rule** dialog, fill in:
   - **Rule name**: `rule_Net_Amount_alert`
   - **Source**: auto-filled as `DepositMovement` (from the KQL Queryset).
   - **Query**: auto-filled with the combined query from step 2.
   - **Run query every**: `5 minutes` (recommended) or `1 minute` (for testing).
   - **Condition**: `On each event` (default — will be refined in section 8.4).
   - **Action**: `Message me in Teams`.
6. **Save location**: choose or create `act-deposit-alerts`.
7. Click **Create**.
   > A confirmation dialog **"Alert created"** appears — click **Open** to go to the Activator.

---

## 8.4 Configure the alert rule

After clicking **Open**, you are inside `act-deposit-alerts` with the rule `rule_Net_Amount_alert` selected.

The left Explorer panel shows:
```
DepositMovement
  └─ DepositMovement event
       └─ rule_Net_Amount_alert   (Running)
```

### Configure the Condition

In the **Definition** tab (right panel), under **Condition 1**:

1. Change **Operation** from `On every value` → **`Is less than or equal to`** (numeric).
2. **Column**: select `Cum_Net_Total`.
3. **Value**: enter `-5000`.
   > This triggers when the cumulative net outflow breaches the 🟡 Low threshold (−5,000 M).
   > Since the KQL query outputs values in millions, `−5000` means −5,000 M Baht.

> 💡 **Single rule vs. three rules**: Because the KQL query already outputs `Alert_Flag` (Normal / Low / Medium / High), you can use a **single rule** with:
> - Operation: **`Is not equal to`** (string)
> - Column: `Alert_Flag`
> - Value: `Normal`
>
> This fires for **any** tier (Low, Medium, High). The `Alert_Flag` value in the Teams message tells you which tier was breached.

### Configure the Action

Scroll down to the **Action** section (see section 8.5 for Teams message template).

### Save

Click **Save and update** at the bottom right.

### Quick test

Click **Send me a test action** in the toolbar to verify the Teams connection works before waiting for a real trigger.

---

## 8.5 Configure the Microsoft Teams action

For the rule, configure the Teams notification:

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
│ ATM     │ {ATM_Net}  │
│ BCMS    │ {BCMS_Net} │
│ ENET    │ {ENET_Net} │
│ TELL    │ {TELL_Net} │
└─────────┴────────────┘

Action Required:
• Low (-5,000M): Monitor closely
• Medium (-10,000M): Escalate to Treasury
• High (-15,000M): Immediate management action

Dashboard: [Open Power BI Report]
```

> 💡 The query returns **one row** with pivoted channel columns. Use the **Insert dynamic content** dropdown to map each `{field}` to the corresponding query column. This ensures **one Teams message** per alert with all 4 channels included.

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
All 31 days of May 2026 (2026-05-01 → 2026-05-31) are designed to breach **all 3 tiers** within a single intraday.

#### Summary — Alert Breach Windows per Date

| Date | 🟡 Low ≤ −5,000 M | 🟠 Medium ≤ −10,000 M | 🔴 High ≤ −15,000 M | EOD Cumulative |
|---|---|---|---|---|
| **2026-05-01** | **08:30 – 09:00** | **12:30 – 13:00** | **16:30 – 17:00** | −17,500 M |
| **2026-05-02** | **09:00 – 09:30** | **13:00 – 13:30** | **17:30 – 18:00** | −17,200 M |
| **2026-05-03** | **09:30 – 10:00** | **14:00 – 14:30** | **18:30 – 19:00** | −16,600 M |
| **2026-05-04** | **10:00 – 10:30** | **14:30 – 15:00** | **19:00 – 19:30** | −16,800 M |
| **2026-05-05** | **10:30 – 11:00** | **15:00 – 15:30** | **19:30 – 20:00** | −17,000 M |
| **2026-05-06** | **08:30 – 09:00** | **13:00 – 13:30** | **17:00 – 17:30** | −17,400 M |
| **2026-05-07** | **09:00 – 09:30** | **13:30 – 14:00** | **18:00 – 18:30** | −16,900 M |
| **2026-05-08** | **09:00 – 09:30** | **13:30 – 14:00** | **17:30 – 18:00** | −17,100 M |
| **2026-05-09** | **09:30 – 10:00** | **14:00 – 14:30** | **18:30 – 19:00** | −16,700 M |
| **2026-05-10** | **10:00 – 10:30** | **14:30 – 15:00** | **18:30 – 19:00** | −17,300 M |
| **2026-05-11** | **08:00 – 08:30** | **12:00 – 12:30** | **16:30 – 17:00** | −17,600 M |
| **2026-05-12** | **08:30 – 09:00** | **12:30 – 13:00** | **17:00 – 17:30** | −16,500 M |
| **2026-05-13** | **09:00 – 09:30** | **13:00 – 13:30** | **17:30 – 18:00** | −17,000 M |
| **2026-05-14** | **09:30 – 10:00** | **13:30 – 14:00** | **18:00 – 18:30** | −16,800 M |
| **2026-05-15** | **10:00 – 10:30** | **14:00 – 14:30** | **18:30 – 19:00** | −17,200 M |
| **2026-05-16** | **08:00 – 08:30** | **12:00 – 12:30** | **16:00 – 16:30** | −17,500 M |
| **2026-05-17** | **08:30 – 09:00** | **12:30 – 13:00** | **16:30 – 17:00** | −16,600 M |
| **2026-05-18** | **08:30 – 09:00** | **13:00 – 13:30** | **17:30 – 18:00** | −17,100 M |
| **2026-05-19** | **09:00 – 09:30** | **13:30 – 14:00** | **18:00 – 18:30** | −16,900 M |
| **2026-05-20** | **09:30 – 10:00** | **14:00 – 14:30** | **18:30 – 19:00** | −17,400 M |
| **2026-05-21** | **08:00 – 08:30** | **11:30 – 12:00** | **15:30 – 16:00** | −17,300 M |
| **2026-05-22** | **08:00 – 08:30** | **12:00 – 12:30** | **16:00 – 16:30** | −16,700 M |
| **2026-05-23** | **08:30 – 09:00** | **12:30 – 13:00** | **16:30 – 17:00** | −17,000 M |
| **2026-05-24** | **08:30 – 09:00** | **13:00 – 13:30** | **17:00 – 17:30** | −16,500 M |
| **2026-05-25** | **09:00 – 09:30** | **13:30 – 14:00** | **17:30 – 18:00** | −17,200 M |
| **2026-05-26** | **07:30 – 08:00** | **11:30 – 12:00** | **16:00 – 16:30** | −17,600 M |
| **2026-05-27** | **08:00 – 08:30** | **12:00 – 12:30** | **16:30 – 17:00** | −16,800 M |
| **2026-05-28** | **08:00 – 08:30** | **12:30 – 13:00** | **17:00 – 17:30** | −17,100 M |
| **2026-05-29** | **08:30 – 09:00** | **13:00 – 13:30** | **17:30 – 18:00** | −16,900 M |
| **2026-05-30** | **09:00 – 09:30** | **13:30 – 14:00** | **18:00 – 18:30** | −17,400 M |
| **2026-05-31** | **08:00 – 08:30** | **12:00 – 12:30** | **16:00 – 16:30** | −17,000 M |

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
