$ErrorActionPreference = 'Stop'
$projectDir = $PSScriptRoot
$pythonExe = Join-Path $projectDir '.conda\python.exe'
$condaCmd = Get-Command conda -ErrorAction SilentlyContinue
if (-not (Test-Path -LiteralPath $pythonExe)) {
    if (-not $condaCmd) {
        throw 'Conda not found. Run setup.ps1 from Anaconda/Miniconda PowerShell Prompt.'
    }
    $baseDir = (& conda info --base | Select-Object -Last 1).Trim()
    $condaPython = Join-Path $baseDir 'python.exe'
    $env:CONDA_NO_PLUGINS = 'true'
    & $condaPython -m conda create --prefix (Join-Path $projectDir '.conda') python=3.11 pip --solver classic -y
    if ($LASTEXITCODE -ne 0) { throw 'Conda environment creation failed.' }
}
& $pythonExe -m pip install -r (Join-Path $projectDir 'requirements.txt')
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
Write-Host 'Ready. Double-click start.cmd.'
