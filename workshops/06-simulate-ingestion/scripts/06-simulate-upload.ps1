# Simulate real-time CSV drops to ADLS Gen2 (Workshop 06)
# Supports real 10-minute cadence and accelerated modes.
[CmdletBinding()]
param(
  [Parameter(Mandatory)] [string] $StorageAccount,
  [Parameter(Mandatory)] [string] $ResourceGroup,
  [string] $Container       = "intraday-deposits",
  [string] $Prefix          = "incoming/",
  [string] $DatasetPath     = "./resources/datasets",
  [int]    $IntervalSeconds = 600,     # default = real 10 min cadence
  [switch] $Accelerated                # overrides interval → 30 s
)

if ($Accelerated) { $IntervalSeconds = 30 }

$key = (az storage account keys list -n $StorageAccount -g $ResourceGroup --query "[0].value" -o tsv)
if (-not $key) { throw "Unable to retrieve storage account key. Check permissions / az login." }

$files = Get-ChildItem -Path $DatasetPath -Filter "mock_*.csv" | Sort-Object Name
if ($files.Count -eq 0) { throw "No mock_*.csv files found under $DatasetPath" }

Write-Host "Replaying $($files.Count) files into $StorageAccount/$Container/$Prefix with interval = $IntervalSeconds s" -ForegroundColor Cyan

$i = 0
foreach ($f in $files) {
    $i++
    $blobName = "$Prefix$($f.Name)"
    Write-Host "[$i/$($files.Count)] $(Get-Date -Format HH:mm:ss)  Uploading $($f.Name) -> $blobName"
    az storage blob upload `
        --account-name $StorageAccount --account-key $key `
        --container-name $Container `
        --name $blobName `
        --file $f.FullName `
        --overwrite true | Out-Null

    if ($i -lt $files.Count) {
        Write-Host "    waiting $IntervalSeconds s before next drop..." -ForegroundColor DarkGray
        Start-Sleep -Seconds $IntervalSeconds
    }
}

Write-Host "Replay complete." -ForegroundColor Green
