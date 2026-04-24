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

1. **[portal.azure.com](https://portal.azure.com)** → open the storage account from Workshop 01.
2. Left menu → **Access control (IAM)** → **+ Add** → **Add role assignment**.
3. **Role** tab: search **Storage Blob Data Contributor** → select → **Next**.
4. **Members** tab:
   - Assign access to — **User, group, or service principal**.
   - **+ Select members** → paste the **Workspace Identity Object ID** from 0.5 (or search by workspace name) → **Select**.
5. **Review + assign** → **Review + assign**.
6. Verify: IAM → **Role assignments** tab → filter by *Storage Blob Data Contributor* → the workspace identity should appear.

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
- [ ] `Storage Blob Data Contributor` role visible on the storage account IAM page
- [ ] **Resource instances** on the Networking blade lists the Fabric workspace

→ Proceed to **[Workshop 01 — Provision ADLS Gen2](../01-provision-adls-gen2/)**
