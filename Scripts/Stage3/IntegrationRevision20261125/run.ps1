param([Parameter(Mandatory=$true)][string]$Script,
      [Parameter(Mandatory=$true)][string]$Name,
      [ValidateSet('d3d11','d3d12')][string]$Renderer='d3d12',
      [switch]$NullRHI)
$ErrorActionPreference='Stop'
$stage3Project=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..\..')).Path
$stage3Output=Join-Path $stage3Project 'Saved\Stage3IntegrationRevision20261125\Runs'
$stage3User=Join-Path $stage3Output ($Name+'User')
New-Item -ItemType Directory -Force -Path $stage3User | Out-Null
$stage3Args=@(
 ('"{0}\Catrun.uproject"' -f $stage3Project),'/Game/Maps/Stage3','-RenderOffscreen',('-'+$Renderer),'-windowed','-ResX=1280','-ResY=720',
 '-NoSplash','-NoSound','-unattended','-nop4','-NoSaveConfig','-SaveToUserDir','-Multiprocess',('-UserDir="{0}"' -f $stage3User),
 '-ini:EditorSettings:[/Script/UnrealEd.EditorPerformanceSettings]:bThrottleCPUWhenNotForeground=False',
 ('-ExecCmds="Slate.bAllowThrottling 0,t.IdleWhenNotForeground 0,py {0}/Scripts/Stage3/{1}"' -f $stage3Project.Replace('\','/'),$Script),
 ('-abslog="{0}\{1}.log"' -f $stage3Output,$Name)
)
if ($NullRHI) {$stage3Args+='-nullrhi';$stage3Args+='-onethread'}
$stage3Process=Start-Process -FilePath 'C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe' -ArgumentList $stage3Args -WorkingDirectory $stage3Project -WindowStyle Hidden -PassThru
@{pid=$stage3Process.Id;log=(Join-Path $stage3Output ($Name+'.log'))} | ConvertTo-Json -Compress
