# Workshop 03 — Trusted Workspace Access (Portal)

Allow the firewall-enabled ADLS Gen2 to be accessed by the Fabric pipeline using **Workspace Identity** + a **resource instance rule**. This is the preferred path (no gateway required) and is supported for `Microsoft.Storage.BlobCreated` events.

**Prerequisite:** [Workshop 02](../02-eventhouse-kql-tables/) complete
**Next:** [Workshop 04 — Data Pipeline](../04-data-pipeline/)

---

## 3.1 Create the Fabric Workspace Identity

1. Open **Fabric Portal** → your workspace.
2. Top-right → **Workspace settings** → left menu → **Workspace identity**.
3. Click **+ Workspace identity** → **Add**. Fabric provisions a service principal with the same name as the workspace.
4. Copy the **Object (principal) ID** shown after creation — you'll use it in 3.2.

## 3.2 Grant RBAC on the storage account (Azure Portal)

1. **[portal.azure.com](https://portal.azure.com)** → open the storage account from Workshop 01.
2. Left menu → **Access control (IAM)** → **+ Add** → **Add role assignment**.
3. **Role** tab: search **Storage Blob Data Contributor** → select → **Next**.
4. **Members** tab:
   - Assign access to — **User, group, or service principal**.
   - **+ Select members** → paste the **Workspace Identity Object ID** from 3.1 (or search by workspace name) → **Select**.
5. **Review + assign** → **Review + assign**.
6. Verify: IAM → **Role assignments** tab → filter by *Storage Blob Data Contributor* → the workspace identity should appear.

## 3.3 Add the Fabric resource instance rule

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

## 3.4 Verify

1. Storage account → left menu → **Security + networking** → **Networking** → scroll to **Resource instances**.
2. You should see a row with **Resource type** `Microsoft.Fabric/workspaces` and your workspace GUID.

## ✅ Exit Criteria

- [ ] Workspace identity created in Fabric; Object ID captured
- [ ] `Storage Blob Data Contributor` role visible on the storage account IAM page
- [ ] **Resource instances** on the Networking blade lists the Fabric workspace
- [ ] Test from Workshop 04 (pipeline connection **Test connection**) succeeds

→ Proceed to **[Workshop 04 — Data Pipeline](../04-data-pipeline/)**
