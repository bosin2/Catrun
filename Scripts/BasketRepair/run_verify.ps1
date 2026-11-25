param([switch]$PreviewOnly,[switch]$Room4Only)
$ErrorActionPreference='Stop'
$basketRoot='C:/Users/whghk/Catrun'
$basketRun="$basketRoot/Saved/BasketRepair20261125"
New-Item -ItemType Directory -Force -Path "$basketRun/RuntimeUser/Saved/SaveGames" | Out-Null
Copy-Item -LiteralPath "$basketRoot/Saved/SaveGames/CatrunProgress.sav" -Destination "$basketRun/RuntimeUser/Saved/SaveGames/CatrunProgress.sav"
$basketArgs=@("`"$basketRoot/Catrun.uproject`"",'-RenderOffscreen','-onethread','-d3d12','-windowed','-ResX=1600','-ResY=900','-NoSplash','-nosound','-unattended','-NoSaveConfig','-SaveToUserDir',"-UserDir=`"$basketRun/RuntimeUser`"",'-ini:EditorSettings:[/Script/UnrealEd.EditorPerformanceSettings]:bThrottleCPUWhenNotForeground=False',"-ExecCmds=`"Slate.bAllowThrottling 0,t.IdleWhenNotForeground 0,py $basketRoot/Scripts/BasketRepair/verify_runtime.py`"","-abslog=`"$basketRun/runtime.log`"")
if ($PreviewOnly) {$basketArgs += '-BasketRepairPreviewOnly'}
if ($Room4Only) {$basketArgs += '-BasketRepairRoom4Only'}
$basketProcess=Start-Process -FilePath 'C:/Program Files/Epic Games/UE_5.8/Engine/Binaries/Win64/UnrealEditor.exe' -ArgumentList $basketArgs -WindowStyle Hidden -PassThru
$basketProcess.Id | Set-Content "$basketRun/runtime_process.txt"
$basketProcess.Id
