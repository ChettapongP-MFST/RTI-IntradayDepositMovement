# Workshop 00 — Prerequisites

Before starting any deployment, verify Azure and Fabric readiness and collect the information each later workshop will reference.

**Estimated time:** 20–30 minutes
**Next:** [Workshop 01 — Provision ADLS Gen2](../01-provision-adls-gen2/)

---

> This workshop series is designed for **analyst end-users**. Every step runs in a **browser** — Azure Portal, Fabric Portal, Power BI — with no command-line tools required.

## 0.1 Azure prerequisites

| # | Item | How to verify (Portal) |
|---|---|---|
| 1 | Azure subscription with **Contributor** on target resource group | [portal.azure.com](https://portal.azure.com) → Resource group → **Access control (IAM)** → **View my access** |
| 2 | Permission to create **Storage accounts** | Same IAM view — role must be Contributor / Owner / Storage Account Contributor |
| 3 | Permission to assign **Storage Blob Data Contributor** RBAC | IAM → **Check access** → role must be **User Access Administrator** or **Owner** |
| 4 | Ability to deploy an ARM template via portal **Custom deployment** | Portal → search `deploy a custom template` (used once in Workshop 03) |

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

## ✅ Exit Criteria

- [ ] All rows in **0.1** and **0.2** checked in the portal
- [ ] All values in **0.3** filled
- [ ] Azure Portal and Fabric Portal both open in your browser with the correct tenant selected

→ Proceed to **[Workshop 01 — Provision ADLS Gen2](../01-provision-adls-gen2/)**
