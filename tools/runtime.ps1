function Get-LiurenPython {
    $env:PYTHONUTF8 = '1'
    $env:PYTHONIOENCODING = 'utf-8'
    $liurenPython = $env:LIUREN_PYTHON
    if (-not $liurenPython) {
        $registry = Join-Path $env:USERPROFILE '.conda\environments.txt'
        if (Test-Path -LiteralPath $registry) {
            foreach ($candidate in Get-Content -LiteralPath $registry) {
                if ($candidate -match '[\\/]六壬[\\/].*[\\/]ai-env$') {
                    $liurenPython = Join-Path $candidate 'python.exe'
                    break
                }
            }
        }
    }
    if (-not $liurenPython -or -not (Test-Path -LiteralPath $liurenPython)) {
        throw '找不到六壬 ai-env。请设置 LIUREN_PYTHON 为专属环境的 python.exe。'
    }
    return $liurenPython
}
