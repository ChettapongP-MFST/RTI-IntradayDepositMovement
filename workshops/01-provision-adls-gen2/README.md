# Workshop 01 — Provision ADLS Gen2

Create the firewall-enabled ADLS Gen2 storage account and container that will receive the 10-minute CSV drops.

**Prerequisite:** [Workshop 00](../00-prerequisites/) complete
**Next:** [Workshop 02 — Eventhouse & KQL Tables](../02-eventhouse-kql-tables/)

---

## 1.1 Variables

Fill these in from Workshop 00.3:

```powershell
$sub = "<SUBSCRIPTION-ID>"
$rg  = "<RG-NAME>"
$loc = "<REGION>"                  # e.g. southeastasia
$sa  = "<STORAGE-ACCOUNT-NAME>"    # globally unique, lowercase
$ctr = "intraday-deposits"
```

## 1.2 Create the storage account

Run the script:

- [scripts/01-create-storage.ps1](scripts/01-create-storage.ps1)

Or directly:

```powershell
az account set --subscription $sub
az group create -n $rg -l $loc

# StorageV2 + HNS (ADLS Gen2) + firewall default Deny
az storage account create `
    --name $sa --resource-group $rg --location $loc `
    --sku Standard_LRS --kind StorageV2 --hns true `
    --allow-blob-public-access false `
    --default-action Deny `
    --bypass AzureServices `
    --min-tls-version TLS1_2
```

## 1.3 Create the container

```powershell
$key = (az storage account keys list -n $sa -g $rg --query "[0].value" -o tsv)
az storage container create --name $ctr --account-name $sa --account-key $key
```

Sub-folders (`incoming/`, `archive/`) are created implicitly on first write in HNS.

## 1.4 Allow your IP temporarily (for Workshop 06 uploads)

```powershell
$myIp = (Invoke-RestMethod https://api.ipify.org)
az storage account network-rule add -g $rg -n $sa --ip-address $myIp
```

> Remove this rule after Workshop 06:
> `az storage account network-rule remove -g $rg -n $sa --ip-address $myIp`

## 1.5 Event Grid

Blob events are emitted for free by StorageV2 + HNS accounts. No extra configuration needed — Fabric subscribes in Workshop 05.

## ✅ Exit Criteria

- [ ] Storage account created with HNS enabled
- [ ] Public network: **Deny** with **AzureServices bypass**
- [ ] Container `intraday-deposits` exists
- [ ] Your IP is temporarily allow-listed

→ Proceed to **[Workshop 02 — Eventhouse & KQL Tables](../02-eventhouse-kql-tables/)**
