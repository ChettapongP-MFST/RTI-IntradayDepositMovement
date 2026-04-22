# Create firewall-enabled ADLS Gen2 (Workshop 01)
# Usage:
#   ./01-create-storage.ps1 -Subscription <subId> -ResourceGroup <rg> -Location <region> -StorageAccount <saName>
[CmdletBinding()]
param(
  [Parameter(Mandatory)] [string] $Subscription,
  [Parameter(Mandatory)] [string] $ResourceGroup,
  [Parameter(Mandatory)] [string] $Location,
  [Parameter(Mandatory)] [string] $StorageAccount,
  [string] $Container = "intraday-deposits",
  [switch] $AllowMyIp
)

az account set --subscription $Subscription | Out-Null

Write-Host "Ensuring resource group '$ResourceGroup' in $Location..."
az group create -n $ResourceGroup -l $Location | Out-Null

Write-Host "Creating ADLS Gen2 storage account '$StorageAccount' (firewall Deny, AzureServices bypass)..."
az storage account create `
    --name $StorageAccount --resource-group $ResourceGroup --location $Location `
    --sku Standard_LRS --kind StorageV2 --hns true `
    --allow-blob-public-access false `
    --default-action Deny `
    --bypass AzureServices `
    --min-tls-version TLS1_2 | Out-Null

Write-Host "Creating container '$Container'..."
$key = (az storage account keys list -n $StorageAccount -g $ResourceGroup --query "[0].value" -o tsv)
az storage container create --name $Container --account-name $StorageAccount --account-key $key | Out-Null

if ($AllowMyIp) {
    $myIp = (Invoke-RestMethod https://api.ipify.org)
    Write-Host "Allowing your IP '$myIp' on the storage firewall..."
    az storage account network-rule add -g $ResourceGroup -n $StorageAccount --ip-address $myIp | Out-Null
}

Write-Host "Done. Storage account: $StorageAccount  |  Container: $Container" -ForegroundColor Green
