# Grant Storage Blob Data Contributor to the Fabric workspace identity (Workshop 00, section 0.6)
[CmdletBinding()]
param(
  [Parameter(Mandatory)] [string] $ResourceGroup,
  [Parameter(Mandatory)] [string] $StorageAccount,
  [Parameter(Mandatory)] [string] $WorkspaceIdentityObjectId
)

$saId = (az storage account show -n $StorageAccount -g $ResourceGroup --query id -o tsv)

az role assignment create `
    --assignee-object-id $WorkspaceIdentityObjectId `
    --assignee-principal-type ServicePrincipal `
    --role "Storage Blob Data Contributor" `
    --scope $saId

Write-Host "Granted Storage Blob Data Contributor on $StorageAccount to identity $WorkspaceIdentityObjectId" -ForegroundColor Green
