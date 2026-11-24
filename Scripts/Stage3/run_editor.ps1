param([Parameter(Mandatory=$true)][string]$Script,[string]$Name='Stage3',[switch]$Render)
$ErrorActionPreference='Stop'
$stage3Root=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$stage3Script=(Resolve-Path -LiteralPath $Script).Path
$stage3Out=Join-Path $stage3Root 'Saved\Stage3Integration20261125'
New-Item -ItemType Directory -Force -Path $stage3Out | Out-Null
$stage3Arguments=@(
    ('"{0}\Catrun.uproject"' -f $stage3Root), '-run=pythonscript', ('-script="{0}"' -f $stage3Script),
    '-unattended','-nop4','-nosplash','-nosound','-onethread','-NoAsyncLoadingThread','-NoSaveConfig','-NoCrashDialog',
    '-dpcvars=Editor.AsyncStaticMeshCompilation=0,Editor.AsyncSkinnedAssetCompilation=0,p.EnableDeferredPhysicsCreation=0,p.Chaos.EnableAsyncInitBody=0',
    ('-abslog="{0}\{1}.log"' -f $stage3Out,$Name),'-ini:Engine:[DevOptions.Shaders]:NumUnusedShaderCompilingThreads=14',
    '-ini:Engine:[DevOptions.Shaders]:NumUnusedShaderCompilingThreadsDuringGame=14','-ini:Engine:[DevOptions.Shaders]:ShaderCompilerCoreCountThreshold=999'
)
if (-not $Render) {$stage3Arguments+='-nullrhi'}
else {$stage3Arguments+=@('-AllowCommandletRendering','-RenderOffscreen','-d3d11')}
$stage3Process=Start-Process -FilePath 'C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe' -ArgumentList $stage3Arguments -WorkingDirectory $stage3Root -WindowStyle Hidden -PassThru
@{pid=$stage3Process.Id;log=(Join-Path $stage3Out "$Name.log");script=$stage3Script} | ConvertTo-Json -Compress
