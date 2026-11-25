param([ValidateSet('Author','Native')][string]$Mode='Author',[string]$Name='ArrivalRevision2')
$ErrorActionPreference='Stop'
$elevatorRoot=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$elevatorOut=Join-Path $elevatorRoot ('Saved\ElevatorTransition\'+$Name)
New-Item -ItemType Directory -Force -Path $elevatorOut | Out-Null
$elevatorArgs=@(('"{0}\Catrun.uproject"' -f $elevatorRoot),'-unattended','-nop4','-nullrhi','-nosplash','-nosound','-onethread','-NoAsyncLoadingThread','-NoSaveConfig','-NoCrashDialog',
 '-Multiprocess', '-SaveToUserDir', ('-UserDir="{0}\User"' -f $elevatorOut), ('-abslog="{0}\run.log"' -f $elevatorOut),
 '-dpcvars=Editor.AsyncStaticMeshCompilation=0,Editor.AsyncSkinnedAssetCompilation=0,p.EnableDeferredPhysicsCreation=0,p.Chaos.EnableAsyncInitBody=0',
 '-ini:Engine:[DevOptions.Shaders]:NumUnusedShaderCompilingThreads=14','-ini:Engine:[DevOptions.Shaders]:ShaderCompilerCoreCountThreshold=999')
# Multiprocess skips repeated SDK discovery (already validated by the successful build),
# avoiding the global UBT mutex held by unrelated project builds.
if($Mode -eq 'Author'){$elevatorArgs+=@('-run=pythonscript',('-script="{0}\Scripts\ElevatorTransition\author_revision2.py"' -f $elevatorRoot))}
else{$elevatorArgs+=@('-ExecCmds="Automation RunTests Catrun.LevelFlow.ElevatorWeight+Catrun.LevelFlow.Stage3ElevatorArrivalTitleGate+Catrun.LevelFlow.Stage2ArrivalTitleGate"','-TestExit="Automation Test Queue Empty"',('-ReportExportPath="{0}\Report"' -f $elevatorOut))}
$elevatorProc=Start-Process -FilePath 'C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe' -ArgumentList $elevatorArgs -WorkingDirectory $elevatorRoot -WindowStyle Hidden -PassThru
@{pid=$elevatorProc.Id;log=(Join-Path $elevatorOut 'run.log')} | ConvertTo-Json -Compress
