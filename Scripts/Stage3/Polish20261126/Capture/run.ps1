param([string]$Name='Run01')
$ErrorActionPreference='Stop'
$proj=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..\..')).Path
$out=Join-Path $proj 'Saved\Stage3Polish20261126\Captures\Runs'
$user=Join-Path $out ($Name+'User')
New-Item -ItemType Directory -Force -Path $user | Out-Null
$env:S3P_CAPTURE_PASS=$Name
$a=@(
 ('"{0}\Catrun.uproject"' -f $proj),'/Game/Maps/Stage3','-RenderOffscreen','-d3d12','-windowed','-ResX=1280','-ResY=720',
 '-NoSplash','-NoSound','-unattended','-nop4','-NoSaveConfig','-NoCrashDialog','-SaveToUserDir','-Multiprocess',('-UserDir="{0}"' -f $user),
 '-ini:EditorSettings:[/Script/UnrealEd.EditorPerformanceSettings]:bThrottleCPUWhenNotForeground=False',
 ('-ExecCmds="Slate.bAllowThrottling 0,t.IdleWhenNotForeground 0,py {0}/Scripts/Stage3/Polish20261126/Capture/capture_polish.py"' -f $proj.Replace('\','/')),
 ('-abslog="{0}\{1}.log"' -f $out,$Name)
)
$p=Start-Process -FilePath 'C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe' -ArgumentList $a -WorkingDirectory $proj -WindowStyle Hidden -PassThru
@{pid=$p.Id;log=(Join-Path $out ($Name+'.log'))} | ConvertTo-Json -Compress
