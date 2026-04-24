# Add a Fabric workspace resource instance rule to the storage account (Workshop 00, section 0.7)
# Requires: Az PowerShell signed in (Connect-AzAccount)
[CmdletBinding()]
param(
  [Parameter(Mandatory)] [string] $ResourceGroup,
  [Parameter(Mandatory)] [string] $StorageAccount,
  [Parameter(Mandatory)] [string] $TenantId,
  [Parameter(Mandatory)] [string] $FabricWorkspaceGuid
)

$resourceId = "/subscriptions/00000000-0000-0000-0000-000000000000/resourcegroups/Fabric/providers/Microsoft.Fabric/workspaces/$FabricWorkspaceGuid"

Add-AzStorageAccountNetworkRule `
    -ResourceGroupName $ResourceGroup `
    -Name $StorageAccount `
    -TenantId $TenantId `
    -ResourceId $resourceId

Write-Host "Resource instance rule added. Verifying..." -ForegroundColor Cyan
(Get-AzStorageAccount -ResourceGroupName $ResourceGroup -Name $StorageAccount).NetworkRuleSet.ResourceAccessRules |
    Format-Table TenantId, ResourceId
