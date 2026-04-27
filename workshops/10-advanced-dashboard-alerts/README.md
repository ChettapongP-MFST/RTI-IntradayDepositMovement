# Workshop 10 — Advanced Dashboard & Alerts (Gold Layer)

Build a production-grade **near real-time dashboard** and a comprehensive set of **Activator alert rules** driven by the `Summary_Alert_Channel_v2` Gold table.

This workshop gives you a fully guided, click-by-click walkthrough. No scripting required.

**Prerequisite:** [Workshop 09](../09-validate-monitor/) complete — full pipeline running end-to-end with data in `DepositMovement`
**Next:** You've completed the full workshop series! 🎉

---

## What You Will Build

| # | Item | Fabric Component |
|---|---|---|
| A | Gold table v2 with ratio metrics | Eventhouse / KQL Database |
| B | Power BI report — 4 pages, 30-second refresh | Power BI |
| C | 6 production alert rules → Microsoft Teams | Data Activator |

---

## Data Sources Reference

| Name | Where to Find | Used For |
|---|---|---|
| `DepositMovement` | KQL Database `DepositMovement` | Transaction-level detail |
| `Summary_Alert_Channel_v2` | KQL Database `DepositMovement` (created in this workshop) | Pre-aggregated daily KPIs |
| `dbo.ProcessedFiles` | Warehouse `wh_control_framework` | Pipeline health & audit |

---

## 10.1 Update the Gold Table (Add Ratio Columns)

The existing Gold table needs two extra ratio columns that Activator will use as alert thresholds:
- **`OffUs_Ratio`** — what fraction of transactions are Off-Us (external settlement)
- **`Debit_Credit_Ratio`** — how much debit versus credit (high ratio = cash drain risk)

### 10.1.1 Open the KQL Database

1. Go to [https://fabric.microsoft.com](https://fabric.microsoft.com) and sign in.
2. In the left navigation bar, click **Workspaces** → select your workspace (e.g., `ws-rti-deposit`).
3. In the workspace item list, find **`DepositMovement`** with the Eventhouse icon (looks like a lightning bolt or hexagon).
4. Click **`DepositMovement`** to open the Eventhouse.
5. On the left panel inside the Eventhouse, click the **KQL Database** named **`DepositMovement`** (it may already be selected automatically).
6. In the top toolbar, click **Query** (or **Explore your data**) to open the KQL query editor. A blank query pane appears in the main area.

### 10.1.2 Run the stored procedure update

1. In the KQL query editor, click **+ New query** tab — look for the `+` icon in the tab row near the top of the query pane.
2. A blank query tab opens.
3. Paste the entire block below into the query tab:

```kusto
// Step 1: Remove the old procedure so we can recreate it with new columns
.drop procedure sp_Recalculate_Summary_Alert_Channel ifexists

// Step 2: Create the updated procedure
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
        UpdatedAtUtc       = now(),
        OffUs_Ratio        = todouble(Debit_Txn_Total) / iff(Txn_Count == 0, 1.0, todouble(Txn_Count)),
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

4. Click the **Run** button (▶ triangle) at the top of the query pane, or press **Shift+Enter**.
5. In the results panel at the bottom, you should see: `Procedure 'sp_Recalculate_Summary_Alert_Channel' was created successfully.`

### 10.1.3 Populate the Gold table now

1. Click the **+ New query** tab again (same `+` icon).
2. Paste and run the following in one go:

```kusto
// Trigger the procedure to populate the Gold table
exec sp_Recalculate_Summary_Alert_Channel;

// Verify data landed
Summary_Alert_Channel_v2
| order by Date desc, Channel
| limit 20
```

3. Click **Run** (▶).
4. The results panel should show rows with 11 columns: `Date`, `Channel`, `Credit_Total`, `Debit_Total`, `Net_Amount`, `Txn_Count`, `Credit_Txn_Total`, `Debit_Txn_Total`, `OffUs_Ratio`, `Debit_Credit_Ratio`, `UpdatedAtUtc`.

> ✅ If rows appear, the Gold table is ready. Proceed to section 10.2.

---

## 10.2 Create the Power BI Report

### 10.2.1 Launch Power BI from Fabric

1. You should still be inside the KQL Database `DepositMovement` in Fabric.
2. In the **top toolbar**, click **Explore your data**.
3. A dropdown appears — click **Build a Power BI report**.
4. The Power BI report editor opens inside Fabric (in the same browser tab or a new one).
   - On the right side you'll see a **Data** panel listing your KQL tables: `DepositMovement`, `Summary_Alert_Channel_v2`.
   - In the centre is a blank report canvas.
   - The connection is already set to **DirectQuery** (live query — data always fresh).

### 10.2.2 Add the Warehouse table (Pipeline Audit data)

1. In the Power BI report editor, click the **Home** tab in the top ribbon.
2. Click **Get data** (the database icon with a down arrow).
3. In the search box, type `Warehouse` → select **Microsoft Fabric Warehouse** from the results → click **Connect**.
4. A list of workspaces and items appears. Navigate to your workspace → expand it → find **`wh_control_framework`** → click on it.
5. A navigator window opens showing `dbo` schema. Expand **dbo** → check the box next to **`ProcessedFiles`**.
6. Click **Load** (bottom right of the navigator).
7. In the connectivity mode dialog, select **Import** → click **OK**.
   - Import is fine for audit data since it doesn't need sub-second freshness.
8. Wait a few seconds for the import to complete. You will see `ProcessedFiles` appear in the **Data** panel on the right.

### 10.2.3 Create table relationships

Power BI needs to know how the tables are linked to each other.

1. On the left sidebar of the Power BI editor, click the **Model view** icon (looks like three boxes connected by lines — the third icon from the top in the left sidebar).
2. You will see three table boxes on screen: `DepositMovement`, `Summary_Alert_Channel_v2`, `ProcessedFiles`.
3. **Create Relationship 1 — Date:**
   - In the `DepositMovement` box, find the `Date` field.
   - Click and **hold** on `Date`, then **drag** it to the `Date` field in the `Summary_Alert_Channel_v2` box, then **release**.
   - A dialog box appears. Check that it shows:
     - From table: `DepositMovement`, Column: `Date`
     - To table: `Summary_Alert_Channel_v2`, Column: `Date`
     - Cardinality: **Many to one (\*:1)**
   - Click **OK**.
4. **Create Relationship 2 — Channel:**
   - Drag `Channel` from `DepositMovement` → drop on `Channel` in `Summary_Alert_Channel_v2`.
   - In the dialog: confirm Many-to-one → click **OK**.
5. A relationship line should now connect the two tables.
6. Click the **Report view** icon (bar chart icon — first icon in the left sidebar) to go back to the canvas.

### 10.2.4 Create DAX Measures

Measures are calculated values that Power BI uses for your KPI visuals.

> **How to add a measure:** In the **Data** panel (right side), right-click a table name → click **New measure** → type the formula in the formula bar → press **Enter**.

**Add these measures to the `DepositMovement` table:**

Right-click **`DepositMovement`** → **New measure** → paste formula → **Enter** → repeat for each:

```
Total Credit = SUM('DepositMovement'[Credit_Amount])
```
```
Total Debit = SUM('DepositMovement'[Debit_Amount])
```
```
Net Position = SUM('DepositMovement'[Net_Amount])
```
```
Total Transactions = SUM('DepositMovement'[Total_Txn])
```

**Add these measures to `Summary_Alert_Channel_v2` table:**

Right-click **`Summary_Alert_Channel_v2`** → **New measure** → paste each:

```
Net Position (Gold) = SUM('Summary_Alert_Channel_v2'[Net_Amount])
```
```
Debit Credit Ratio = AVERAGE('Summary_Alert_Channel_v2'[Debit_Credit_Ratio])
```
```
OffUs Ratio = AVERAGE('Summary_Alert_Channel_v2'[OffUs_Ratio])
```

**Add these measures to the `ProcessedFiles` table:**

Right-click **`ProcessedFiles`** → **New measure** → paste each:

```
Last Ingested = MAX('ProcessedFiles'[IngestedAtUtc])
```
```
Minutes Since Load = DATEDIFF(MAX('ProcessedFiles'[IngestedAtUtc]), UTCNOW(), MINUTE)
```
```
Files Today = CALCULATE(COUNTROWS('ProcessedFiles'), 'ProcessedFiles'[Status] = "Success")
```
```
Failed Files Today = CALCULATE(COUNTROWS('ProcessedFiles'), 'ProcessedFiles'[Status] = "Failed")
```

> 💡 **Tip:** After typing each measure, click the **✓ checkmark** in the formula bar or press **Enter** to save. The measure appears with a calculator icon under the table in the Data panel.

---

## 10.3 Build Page 1 — Real-Time Overview

### Rename the page

1. At the bottom of the canvas, double-click the **Page 1** tab.
2. Type `Overview` → press **Enter**.

### Add 4 KPI Cards (top row)

**Card 1 — Net Position (with colour):**

1. Make sure nothing is selected on the canvas (click a blank area).
2. In the **Visualizations** panel (right side, middle section), click the **Card** icon — it looks like a box with `123` inside.
3. An empty card visual appears on the canvas.
4. In the **Data** panel on the right, expand **`DepositMovement`** → find the **`Net Position`** measure (calculator icon) → drag it onto the card, dropping it onto the **Fields** area under the card visual in the Visualizations panel.
5. The card now shows a number.
6. Click on the card to select it → in the **Format** panel (paint roller icon in the Visualizations area), expand **Callout value** → click **Conditional formatting** (fx button) → **Font color**:
   - Rule 1: If `Net Position` is **greater than** `0` → colour **Green** (`#107C10`)
   - Rule 2: If `Net Position` is **less than** `0` → colour **Red** (`#D13438`)
   - Click **OK**.
7. Still in Format → **General** → **Title** → type `Intraday Net Position`.
8. Resize: drag the corner handles to make it rectangular. Position in the top-left area.

**Card 2 — Total Transactions:**

1. Click a **blank area** of the canvas to deselect everything.
2. Click the **Card** icon again in Visualizations.
3. Drag **`Total Transactions`** measure from `DepositMovement` → into the card's **Fields** well.
4. Format → General → Title → `Total Transactions Today`.
5. Format → Callout value → Display units → **Thousands (K)**.
6. Position to the right of Card 1.

**Card 3 — Total Credit:**

1. Add another **Card** visual.
2. Drag **`Total Credit`** → into Fields.
3. Format → Title → `Total Credit Volume`.
4. Format → Callout value → Display units → **Millions (M)**.
5. Position to the right of Card 2.

**Card 4 — Total Debit:**

1. Add another **Card** visual.
2. Drag **`Total Debit`** → into Fields.
3. Format → Title → `Total Debit Volume`.
4. Format → Callout value → Display units → **Millions (M)**.
5. Position to the right of Card 3.

### Add Net Position Trend (Line Chart)

1. Click a blank area of the canvas.
2. In Visualizations, click the **Line chart** icon (line going up-right).
3. In the **Visualizations** panel under the visual icons, you'll see wells: **X-axis**, **Y-axis**, **Legend**, **Tooltips**.
4. From `DepositMovement` in the Data panel:
   - Drag **`Time`** → drop onto **X-axis** well.
   - Drag **`Net Position`** measure → drop onto **Y-axis** well.
   - Drag **`Channel`** → drop onto **Legend** well.
5. Format → General → Title → `Net Position by 30-Min Slot`.
6. Format → Lines → Line width → `2`.
7. Resize this chart to be wide — it should span most of the middle of the canvas.

### Add 2 Donut Charts (bottom row)

**Donut 1 — Online vs. Offline:**

1. Click blank area of canvas.
2. In Visualizations, click the **Donut chart** icon (circle with a hole in the middle).
3. From `DepositMovement`:
   - Drag **`Channel_Group`** → **Legend** well.
   - Drag **`Total Transactions`** measure → **Values** well.
4. Format → General → Title → `Online vs. Offline Split`.
5. Position in the bottom-left.

**Donut 2 — On-Us vs. Off-Us:**

1. Add another **Donut chart**.
2. Drag **`Transaction_Type`** → **Legend** well.
3. Drag **`Total Transactions`** → **Values** well.
4. Format → Title → `On-Us vs. Off-Us Split`.
5. Position to the right of Donut 1.

### Enable Automatic Page Refresh (30 seconds)

1. Click a **blank area** of the canvas (no visual selected).
2. In the **Format** panel on the right (paint roller icon), scroll down until you see **Page refresh**.
3. Toggle **Page refresh** to **On**.
4. Set type to **Fixed interval**.
5. Set the interval to **30** seconds.

> ✅ Page 1 is complete. You should see 4 cards across the top, a wide line chart in the middle, and 2 donuts at the bottom.

---

## 10.4 Build Page 2 — Channel Drill-Down

### Add the page

1. At the bottom, click the **+** button next to the `Overview` tab.
2. Double-click the new tab → rename it `Channel Drill-Down`.

### Add Date Slicer (top-left)

1. In Visualizations, click the **Slicer** icon (funnel/triangle shape).
2. From `DepositMovement`, drag **`Date`** → **Field** well.
3. Format → Slicer settings → Options → Style → **Between** (shows a date range picker).
4. Format → Title → `Select Date`.
5. Position across the top-left of the canvas.

### Add Channel Group Slicer (top-right)

1. Add another **Slicer**.
2. Drag **`Channel_Group`** from `DepositMovement` → **Field** well.
3. Format → Slicer settings → Style → **Tile** (displays as clickable buttons: Online / Offline).
4. Format → Title → `Channel Group`.
5. Position next to the Date slicer.

### Add Net Position by Channel (Clustered Bar Chart)

1. Click blank area → click **Clustered bar chart** in Visualizations (horizontal bars).
2. Drag **`Channel`** from `DepositMovement` → **Y-axis** well.
3. Drag **`Net Position`** measure → **X-axis** well.
4. Format → Data colors → enable **Conditional formatting** (fx button):
   - Diverging colour: negative values = red, positive = teal/green.
5. Format → Title → `Net Position by Channel`.
6. Add a **Constant line** at `0`: Format → Reference line → Add line → Value = `0`.
7. Position upper-left of main canvas area.

### Add Transaction Volume by Channel

1. Add a **Clustered bar chart**.
2. Drag **`Channel`** → **Y-axis**.
3. Drag **`Total Transactions`** → **X-axis**.
4. Format → Title → `Transaction Volume by Channel`.
5. Position upper-right.

### Add Channel Activity Heatmap (Matrix)

1. Click blank area → click **Matrix** visual in Visualizations (looks like a table grid).
2. Drag **`Channel`** → **Rows** well.
3. Drag **`Time`** → **Columns** well.
4. Drag **`Total Transactions`** → **Values** well.
5. Format → Cell elements → **Background color** → toggle **On** → this applies colour shading to create a heatmap: darker = more transactions.
6. Format → Title → `Channel Activity Heatmap (30-min slots)`.
7. Position in the middle row of the canvas — make it wide.

### Add Off-Us Ratio per Channel (100% Stacked Bar)

1. Click blank area → click **100% stacked bar chart** in Visualizations.
2. Drag **`Channel`** → **Y-axis**.
3. Drag **`Transaction_Type`** → **Legend** well.
4. Drag **`Total Transactions`** → **X-axis**.
5. Format → Title → `On-Us vs. Off-Us by Channel (%)`.
6. Position bottom-left.

### Add Debit/Credit Ratio by Channel

1. Add a **Clustered bar chart**.
2. Drag **`Channel`** → **Y-axis**.
3. Drag **`Debit Credit Ratio`** measure (from `Summary_Alert_Channel_v2`) → **X-axis**.
4. Format → Reference line → **Add line** → Value = `2.0` → Label = `Alert Threshold` → Colour = Red.
5. Format → Title → `Debit/Credit Ratio by Channel`.
6. Position bottom-right.

---

## 10.5 Build Page 3 — Product Analysis

1. Click **+** at the bottom → rename the new page `Product Analysis`.

### Add Product Slicer (top)

1. Add a **Slicer**.
2. Drag **`Product`** from `DepositMovement` → **Field** well.
3. Format → Style → **Tile** (shows Fixed / Saving / Current as buttons).
4. Stretch it across the top of the canvas.

### Add Net Position Gauge

1. Click blank area → click **Gauge** visual in Visualizations (semicircle dial).
2. Drag **`Net Position`** measure → **Value** well.
3. Format → Title → `Net Position by Product` *(use the Product slicer above to filter by product)*.
4. Position top-left.

### Add Credit vs. Debit by Product

1. Add a **Clustered column chart** (vertical bars).
2. Drag **`Product`** → **X-axis**.
3. Drag **`Total Credit`** → **Y-axis** (first field).
4. Drag **`Total Debit`** → **Y-axis** (second field — just drag it below `Total Credit` in the Y-axis well).
5. Format → Title → `Credit vs. Debit by Product`.
6. Position top-right.

### Add Transaction Mix Matrix

1. Add a **Matrix** visual.
2. Drag **`Product`** → **Rows**.
3. Drag **`Channel`** → **Columns**.
4. Drag **`Total Transactions`** → **Values**.
5. Format → Title → `Transaction Mix: Product × Channel`.
6. Position in the middle.

### Add Intraday Trend by Product (Line Chart)

1. Add a **Line chart**.
2. Drag **`Time`** → **X-axis**.
3. Drag **`Net Position`** → **Y-axis**.
4. Drag **`Product`** → **Legend** (gives one line per product: Fixed, Saving, Current).
5. Format → Title → `Intraday Net Trend by Product`.
6. Position at the bottom — make it wide.

---

## 10.6 Build Page 4 — Pipeline Health

1. Click **+** → rename new page `Pipeline Health`.

### Add 4 Health Cards (top row)

**Last File Ingested:**
1. Add a **Card** visual.
2. Drag **`Last Ingested`** measure (from `ProcessedFiles`) → **Fields** well.
3. Format → Title → `Last File Ingested (UTC)`.
4. Position top-left.

**Pipeline Lag:**
1. Add a **Card** visual.
2. Drag **`Minutes Since Load`** measure → **Fields**.
3. Format → Callout value → **Conditional formatting** → Font color:
   - If value > 35 → **Red** (SLA breached)
   - If value ≤ 35 → **Green** (on time)
4. Format → Title → `Pipeline Lag (minutes)`.
5. Position next to the previous card.

**Files Loaded Today:**
1. Add a **Card** visual.
2. Drag **`Files Today`** measure → **Fields**.
3. Format → Title → `Files Loaded Today`.
4. Position next.

**Failed Files:**
1. Add a **Card** visual.
2. Drag **`Failed Files Today`** measure → **Fields**.
3. Format → Callout value → Conditional formatting: if value > 0 → **Red**.
4. Format → Title → `Failed Files`.
5. Position last in the top row.

### Add ProcessedFiles Audit Log (Table)

1. Click blank area → click the **Table** visual in Visualizations (plain grid icon).
2. From `ProcessedFiles`, drag these fields into the **Columns** well one by one:
   - `FileName`
   - `IngestedAtUtc`
   - `Status`
   - `RowCount_`
   - `PipelineName`
   - `ErrorMsg`
3. Format → Cell elements → **Background color** for the `Status` column (click **fx** next to Background color):
   - Rule 1: `Status` contains `Failed` → background **Red** (#FDCDD0)
   - Rule 2: `Status` contains `Success` → background **Green** (#DFF6DD)
   - Rule 3: `Status` contains `Skipped` → background **Yellow** (#FFF4CE)
4. Format → Title → `Ingestion Audit Log`.
5. Click the `IngestedAtUtc` column header in the visual → click the **sort descending** arrow (▼) so newest rows appear first.
6. Make the table wide — position in the middle of the canvas.

### Add Status Over Time (Stacked Bar Chart)

1. Add a **Stacked bar chart**.
2. Drag **`IngestedAtUtc`** from `ProcessedFiles` → **X-axis** (Power BI auto-groups by hour/day).
3. Drag **`FileName`** → **Y-axis** → in the **Y-axis** well, click the dropdown on `FileName` → change from **Sum** to **Count**.
4. Drag **`Status`** → **Legend**.
5. Format → Title → `Ingestion Status Over Time`.
6. Position at the bottom of the canvas.

---

## 10.7 Save and Publish the Report

1. In the top ribbon, click **File** → **Save**.
2. In the save dialog, name the report: `RTI Intraday Deposit — Advanced Dashboard`
3. Click **Save**.
4. Click **File** → **Publish to workspace**.
5. In the dialog, select your workspace (e.g., `ws-rti-deposit`) → click **Select**.
6. A progress bar appears. When done, you'll see: *"Report published successfully"*.
7. Click **Open in Fabric** (or navigate back to the workspace manually).

### Share the report with your team

1. In the Fabric workspace, click on the **`RTI Intraday Deposit — Advanced Dashboard`** Power BI report.
2. In the top-right corner, click **Share** (person icon with a `+` symbol).
3. In the **Share report** panel:
   - Type the email address of the operations team → set **Access level** to **Viewer** → click **Grant access**.
   - Repeat for data engineers → set **Contributor**.
4. Uncheck **Allow recipients to share this report** if you want to control access tightly.
5. Click **Send**.

---

## 10.8 Create the Data Activator Item

Data Activator watches your data continuously and fires alerts when conditions you define are met.

### 10.8.1 Create a new Activator

1. Go back to your Fabric workspace (click **Workspaces** in the left nav → select your workspace).
2. Click **+ New item** in the top toolbar.
3. In the item picker dialog, scroll down or type `Activator` in the search box.
4. Click **Activator** in the results.
5. In the name field, type: `act-deposit-alerts-v2`
6. Click **Create**.
7. The Activator editor opens. You will see:
   - **Left panel:** Sources and Objects (currently empty)
   - **Main canvas:** Design area

---

## 10.9 Define Alert Rules

Each rule follows the same 4-step pattern:
1. **Add event source** — connect to KQL data
2. **Define trigger condition** — when to fire
3. **Write the Teams message** — what to send
4. **Save and activate** the rule

You will create **3 KQL sources** and attach rules to them.

> ⏰ **Timezone note** — The `Date` column is stored in **ICT (UTC+7, Bangkok)**. KQL's `now()` returns UTC+0, so every query that filters on `Date` must offset by **+7 h**: `let now_bkk = now() + 7h;`
> Columns named `*Utc` (e.g. `IngestedAtUtc`, `UpdatedAtUtc`) are already in UTC — no offset needed for those.

---

### Set Up Source 1 — Gold Summary Data

1. In the Activator editor, click **+ New source** (or **+ Add event source**) in the left panel.
2. In the source type picker, select **Eventhouse**.
3. In the connection fields:
   - **Eventhouse:** select `eh-rti-deposit`
   - **KQL Database:** select `DepositMovement`
4. In the **Query** box, paste:

```kusto
Summary_Alert_Channel_v2
| where UpdatedAtUtc >= ago(15m)
| project Channel, Net_Amount, Debit_Total, Credit_Total,
          OffUs_Ratio, Debit_Credit_Ratio, Txn_Count, Date, UpdatedAtUtc
```

5. Click **Test query** to confirm rows appear in the preview.
6. Set **Schedule** (how often Activator checks): `Every 5 minutes`.
7. Name this source: `source-summary-gold`
8. Click **Save source**.

---

### Rule 1 — Net Outflow Alert

1. In the left panel, click **`source-summary-gold`** to select it.
2. Click **+ New rule** (appears in the main canvas or left panel).
3. In the rule editor:
   - **Name:** `Rule 1 - Net Outflow`
   - **Object column:** `Channel` — this tells Activator to track each channel separately
4. **Trigger condition:**
   - Click **+ Add condition**
   - Column: **`Net_Amount`** → Operator: **Less than** → Value: `-2000000`
5. Click **+ Add action** → select **Microsoft Teams**:
   - Click **Sign in** → sign in with your Microsoft 365 account
   - Team: select `RTI Operations` (or your team name)
   - Channel: select `#rti-alerts`
   - Message body:

```
⚠️ Net Outflow Alert
Channel: {Channel}
Net Amount: {Net_Amount}
Date: {Date}
Updated: {UpdatedAtUtc}
```

   > To insert dynamic values like `{Channel}`: click the **lightning bolt** icon (⚡) next to the message box → select the field from the dropdown. It inserts as a placeholder automatically.

6. Click **Save rule**.

---

### Rule 2 — ATM Cash Drain

1. With `source-summary-gold` still selected, click **+ New rule**.
2. **Name:** `Rule 2 - ATM Cash Drain`
3. **Object column:** `Channel`
4. **Trigger conditions** (two conditions — both must be true):
   - Condition 1: **`Channel`** → **Equals** → `ATM`
   - Click **+ Add condition**: **`Debit_Credit_Ratio`** → **Greater than** → `3.0`
5. **Action:** Teams → `#rti-alerts`
6. Message:

```
🏧 ATM Cash Drain Alert
Debit/Credit Ratio: {Debit_Credit_Ratio}
Debit Total: {Debit_Total}
Credit Total: {Credit_Total}
Updated: {UpdatedAtUtc}
```

7. Click **Save rule**.

---

### Rule 3 — Off-Us Volume Spike

1. With `source-summary-gold` selected, click **+ New rule**.
2. **Name:** `Rule 3 - Off-Us Spike`
3. **Object column:** `Channel`
4. **Trigger condition:**
   - **`OffUs_Ratio`** → **Greater than** → `0.70`
5. **Action:** Teams → `#rti-alerts`
6. Message:

```
📊 Off-Us Volume Spike
Channel: {Channel}
Off-Us Ratio: {OffUs_Ratio}
Total Transactions: {Txn_Count}
Updated: {UpdatedAtUtc}
```

7. Click **Save rule**.

---

### Set Up Source 2 — Daily Cumulative Net

1. Click **+ New source** in the left panel.
2. Select **Eventhouse** → `eh-rti-deposit` → `DepositMovement`.
3. Query:

```kusto
let now_bkk = now() + 7h;   // ⏰ UTC → ICT (Bangkok)
Summary_Alert_Channel_v2
| where Date == startofday(now_bkk)
| summarize Cumulative_Net = sum(Net_Amount)
| extend Source = "Daily"
```

4. Schedule: `Every 5 minutes`.
5. Name: `source-daily-cumulative`
6. Click **Save source**.

---

### Rule 4 — Intraday Net Negative

1. Click **`source-daily-cumulative`** in the left panel.
2. Click **+ New rule**.
3. **Name:** `Rule 4 - Net Negative`
4. **Object column:** `Source`
5. **Trigger condition:**
   - **`Cumulative_Net`** → **Less than** → `0`
6. **Action:** Teams → `#rti-executive` channel
7. Message:

```
🚨 Intraday Net Position NEGATIVE
Cumulative Net Today: {Cumulative_Net}
Immediate attention required.
```

8. Click **Save rule**.

---

### Set Up Source 3 — Channel Silence Detection

1. Click **+ New source**.
2. Select **Eventhouse** → `eh-rti-deposit` → `DepositMovement`.
3. Query:

```kusto
let ExpectedChannels = datatable(Channel:string)["ATM","BCMS","ENET","TELL"];
let ActiveChannels = DepositMovement
    | where IngestedAtUtc >= ago(35m)
    | distinct Channel;
ExpectedChannels
| join kind=leftanti ActiveChannels on Channel
| extend AlertTime = now()
```

4. Schedule: `Every 5 minutes`.
5. Name: `source-channel-silence`
6. Click **Save source**.

---

### Rule 5 — Channel Silence

1. Click **`source-channel-silence`** in the left panel.
2. Click **+ New rule**.
3. **Name:** `Rule 5 - Channel Silence`
4. **Object column:** `Channel`
5. **Trigger condition:** Select **"Any row returned"** (the query only returns missing channels, so any result = alert). If Activator requires a column condition, use: `Channel` → **Is not empty**.
6. **Action:** Teams → `#rti-alerts`
7. Message:

```
🔕 Channel Silence Detected
Missing Channel: {Channel}
No transactions in the last 35 minutes.
Check pipeline and source system.
```

8. Click **Save rule**.

---

### Set Up Source 4 — Pipeline Lag (from Power BI)

Rule 6 watches the pipeline lag measure from your Power BI semantic model.

1. Click **+ New source**.
2. Select **Power BI semantic model**.
3. Find and select: **RTI Intraday Deposit — Advanced Dashboard** (the report you published).
4. Select the measure: **`Minutes Since Load`**.
5. Schedule: `Every 5 minutes`.
6. Name: `source-pipeline-lag`
7. Click **Save source**.

---

### Rule 6 — Pipeline SLA Breach

1. Click **`source-pipeline-lag`** in the left panel.
2. Click **+ New rule**.
3. **Name:** `Rule 6 - Pipeline SLA`
4. **Trigger condition:**
   - **`Minutes Since Load`** → **Greater than** → `35`
5. **Action:** Teams → `#rti-ops`
6. Message:

```
⏰ Pipeline SLA Breach
Minutes Since Last Load: {Minutes Since Load}
Expected cadence: every 10 minutes.
Check the event trigger and pipeline in Fabric Monitor Hub.
```

7. Click **Save rule**.

---

## 10.10 Activate All Rules

1. In the Activator left panel, you will see all 4 sources and 6 rules listed.
2. Check each rule — it should show a **grey circle** (inactive) until you start the Activator.
3. At the top of the Activator editor, click the **Start** button (▶ or a button labelled **Start**).
4. All rules should switch to a **green circle** labelled **Active**.
5. The Activator header should show status: **Running**.

> If any rule fails to activate, click on it → check the error message in the details panel → it usually means a connection or query issue. Re-check the KQL query by running it manually in the KQL Database first.

---

## 10.11 Test All Alert Rules

Before handing the solution to operations, verify each alert fires correctly. Lower the thresholds temporarily to force a trigger.

| Rule | Temporary change to trigger it | Expected Teams message |
|---|---|---|
| Rule 1 | In Activator, edit Rule 1 → change `-2000000` to `-1` → Save | `#rti-alerts`: Net Outflow Alert |
| Rule 2 | Edit Rule 2 → change Debit_Credit_Ratio threshold from `3.0` to `0.5` → Save | `#rti-alerts`: ATM Cash Drain Alert |
| Rule 3 | Edit Rule 3 → change OffUs_Ratio from `0.70` to `0.10` → Save | `#rti-alerts`: Off-Us Spike |
| Rule 4 | Edit Rule 4 → change threshold from `0` to `9999999999` → Save | `#rti-executive`: Net Negative |
| Rule 5 | Edit the source query → change `ago(35m)` to `ago(1s)` → Save | `#rti-alerts`: all 4 channels shown as silent |
| Rule 6 | Pause the event trigger (Workshop 05 → Eventstream → Stop) for 40 min | `#rti-ops`: SLA Breach |

**After confirming each alert:**
1. In Activator, click on the rule → click **Edit**.
2. Restore the original threshold value.
3. Click **Save rule**.
4. Re-enable the event trigger if you paused it for Rule 6.

---

## 10.12 Verify the Full End-to-End Flow

1. Upload a new CSV file to ADLS Gen2 (see Workshop 06 for upload steps).
2. In Fabric, click **Monitor** in the left navigation → **Pipeline runs** — watch the `pl_ingest_DepositMovement` pipeline run start automatically.
3. Wait for the pipeline to complete (Status = ✅ **Succeeded**).
4. Open your Power BI report (**Overview** page) — within 30 seconds the data should update with the new batch.
5. In the KQL Database, run:

```kusto
Summary_Alert_Channel_v2
| order by UpdatedAtUtc desc
| limit 5
```

6. Confirm the `UpdatedAtUtc` column shows a timestamp from the last few minutes.
7. In the Warehouse (`wh_control_framework`), open **New SQL query** and run:

```sql
SELECT TOP (5) *
FROM dbo.ProcessedFiles
ORDER BY IngestedAtUtc DESC;
```

8. Confirm a new `Success` row appears for the file you just uploaded.

---

## ✅ Exit Criteria

- [ ] `Summary_Alert_Channel_v2` exists in KQL with 11 columns (including `OffUs_Ratio`, `Debit_Credit_Ratio`)
- [ ] Stored procedure updated successfully — no errors on execution
- [ ] Power BI report `RTI Intraday Deposit — Advanced Dashboard` published to workspace
  - [ ] Page 1 — Overview: 4 cards + trend chart + 2 donuts + APR 30 seconds enabled
  - [ ] Page 2 — Channel Drill-Down: slicers + bar charts + heatmap matrix + ratio chart
  - [ ] Page 3 — Product Analysis: slicer + gauge + column chart + matrix + line chart
  - [ ] Page 4 — Pipeline Health: 4 health cards + audit table + stacked bar
- [ ] All 11 DAX measures created and showing values
- [ ] Report shared: operations = Viewer, data engineers = Contributor
- [ ] Activator item `act-deposit-alerts-v2` created and status = **Running**
- [ ] All 6 alert rules defined and tested — thresholds restored after testing
- [ ] At least one Teams message received for each of the 6 rules
- [ ] End-to-end flow verified: file upload → pipeline → KQL → Power BI refresh → (optional) alert

---

## Reference KQL Queries for Ad-Hoc Validation

Run these anytime in the KQL Database query pane:

```kusto
// Intraday net position by channel (today)
let now_bkk = now() + 7h;   // ⏰ UTC → ICT (Bangkok)
Summary_Alert_Channel_v2
| where Date == startofday(now_bkk)
| project Channel, Net_Amount, Txn_Count, OffUs_Ratio, Debit_Credit_Ratio
| order by Net_Amount asc

// Which channels are active in the last 30 min?
DepositMovement
| where IngestedAtUtc >= ago(30m)
| summarize Txn = count() by Channel
| order by Channel asc

// Recent 2-hour net trend by channel
DepositMovement
| where IngestedAtUtc >= ago(2h)
| summarize Net = sum(Net_Amount), Rows = count() by bin(IngestedAtUtc, 30m), Channel
| order by IngestedAtUtc desc

// Top risk channels right now
let now_bkk = now() + 7h;   // ⏰ UTC → ICT (Bangkok)
Summary_Alert_Channel_v2
| where Date == startofday(now_bkk)
| where Debit_Credit_Ratio > 2.0 or OffUs_Ratio > 0.6
| project Channel, Debit_Credit_Ratio, OffUs_Ratio, Net_Amount
| order by Debit_Credit_Ratio desc
```

**In the Warehouse SQL query pane:**

```sql
-- Latest pipeline runs
SELECT TOP (10) *
FROM dbo.ProcessedFiles
ORDER BY IngestedAtUtc DESC;

-- Today's summary
SELECT Status, COUNT(*) AS Count_
FROM dbo.ProcessedFiles
WHERE CAST(IngestedAtUtc AS DATE) = CAST(GETUTCDATE() AS DATE)
GROUP BY Status;
```
