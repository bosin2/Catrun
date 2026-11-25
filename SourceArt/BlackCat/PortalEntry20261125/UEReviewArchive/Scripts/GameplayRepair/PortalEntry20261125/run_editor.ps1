param([string]$Script = 'preflight.py', [string]$Label = 'Preflight')
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$outputRoot = Join-Path $projectRoot 'Saved\PortalEntry20261125'
[IO.Directory]::CreateDirectory($outputRoot) | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$logPath = Join-Path $outputRoot ($Label + '-' + $stamp + '.log')
$pythonPath = (Join-Path $PSScriptRoot $Script).Replace('\', '/')
if (-not (Test-Path -LiteralPath $pythonPath -PathType Leaf)) { throw 'Missing authoring script' }
$arguments = @(
    ('"' + $projectRoot + '\Catrun.uproject"'), '-run=pythonscript',
    ('-script="' + $pythonPath + '"'), '-nullrhi', '-unattended', '-NoSound', '-NoSplash',
    '-NoSaveConfig', '-nop4', '-Multiprocess',
    '-ini:Engine:[/Script/PythonScriptPlugin.PythonScriptPluginSettings]:bRemoteExecution=False',
    ('-abslog="' + $logPath + '"')
)
$process = Start-Process -FilePath 'C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe' -ArgumentList $arguments -WindowStyle Hidden -PassThru
[pscustomobject]@{ pid = $process.Id; label = $Label; log = $logPath; project = $projectRoot } |
    ConvertTo-Json | Tee-Object -FilePath (Join-Path $outputRoot 'process.json')
