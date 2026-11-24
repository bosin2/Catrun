$ErrorActionPreference = 'Stop'
$basketRoot = 'C:/Users/whghk/Catrun'
$basketRun = "$basketRoot/Saved/BasketIntegration20261125"
$basketUser = "$basketRun/PIEUser"
if (Test-Path -LiteralPath "$basketRun/PIE/report.json") {
    $basketStamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    Copy-Item -LiteralPath "$basketRun/PIE/report.json" -Destination "$basketRun/PIE/report_$basketStamp.json"
}
New-Item -ItemType Directory -Force "$basketUser/Saved/SaveGames" | Out-Null
Copy-Item -LiteralPath "$basketRoot/Saved/SaveGames/CatrunProgress.sav" -Destination "$basketUser/Saved/SaveGames/CatrunProgress.sav"
$basketArguments = @(
    "`"$basketRoot/Catrun.uproject`"", '-RenderOffscreen', '-onethread', '-d3d11', '-windowed', '-ResX=1280', '-ResY=720',
    '-NoSplash', '-NoSound', '-unattended', '-nop4', '-SaveToUserDir', "-UserDir=`"$basketUser`"",
    '-ini:EditorSettings:[/Script/UnrealEd.EditorPerformanceSettings]:bThrottleCPUWhenNotForeground=False',
    "-ExecCmds=`"Slate.bAllowThrottling 0,t.IdleWhenNotForeground 0,py $basketRoot/Scripts/BasketIntegration/verify_pie.py`"", "-abslog=`"$basketRun/pie.log`""
)
$basketProcess = Start-Process -FilePath 'C:/Program Files/Epic Games/UE_5.8/Engine/Binaries/Win64/UnrealEditor.exe' -ArgumentList $basketArguments -WindowStyle Hidden -PassThru
$basketProcess.Id | Set-Content "$basketRun/pie_process.txt"
Write-Output "Basket PIE process: $($basketProcess.Id)"
