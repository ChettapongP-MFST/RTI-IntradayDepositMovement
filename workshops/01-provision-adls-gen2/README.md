# Workshop 01 — Provision ADLS Gen2 (Azure Portal)

Create the firewall-enabled ADLS Gen2 storage account and container that will receive the 10-minute CSV drops — **entirely from the Azure Portal**.

**Prerequisite:** [Workshop 00](../00-prerequisites/) complete
**Next:** [Workshop 02 — Eventhouse & KQL Tables](../02-eventhouse-kql-tables/)

---

## 1.1 Create the resource group (if new)

1. [portal.azure.com](https://portal.azure.com) → top search bar → type **Resource groups** → **+ Create**.
2. Subscription, Name, Region → **Review + create** → **Create**.

## 1.2 Create the storage account

1. Top search bar → **Storage accounts** → **+ Create**.
2. **Basics** tab:
   - Subscription, Resource group (from 1.1)
   - **Storage account name** — 3–24 chars lowercase, globally unique
   - Region — same as resource group
   - Performance — **Standard**
   - Redundancy — **LRS** (or ZRS for prod)
3. **Advanced** tab:
   - **Enable hierarchical namespace** ✅ *(this makes it ADLS Gen2 — required)*
   - Minimum TLS version — **1.2**
   - Allow enabling anonymous access on individual containers — **unchecked**
4. **Networking** tab:
   - Public network access — **Enabled from selected virtual networks and IP addresses**
   - Under **Exceptions** → check ✅ **Allow Azure services on the trusted services list to access this storage account**
   - Under **Firewall** → check ✅ **Add your client IP address (xx.xx.xx.xx)** *(temporary — used by Workshop 06 uploads; remove in Workshop 09)*
5. **Data protection / Encryption** — leave defaults.
6. **Review + create** → **Create**. Wait for deployment (~1 min).

## 1.3 Create the container

1. Open the storage account → left menu → **Data storage** → **Containers**.
2. **+ Container** → Name: `intraday-deposits` → **Create**.
3. Sub-folders `incoming/` and `archive/` are created automatically on first file upload in HNS accounts — no manual step needed.

## 1.4 Verify network settings

1. Left menu → **Security + networking** → **Networking** → **Firewalls and virtual networks** tab.
2. Confirm:
   - Public network access = **Enabled from selected virtual networks and IP addresses**
   - Your public IP is listed under **Firewall**
   - **Allow Azure services on the trusted services list…** is checked ✅

> Workshop 00 (section 0.7) adds a **resource instance rule** so the Fabric workspace identity bypasses this firewall without opening it up publicly.

## 1.5 Event Grid

Blob events are emitted automatically by StorageV2 + HNS accounts — no extra configuration. Fabric subscribes in Workshop 05.

## ✅ Exit Criteria

- [ ] Storage account visible in Azure Portal, **Hierarchical namespace** column shows `Enabled`
- [ ] **Networking** → Public access restricted to selected IPs, AzureServices bypass ✅
- [ ] Container `intraday-deposits` visible in **Containers** blade
- [ ] Your public IP is temporarily allow-listed

→ Proceed to **[Workshop 02 — Eventhouse & KQL Tables](../02-eventhouse-kql-tables/)**

> ℹ️ The `scripts/01-create-storage.ps1` file is retained for automation engineers who prefer CLI — analysts should use the portal steps above.
