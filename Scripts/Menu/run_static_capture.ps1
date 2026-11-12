param([Parameter(Mandatory=$true)][string]$Run,[string]$Maps='Tutorial,Stage1,Stage2,SoundTest_Tutorial,SoundTest_Stage1,SoundTest_Stage2')
$ErrorActionPreference='Stop'
$taskRoot='C:/Users/whghk/Catrun'
$taskOutput=Join-Path $taskRoot ('Saved/ChaptersFlow20261112/'+$Run)
if(Test-Path -LiteralPath $taskOutput){throw 'Use a unique run name.'}
$taskEditors=Get-CimInstance Win32_Process -Filter "Name='UnrealEditor.exe' OR Name='UnrealEditor-Cmd.exe'" | Where-Object {$_.CommandLine -like '*Catrun*'}
if($taskEditors){throw 'An existing Catrun editor owns the project.'}
$taskBuilders=Get-CimInstance Win32_Process -Filter "Name='dotnet.exe'" | Where-Object {$_.CommandLine -like '*UnrealBuildTool*Catrun*'}
if($taskBuilders){throw 'Wait for the native build before loading its modules.'}
New-Item -ItemType Directory -Path $taskOutput | Out-Null
$env:CATRUN_CAPTURE_MAPS=$Maps
$taskArgs=@(('"'+$taskRoot+'/Catrun.uproject"'),'-run=pythonscript',('-script="'+$taskRoot+'/Scripts/Menu/capture_chapter_maps.py"'),'-unattended','-nop4','-utf8output','-AllowCommandletRendering','-RenderOffscreen','-onethread','-NoAsyncLoadingThread','-nosound','-NoSaveConfig','-NoCrashDialog','-culture=en',('-abslog="'+$taskOutput+'/Editor.log"'),'-dpcvars=Editor.AsyncStaticMeshCompilation=0,Editor.AsyncSkinnedAssetCompilation=0,p.EnableDeferredPhysicsCreation=0,p.Chaos.EnableAsyncInitBody=0')
$taskProcess=Start-Process -FilePath 'C:/Program Files/Epic Games/UE_5.8/Engine/Binaries/Win64/UnrealEditor-Cmd.exe' -ArgumentList $taskArgs -WindowStyle Hidden -PassThru
Remove-Item Env:CATRUN_CAPTURE_MAPS
@{pid=$taskProcess.Id;run=$Run;maps=$Maps;offscreen=$true;playback=$false} | ConvertTo-Json | Tee-Object -FilePath (Join-Path $taskOutput 'launch.json')
