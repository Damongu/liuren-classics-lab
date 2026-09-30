param([switch]$Model)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'tools\runtime.ps1')
$liurenPython = Get-LiurenPython
$acceptanceArgs = @((Join-Path $PSScriptRoot 'tools\acceptance.py'))
if ($Model) { $acceptanceArgs += '--model' }
& $liurenPython @acceptanceArgs
exit $LASTEXITCODE
