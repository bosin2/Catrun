param([string]$Name='Runtime01',[string]$Script='verify_runtime.py',[string]$ProjectRoot='', [ValidateSet('d3d11','d3d12')][string]$RHI='d3d11')
$ErrorActionPreference='Stop'
$elevatorRoot=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
if ($ProjectRoot) { $elevatorRoot=(Resolve-Path -LiteralPath $ProjectRoot).Path }
$elevatorOut=Join-Path $elevatorRoot 'Saved\ElevatorTransition'
$elevatorArgs=@(
 ('"{0}\Catrun.uproject"' -f $elevatorRoot),'/Game/Maps/Stage2',
 ('-ExecCmds="Slate.bAllowThrottling 0,t.IdleWhenNotForeground 0,py {0}/Scripts/ElevatorTransition/{1}"' -f $elevatorRoot.Replace('\','/'),$Script),
 '-Multiprocess','-RenderOffscreen',('-'+$RHI),'-unattended','-nop4','-NoSaveConfig','-NoCrashDialog','-nosplash',
 '-onethread','-NoAsyncLoadingThread','-SaveToUserDir',
 ('-UserDir="{0}\IsolatedUser\{1}"' -f $elevatorOut,$Name),
 ('-abslog="{0}\{1}.log"' -f $elevatorOut,$Name),
 '-ResX=1280','-ResY=720','-windowed',
 '-dpcvars=Editor.AsyncStaticMeshCompilation=0,Editor.AsyncSkinnedAssetCompilation=0,p.EnableDeferredPhysicsCreation=0,p.Chaos.EnableAsyncInitBody=0',
 '-ini:EditorSettings:[/Script/UnrealEd.EditorPerformanceSettings]:bThrottleCPUWhenNotForeground=False',
 '-ini:Engine:[/Script/PythonScriptPlugin.PythonScriptPluginSettings]:bRemoteExecution=True',
 '-ini:Engine:[/Script/PythonScriptPlugin.PythonScriptPluginSettings]:RemoteExecutionMulticastGroupEndpoint=239.0.0.1:6777',
 '-ini:Engine:[/Script/PythonScriptPlugin.PythonScriptPluginSettings]:RemoteExecutionMulticastBindAddress=127.0.0.1',
 '-ini:Engine:[DevOptions.Shaders]:NumUnusedShaderCompilingThreads=14',
 '-ini:Engine:[DevOptions.Shaders]:ShaderCompilerCoreCountThreshold=999'
)
$elevatorProc=Start-Process -FilePath 'C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe' -ArgumentList $elevatorArgs -WorkingDirectory $elevatorRoot -WindowStyle Hidden -PassThru
@{pid=$elevatorProc.Id;log=(Join-Path $elevatorOut "$Name.log")} | ConvertTo-Json -Compress
