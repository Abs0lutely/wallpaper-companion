param([string]$Destination = (Join-Path $PSScriptRoot '..\build\tools\inno'))
$ErrorActionPreference = 'Stop'
$toolRoot = Split-Path ([IO.Path]::GetFullPath($Destination)) -Parent
New-Item -ItemType Directory -Force -Path $toolRoot | Out-Null
$installer = Join-Path $toolRoot 'innosetup-6.7.4.exe'
$url = 'https://github.com/jrsoftware/issrc/releases/download/is-6_7_4/innosetup-6.7.4.exe'
if (-not (Test-Path -LiteralPath $installer)) { Invoke-WebRequest -Uri $url -OutFile $installer }
$expected = 'A549929319F9120716677C685535CA4671E4B937B5FDC87E2585F32D8EB30E8C'
if ((Get-FileHash -LiteralPath $installer -Algorithm SHA256).Hash -ne $expected) { throw 'Inno Setup SHA256 mismatch' }
$toolProcess = Start-Process -FilePath $installer -ArgumentList @('/VERYSILENT','/SUPPRESSMSGBOXES','/NORESTART','/SP-','/PORTABLE=1','/NOICONS','/TASKS=',('/DIR="' + [IO.Path]::GetFullPath($Destination) + '"')) -WindowStyle Hidden -Wait -PassThru
if ($toolProcess.ExitCode -ne 0) { throw "Inno Setup extraction failed: $($toolProcess.ExitCode)" }
Write-Host "Compiler ready: $(Join-Path $Destination 'ISCC.exe')"
