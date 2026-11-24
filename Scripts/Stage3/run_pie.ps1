param([string]$Script='verify_pie.py',[string]$Name='PIE',[switch]$NullRHI,[switch]$SingleThread,[ValidateSet('d3d11','d3d12')][string]$Renderer='d3d11')
$ErrorActionPreference='Stop'
$stage3Root=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$stage3Out=Join-Path $stage3Root 'Saved\Stage3Integration20261125'
$stage3User=Join-Path $stage3Out ($Name+'User')
New-Item -ItemType Directory -Force -Path $stage3User | Out-Null
$stage3Arguments=@(
    ('"{0}\Catrun.uproject"' -f $stage3Root),'-RenderOffscreen',('-'+$Renderer),'-windowed','-ResX=1280','-ResY=720',
    '-NoSplash','-NoSound','-unattended','-nop4','-NoSaveConfig','-SaveToUserDir',('-UserDir="{0}"' -f $stage3User),
    '-ini:EditorSettings:[/Script/UnrealEd.EditorPerformanceSettings]:bThrottleCPUWhenNotForeground=False',
    ('-ExecCmds="Slate.bAllowThrottling 0,t.IdleWhenNotForeground 0,py {0}/Scripts/Stage3/{1}"' -f $stage3Root.Replace('\','/'),$Script),
    ('-abslog="{0}\{1}.log"' -f $stage3Out,$Name)
)
if ($NullRHI) {$stage3Arguments+='-nullrhi'}
if ($SingleThread) {$stage3Arguments+='-onethread'}
$stage3Process=Start-Process -FilePath 'C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe' -ArgumentList $stage3Arguments -WorkingDirectory $stage3Root -WindowStyle Hidden -PassThru
@{pid=$stage3Process.Id;log=(Join-Path $stage3Out ($Name+'.log'))} | ConvertTo-Json -Compress
