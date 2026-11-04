param([ValidateSet('Build','Automation','Cook')][string]$Phase, [string]$Run='Final01')
$ErrorActionPreference='Stop'
$taskProjectRoot=(Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$taskEngineRoot='C:\Program Files\Epic Games\UE_5.8\Engine'
$taskProject=Join-Path $taskProjectRoot 'Catrun.uproject'
$taskOutput=Join-Path $taskProjectRoot "Saved/Prototype20261104/Task5/$Run"
$taskProcesses=Get-CimInstance Win32_Process -Filter "Name='UnrealEditor.exe' OR Name='UnrealEditor-Cmd.exe'"
if ($taskProcesses) { throw 'Close the editor normally before final build/commandlet verification.' }
New-Item -ItemType Directory -Force -Path $taskOutput | Out-Null
$taskResultPath=Join-Path $taskOutput "$Phase-result.json"
if(Test-Path -LiteralPath $taskResultPath){throw 'Preserve this run; choose a fresh Run name.'}
$taskStart=[DateTimeOffset]::UtcNow
if($Phase -eq 'Build') {
    $taskBuild=Join-Path $taskEngineRoot 'Build/BatchFiles/Build.bat'
    & $taskBuild CatrunEditor Win64 Development "-Project=$taskProject" -WaitMutex -NoHotReloadFromIDE 2>&1 | Tee-Object -FilePath (Join-Path $taskOutput 'Build.log')
    $taskExit=$LASTEXITCODE
} else {
    $taskLog=Join-Path $taskOutput "$Phase.log"
    $taskArgs=@(('"'+$taskProject+'"'),'-unattended','-nop4','-utf8output',('-abslog="'+$taskLog+'"'))
    if($Phase -eq 'Automation') {
        $taskArgs+=@('-nullrhi','-nosound','-ExecCmds="Automation RunTests Catrun"','-TestExit="Automation Test Queue Empty"',('-ReportExportPath="'+(Join-Path $taskOutput 'AutomationReport')+'"'))
    } else {
        $taskArgs+=@('-run=Cook','-TargetPlatform=Windows','-Map=/Game/Maps/MainMenu+/Game/Maps/Tutorial+/Game/Maps/Stage1+/Game/Maps/Stage2',('-OutputDir="'+(Join-Path $taskOutput 'Cooked/[Platform]')+'"'))
    }
    $taskProcess=Start-Process -FilePath (Join-Path $taskEngineRoot 'Binaries/Win64/UnrealEditor-Cmd.exe') -ArgumentList $taskArgs -WindowStyle Hidden -PassThru
    Write-Output "$Phase started PID $($taskProcess.Id); log $taskLog"
    $taskProcess.WaitForExit()
    $taskExit=$taskProcess.ExitCode
}
$taskResult=@{phase=$Phase;exit_code=$taskExit;started_utc=$taskStart.ToString('o');finished_utc=[DateTimeOffset]::UtcNow.ToString('o');project=$taskProject;output=$taskOutput}
$taskResult | ConvertTo-Json | Set-Content -LiteralPath $taskResultPath -Encoding utf8
$taskResult | ConvertTo-Json -Compress | Write-Output
if($taskExit -ne 0){throw "$Phase failed with exit $taskExit. Preserve log for diagnosis."}
