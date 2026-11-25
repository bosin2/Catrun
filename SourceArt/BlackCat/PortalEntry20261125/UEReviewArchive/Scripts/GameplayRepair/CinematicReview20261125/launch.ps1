param([string]$Label = 'Before', [switch]$FullRegression)
$ErrorActionPreference = 'Stop'
$projectRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..\..')).Path
$runRoot = Join-Path $projectRoot 'Saved\CinematicReview20261125'
$stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
$userRoot = Join-Path $runRoot ($Label + '-' + $stamp + '-User')
$logPath = Join-Path $runRoot ($Label + '-' + $stamp + '.log')
$script = (Join-Path $PSScriptRoot 'capture.py').Replace('\', '/')
$arguments = @(
    ('"' + $projectRoot + '\Catrun.uproject"'), '/Game/Maps/Stage1',
    '-RenderOffscreen', '-d3d11', '-onethread', '-windowed', '-ResX=1920', '-ResY=1080',
    '-NoSplash', '-NoSound', '-unattended', '-nop4', '-NoSaveConfig', '-SaveToUserDir', '-Multiprocess',
    ('-UserDir="' + $userRoot + '"'), '-UseFixedTimeStep', '-FPS=30',
    '-ini:Engine:[/Script/PythonScriptPlugin.PythonScriptPluginSettings]:bRemoteExecution=False',
    '-ini:EditorSettings:[/Script/UnrealEd.EditorPerformanceSettings]:bThrottleCPUWhenNotForeground=False',
    ('-ExecCmds="Slate.bAllowThrottling 0,t.IdleWhenNotForeground 0,py ' + $script + '"'),
    ('-abslog="' + $logPath + '"')
)
if ($FullRegression) { $arguments += '-CinematicFullRegression' }
$process = Start-Process -FilePath 'C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe' -ArgumentList $arguments -WindowStyle Hidden -PassThru
[pscustomobject]@{ pid = $process.Id; label = $Label; log = $logPath; user = $userRoot; project = $projectRoot } |
    ConvertTo-Json | Tee-Object -FilePath (Join-Path $runRoot 'process.json')
