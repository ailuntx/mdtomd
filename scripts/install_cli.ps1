$ErrorActionPreference = 'Stop'

$rootDir = Split-Path -Parent $PSScriptRoot
$pythonBin = if ($env:PYTHON_BIN) { $env:PYTHON_BIN } elseif (Get-Command py -ErrorAction SilentlyContinue) { 'py' } else { 'python' }

function Get-UserScriptsDir {
    $script = 'import sysconfig; print(sysconfig.get_path("scripts", f"{os.name}_user"))'
    try {
        if ($pythonBin -eq 'py') {
            return (& py -c "import os, sysconfig; print(sysconfig.get_path('scripts', f'{os.name}_user'))").Trim()
        }
        return (& $pythonBin -c "import os, sysconfig; print(sysconfig.get_path('scripts', f'{os.name}_user'))").Trim()
    } catch {
        return ''
    }
}

if ($env:VIRTUAL_ENV) {
    if ($pythonBin -eq 'py') {
        & py -m pip install -e $rootDir
    } else {
        & $pythonBin -m pip install -e $rootDir
    }
} else {
    if ($pythonBin -eq 'py') {
        & py -m pip install --user -e $rootDir
    } else {
        & $pythonBin -m pip install --user -e $rootDir
    }
}

$existing = Get-Command mdtomd -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "mdtomd 已可直接使用: $($existing.Source)"
    exit 0
}

$scriptsDir = Get-UserScriptsDir
if (-not $scriptsDir) {
    Write-Error '无法解析 Python 用户脚本目录。'
}

$scriptPath = Join-Path $scriptsDir 'mdtomd.exe'
if (-not (Test-Path $scriptPath)) {
    Write-Error "未找到安装后的 mdtomd: $scriptPath"
}

$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
$pathItems = @()
if ($userPath) {
    $pathItems = $userPath.Split(';') | Where-Object { $_ }
}

if ($pathItems -contains $scriptsDir) {
    Write-Host "用户 PATH 已包含: $scriptsDir"
    Write-Host '现在可直接使用: mdtomd'
    exit 0
}

$newUserPath = if ($userPath) { "$scriptsDir;$userPath" } else { $scriptsDir }
[Environment]::SetEnvironmentVariable('Path', $newUserPath, 'User')

Write-Host "已写入用户 PATH: $scriptsDir"
Write-Host '请重新打开终端或 VS Code 后再使用 mdtomd'
