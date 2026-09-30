param([ValidateSet('凝神子','略决','太白','心镜','景祐','武经','邵彦和','阿甲','林景行','壬归','卜筮残','大全查手','导读官','排盘守卫','复盘官')][string]$Book = '凝神子', [switch]$DryRun)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot 'tools\runtime.ps1')
$liurenPython = Get-LiurenPython
$launchArgs = @((Join-Path $PSScriptRoot 'tools\launch_book.py'), '--book', $Book)
if ($DryRun) { $launchArgs += '--dry-run' }
& $liurenPython @launchArgs
exit $LASTEXITCODE
