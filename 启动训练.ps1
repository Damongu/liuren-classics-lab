param([ValidateRange(1024,65535)][int]$Port = 8765)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'tools\runtime.ps1')
$liurenPython = Get-LiurenPython
& $liurenPython (Join-Path $PSScriptRoot 'liuren-paipan\webapp.py') --host 127.0.0.1 --port $Port
exit $LASTEXITCODE
