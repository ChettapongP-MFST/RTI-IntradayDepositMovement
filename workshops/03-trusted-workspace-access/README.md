# Workshop 03 — Trusted Workspace Access

Allow the firewall-enabled ADLS Gen2 to be accessed by the Fabric pipeline using **Workspace Identity** + a **resource instance rule**. This is the preferred path (no gateway required) and is supported for `Microsoft.Storage.BlobCreated` events.

**Prerequisite:** [Workshop 02](../02-eventhouse-kql-tables/) complete
**Next:** [Workshop 04 — Data Pipeline](../04-data-pipeline/)

---

## 3.1 Create / verify Workspace Identity

Fabric workspace → **Workspace settings** → **Workspace identity** → **+ Add**.

Record the identity's **Object (principal) ID** (used below).

## 3.2 Grant RBAC on the storage account

Assign **Storage Blob Data Contributor** to the workspace identity at the storage-account scope:

- [scripts/03-grant-rbac.ps1](scripts/03-grant-rbac.ps1)

```powershell
$wsIdentityObjId = "<WORKSPACE-IDENTITY-OBJECT-ID>"
$saId = (az storage account show -n $sa -g $rg --query id -o tsv)

az role assignment create `
    --assignee-object-id $wsIdentityObjId `
    --assignee-principal-type ServicePrincipal `
    --role "Storage Blob Data Contributor" `
    --scope $saId
```

## 3.3 Add the resource instance rule

> Portal UI does **not** support this for Fabric — use ARM or PowerShell.

- [scripts/03-add-resource-instance-rule.ps1](scripts/03-add-resource-instance-rule.ps1)

```powershell
$tenantId    = "<TENANT-ID>"
$workspaceId = "<FABRIC-WORKSPACE-GUID>"
$resourceId  = "/subscriptions/00000000-0000-0000-0000-000000000000/resourcegroups/Fabric/providers/Microsoft.Fabric/workspaces/$workspaceId"

Add-AzStorageAccountNetworkRule `
    -ResourceGroupName $rg -Name $sa `
    -TenantId $tenantId -ResourceId $resourceId
```

## 3.4 Verify

```powershell
(Get-AzStorageAccount -ResourceGroupName $rg -Name $sa).NetworkRuleSet.ResourceAccessRules
```

Expected: an entry with `ResourceId` pointing to your Fabric workspace.

## ✅ Exit Criteria

- [ ] Workspace identity created and object ID recorded
- [ ] RBAC `Storage Blob Data Contributor` granted to workspace identity
- [ ] Resource instance rule visible on the storage account
- [ ] Test from Workshop 04 (connection Test) succeeds

→ Proceed to **[Workshop 04 — Data Pipeline](../04-data-pipeline/)**
