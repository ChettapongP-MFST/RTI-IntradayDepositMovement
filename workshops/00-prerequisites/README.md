# Workshop 00 — Prerequisites & Trusted Workspace Access

Before starting any deployment, verify Azure and Fabric readiness, collect the information each later workshop will reference, and configure **Trusted Workspace Access** so the Fabric pipeline can reach the firewall-enabled ADLS Gen2.

**Estimated time:** 30–45 minutes
**Next:** [Workshop 01 — Provision ADLS Gen2](../01-provision-adls-gen2/)

---

> This workshop series is designed for **analyst end-users**. Every step runs in a **browser** — Azure Portal, Fabric Portal, Power BI — with no command-line tools required.

## 0.1 Azure prerequisites

| # | Item | How to verify (Portal) |
|---|---|---|
| 1 | Azure subscription with **Contributor** on target resource group | [portal.azure.com](https://portal.azure.com) → Resource group → **Access control (IAM)** → **View my access** |
| 2 | Permission to create **Storage accounts** | Same IAM view — role must be Contributor / Owner / Storage Account Contributor |
| 3 | Permission to assign **Storage Blob Data Contributor** RBAC | IAM → **Check access** → role must be **User Access Administrator** or **Owner** |
| 4 | Ability to deploy an ARM template via portal **Custom deployment** | Portal → search `deploy a custom template` (used in section 0.5 below) |

## 0.2 Fabric prerequisites

| # | Item | How to verify |
|---|---|---|
| 1 | **F-SKU** Fabric capacity (not Trial) | Fabric Admin portal → Capacity settings |
| 2 | Existing workspace attached to the F-SKU capacity | Workspace → Workspace settings → License info |
| 3 | **Workspace identity** enabled for the workspace | Workspace settings → Workspace identity → **+ Add** |
| 4 | Workspace identity is **Contributor** of the workspace | Manage access → ensure identity listed as Contributor |
| 5 | Your account has **Admin** or **Member** role on the workspace | Manage access |
| 6 | Eventhouse licence available (part of Fabric F-SKU) | Create test Eventhouse |

## 0.2.1 Microsoft Teams prerequisite (for Activator alerts)

> ⚠️ **Required for [Workshop 08 — Activator Alerts](../08-activator-alerts/).** If the Activator Teams app is blocked, alert notifications to Teams channels will fail. You can use **Email** alerts as a workaround.

| # | Item | How to verify / fix |
|---|---|---|
| 1 | **Activator Teams app** is allowed in your tenant | [Teams Admin Center](https://admin.teams.microsoft.com) → **Teams apps** → **Manage apps** → search "Activator" → status must be **Allowed** |
| 2 | **App permission policy** includes the Activator app | Teams Admin Center → **Teams apps** → **Permission policies** → ensure the policy assigned to your users does not block the Activator app |

> 💡 **Who can do this?** Only a **Teams Administrator** or **Global Admin** can change app permissions in the Teams Admin Center. If you are not a Teams admin, ask your IT admin to unblock the Activator Teams app for your organization.

## 0.3 Information to collect

Keep these values at hand — later workshops reference them as variables.

| Item | Value |
|---|---|
| Azure Tenant ID | `___________________________________` |
| Azure Subscription ID | `___________________________________` |
| Resource Group (new or existing) | `___________________________________` |
| Region | `___________________________________` |
| Storage Account name (3–24 chars, lowercase) | `___________________________________` |
| Container | `intraday-deposits` |
| Incoming folder prefix | `incoming/` |
| Fabric Workspace name | `___________________________________` |
| Fabric Workspace GUID | `___________________________________` |
| Fabric Workspace Identity (object ID) | `___________________________________` |
| Eventhouse name | `eh-rti-deposit` |
| KQL Database name | `DepositMovement` |

> **Tip:** Get the workspace GUID from the URL bar when the workspace is open:
> `https://app.fabric.microsoft.com/groups/<WORKSPACE-GUID>/...`

## 0.4 Sign in

1. Open **[portal.azure.com](https://portal.azure.com)** in your browser → sign in with your work account.
2. Top-right → subscription filter → ensure the **target subscription** is selected.
3. Open **[app.fabric.microsoft.com](https://app.fabric.microsoft.com)** in a second tab → sign in → open the **target Fabric workspace**.

## ✅ Checkpoint — Prerequisites ready

- [ ] All rows in **0.1** and **0.2** checked in the portal
- [ ] All values in **0.3** filled
- [ ] Azure Portal and Fabric Portal both open in your browser with the correct tenant selected

Continue below to configure Trusted Workspace Access.

---

## 0.5 Create the Fabric Workspace Identity

Allow the firewall-enabled ADLS Gen2 to be accessed by the Fabric pipeline using **Workspace Identity** + a **resource instance rule**. This is the preferred path (no gateway required) and is supported for `Microsoft.Storage.BlobCreated` events.

1. Open **Fabric Portal** → your workspace.
2. Top-right → **Workspace settings** → left menu → **Workspace identity**.
3. Click **+ Workspace identity** → **Add**. Fabric provisions a service principal with the same name as the workspace.
4. Copy the **Object (principal) ID** shown after creation — you'll use it in 0.6.

## 0.6 Grant RBAC on the storage account (Azure Portal)

Two roles are required on the storage account:

| Role | Purpose | Needed by |
|---|---|---|
| **Storage Blob Data Contributor** | Read/write blobs in the `intraday-deposits` container | Pipeline (Copy activity) |
| **EventGrid EventSubscription Contributor** | Create Event Grid subscriptions for `BlobCreated` events | Event-based trigger ([Workshop 05](../05-event-trigger/)) |

### 0.6.1 Assign Storage Blob Data Contributor

1. **[portal.azure.com](https://portal.azure.com)** → open the storage account from Workshop 01.
2. Left menu → **Access control (IAM)** → **+ Add** → **Add role assignment**.
3. **Role** tab: search **Storage Blob Data Contributor** → select → **Next**.
4. **Members** tab:
   - Assign access to — **User, group, or service principal**.
   - **+ Select members** → paste the **Workspace Identity Object ID** from 0.5 (or search by workspace name) → **Select**.
5. **Review + assign** → **Review + assign**.
6. Verify: IAM → **Role assignments** tab → filter by *Storage Blob Data Contributor* → the workspace identity should appear.

### 0.6.2 Assign EventGrid EventSubscription Contributor

> 💡 This role allows Fabric to create an Event Grid subscription on the storage account when you set up the event-based trigger in [Workshop 05](../05-event-trigger/). Without it, the "Connect" step will fail with a permissions error.

1. Still on the storage account → **Access control (IAM)** → **+ Add** → **Add role assignment**.
2. **Role** tab: search **EventGrid EventSubscription Contributor** → select → **Next**.
3. **Members** tab:
   - Assign access to — **User, group, or service principal**.
   - **+ Select members** → select **your own user account** (the person creating the trigger in Fabric) → **Select**.
4. **Review + assign** → **Review + assign**.
5. Verify: IAM → **Role assignments** tab → filter by *EventGrid EventSubscription Contributor* → your account should appear.

> ⚠️ **Who gets this role?** Unlike `Storage Blob Data Contributor` (assigned to the *workspace identity*), `EventGrid EventSubscription Contributor` is assigned to the **user account** that will create the event trigger in Fabric Portal.

## 0.7 Add the Fabric resource instance rule

> ⚠️ The standard **Networking** blade UI does not yet expose Fabric as a resource type. Use one of the two portal-based options below.

### Option A — Azure Portal "Deploy a custom template" (recommended, no command line)

1. Open **[portal.azure.com](https://portal.azure.com)** → top search → **Deploy a custom template** → **Build your own template in the editor**.
2. Paste the template below, then **Save**:
   ```json
   {
     "$schema": "https://schema.management.azure.com/schemas/2019-04-01/deploymentTemplate.json#",
     "contentVersion": "1.0.0.0",
     "parameters": {
       "storageAccountName": { "type": "string" },
       "tenantId":           { "type": "string" },
       "fabricWorkspaceGuid":{ "type": "string" }
     },
     "resources": [
       {
         "type": "Microsoft.Storage/storageAccounts",
         "apiVersion": "2023-05-01",
         "name": "[parameters('storageAccountName')]",
         "location": "[resourceGroup().location]",
         "kind": "StorageV2",
         "sku": { "name": "Standard_LRS" },
         "properties": {
           "networkAcls": {
             "bypass": "AzureServices",
             "defaultAction": "Deny",
             "resourceAccessRules": [
               {
                 "tenantId": "[parameters('tenantId')]",
                 "resourceId": "[concat('/subscriptions/00000000-0000-0000-0000-000000000000/resourcegroups/Fabric/providers/Microsoft.Fabric/workspaces/', parameters('fabricWorkspaceGuid'))]"
               }
             ]
           }
         }
       }
     ]
   }
   ```
3. Fill in parameters: Subscription, Resource group (existing), `storageAccountName`, `tenantId`, `fabricWorkspaceGuid`.
4. **Review + create** → **Create**.

### Option B — Ask your Azure admin

If custom-template deployment is restricted in your tenant, send the admin the script at [`scripts/03-add-resource-instance-rule.ps1`](scripts/03-add-resource-instance-rule.ps1). This is a one-time action.

## 0.8 Verify Trusted Workspace Access

1. Storage account → left menu → **Security + networking** → **Networking** → scroll to **Resource instances**.
2. You should see a row with **Resource type** `Microsoft.Fabric/workspaces` and your workspace GUID.

## ✅ Exit Criteria

- [ ] All rows in **0.1** and **0.2** checked in the portal
- [ ] All values in **0.3** filled
- [ ] Azure Portal and Fabric Portal both open in your browser with the correct tenant selected
- [ ] Workspace identity created in Fabric; Object ID captured
- [ ] `Storage Blob Data Contributor` role visible on the storage account IAM page (assigned to workspace identity)
- [ ] `EventGrid EventSubscription Contributor` role visible on the storage account IAM page (assigned to your user account)
- [ ] **Resource instances** on the Networking blade lists the Fabric workspace

→ Proceed to **[Workshop 01 — Provision ADLS Gen2](../01-provision-adls-gen2/)**

---

## Appendix A — Mock Dataset Analysis

The workshop uses 16 pre-generated CSV files in [`resources/datasets/`](../../resources/datasets/) to simulate intraday deposit movement data. This appendix describes the data structure, dimensions, and what to expect when the pipeline processes them.

### File inventory

| # | File | Time Window |
|---|---|---|
| 1 | `mock_0000_0030.csv` | 00:00-00:30 |
| 2 | `mock_0030_0100.csv` | 00:30-01:00 |
| 3 | `mock_0100_0130.csv` | 01:00-01:30 |
| 4 | `mock_0130_0200.csv` | 01:30-02:00 |
| 5 | `mock_0200_0230.csv` | 02:00-02:30 |
| 6 | `mock_0230_0300.csv` | 02:30-03:00 |
| 7 | `mock_0300_0330.csv` | 03:00-03:30 |
| 8 | `mock_0330_0400.csv` | 03:30-04:00 |
| 9 | `mock_0400_0430.csv` | 04:00-04:30 |
| 10 | `mock_0430_0500.csv` | 04:30-05:00 |
| 11 | `mock_0500_0530.csv` | 05:00-05:30 |
| 12 | `mock_0530_0600.csv` | 05:30-06:00 |
| 13 | `mock_0600_0630.csv` | 06:00-06:30 |
| 14 | `mock_0630_0700.csv` | 06:30-07:00 |
| 15 | `mock_0700_0730.csv` | 07:00-07:30 |
| 16 | `mock_0730_0800.csv` | 07:30-08:00 |

**Total:** 16 files × 24 rows = **384 rows** (all for date `2026-03-31`)

### CSV columns

| Column | Type | Example | Description |
|---|---|---|---|
| `Date` | date | `2026-03-31` | Business date |
| `Time` | string | `00:00-00:30` | 30-minute time window |
| `Product` | string | `Fixed` | Deposit product type |
| `Channel` | string | `ATM` | Transaction channel |
| `Channel_Group` | string | `Offline` | Channel grouping |
| `Transaction_Type` | string | `On-Us` | On-Us or Off-Us |
| `Credit_Amount` | integer | `940263` | Credit amount (THB) |
| `Debit_Amount` | integer | `889524` | Debit amount (THB) |
| `Net_Amount` | integer | `50739` | Credit − Debit (can be negative) |
| `Credit_Txn` | integer | `15` | Number of credit transactions |
| `Debit_Txn` | integer | `229` | Number of debit transactions |
| `Total_Txn` | integer | `244` | Credit_Txn + Debit_Txn |

### Dimensions — 24 rows per file

Each file contains the **full cross-product** of 3 dimensions:

| Dimension | Values | Count |
|---|---|---|
| **Product** | `Fixed`, `Saving`, `Current` | 3 |
| **Channel** | `ATM`, `BCMS`, `ENET`, `TELL` | 4 |
| **Transaction_Type** | `On-Us`, `Off-Us` | 2 |
| **Total combinations** | 3 × 4 × 2 | **24** |

### Channel → Channel_Group mapping

| Channel | Channel_Group | Description |
|---|---|---|
| `ATM` | Offline | Automated Teller Machine |
| `BCMS` | Online | Business Cash Management System |
| `ENET` | Online | Electronic / Internet Banking |
| `TELL` | Offline | Teller (branch counter) |

### Numeric ranges

| Column | Min | Max | Notes |
|---|---|---|---|
| `Credit_Amount` | 0 | ~1,008,682 | Can be zero |
| `Debit_Amount` | 0 | ~989,024 | Can be zero |
| `Net_Amount` | ~-830,793 | ~+544,534 | Negative = net outflow |
| `Credit_Txn` | 12 | 299 | |
| `Debit_Txn` | 11 | 300 | |
| `Total_Txn` | 60 | 573 | |

### Data integrity checks

These relationships hold for **every row** across all 16 files:

| Rule | Formula |
|---|---|
| Net = Credit − Debit | `Net_Amount = Credit_Amount − Debit_Amount` |
| Total = Credit + Debit | `Total_Txn = Credit_Txn + Debit_Txn` |

### Expected counts after full ingestion (all 16 files)

| Table | Rows | Explanation |
|---|---|---|
| `DepositMovement` (Bronze) | **384** | 16 files × 24 rows |
| `dbo.ProcessedFiles` (Audit) | **16** | 1 row per file (Status = Success) |
| `Summary_Alert_Channel` (Gold) | **64** | 16 time windows × 4 channels |

> The Gold table (`Summary_Alert_Channel`) groups by `Date + Time + Channel`, collapsing 3 products × 2 transaction types = 6 source rows into 1 Gold row per time window per channel.
