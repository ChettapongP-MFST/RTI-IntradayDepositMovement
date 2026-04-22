# Workshop 07 — Power BI KPI Report

Build the primary operational dashboard on **Power BI** over the Eventhouse in **DirectQuery** mode, with 30-second automatic page refresh. A Real-Time Dashboard is provided as an optional 7b.

**Prerequisite:** [Workshop 06](../06-simulate-ingestion/) complete
**Next:** [Workshop 08 — Activator Alerts](../08-activator-alerts/)

---

## 7.1 Create the semantic model (DirectQuery on KQL)

1. Open the KQL Database `DepositMovement` in Fabric.
2. Top-right → **Explore your data** → **Build Power BI report**.
3. Connector: **Azure Data Explorer (Kusto)** → **DirectQuery** mode.
4. Select table `DepositMovement`.

Alternative (Power BI Desktop):

- **Get Data** → **Azure Data Explorer (Kusto)**.
- Cluster: your Eventhouse **Query URI** (Eventhouse overview page).
- Database: `DepositMovement`. Table: `DepositMovement`.
- Data Connectivity mode: **DirectQuery**.

## 7.2 DAX measures

```DAX
Total Credit       := SUM('DepositMovement'[Credit_Amount])
Total Debit        := SUM('DepositMovement'[Debit_Amount])
Net Movement       := SUM('DepositMovement'[Net_Amount])
Total Transactions := SUM('DepositMovement'[Total_Txn])
Latest Load        := MAX('DepositMovement'[load_ts])
Minutes Since Last Load := DATEDIFF([Latest Load], UTCNOW(), MINUTE)
```

## 7.3 Report pages

| Page | Key visuals |
|---|---|
| **Intraday overview** | Net Movement trend by 30-min slot · Credit vs Debit clustered column · KPI tiles `Latest Load`, `Minutes Since Last Load` |
| **Channel breakdown** | Bar Net by Channel · Matrix Channel × Transaction_Type · Donut Channel_Group |
| **Product split** | Pie Product · Line Net_Amount by Product over Time |
| **Data freshness & audit** | Cards from `ProcessedFiles` Status counts · Table of `Failed` rows with `ErrorMsg` |

## 7.4 Enable Automatic Page Refresh (APR)

Report canvas → **Format page** → **Page refresh** → **On** → **Fixed interval** → **30 seconds**.

> DirectQuery on KQL supports APR. For heavy visuals tune to 1 min.

## 7.5 Publish

Save to the same Fabric workspace; share with operations (Viewer/Contributor as appropriate).

## 7.6 (Optional) Step 7b — Real-Time Dashboard

Inside the Eventhouse:

1. **+ New Real-Time Dashboard**.
2. Add tiles from KQL queries (e.g., Net by Channel last 30 min).
3. RTD refreshes sub-second and supports direct Activator rules from tile thresholds.

## ✅ Exit Criteria

- [ ] Power BI report published, APR = 30 s
- [ ] All 4 pages render live data
- [ ] Operations team has access

→ Proceed to **[Workshop 08 — Activator Alerts](../08-activator-alerts/)**
