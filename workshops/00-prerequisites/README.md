# Workshop 00 — Prerequisites

Before starting any deployment, verify Azure and Fabric readiness and collect the information each later workshop will reference.

**Estimated time:** 20–30 minutes
**Next:** [Workshop 01 — Provision ADLS Gen2](../01-provision-adls-gen2/)

---

## 0.1 Azure prerequisites

| # | Item | How to verify |
|---|---|---|
| 1 | Azure subscription with **Contributor** on target resource group | `az account show` / portal → RG → Access control (IAM) |
| 2 | Permission to create **Microsoft.Storage/storageAccounts** | RG role Contributor (or Storage Account Contributor) |
| 3 | Permission to assign **Storage Blob Data Contributor** RBAC | **User Access Administrator** or **Owner** on the storage scope |
| 4 | Ability to run ARM template / PowerShell | Portal UI cannot create Fabric resource instance rules |
| 5 | Azure CLI ≥ 2.60 and Az PowerShell ≥ 11 installed | `az --version`, `Get-Module Az -ListAvailable` |

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

## 0.4 Authenticate

```powershell
az login
az account set --subscription "<SUBSCRIPTION-ID>"

Connect-AzAccount -Tenant "<TENANT-ID>"
Set-AzContext -Subscription "<SUBSCRIPTION-ID>"
```

## ✅ Exit Criteria

- [ ] All rows in **0.1** and **0.2** checked
- [ ] All values in **0.3** filled
- [ ] Both `az login` and `Connect-AzAccount` work against the target tenant/subscription

→ Proceed to **[Workshop 01 — Provision ADLS Gen2](../01-provision-adls-gen2/)**
