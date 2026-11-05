param([int]$Run, [string]$Script = 'author_menu.py')
$ErrorActionPreference = 'Stop'
$taskMenuRoot = (Resolve-Path (Join-Path $PSScriptRoot '../..')).Path
$taskMenuOutput = Join-Path $taskMenuRoot 'Saved/Menu20261105'
$taskMenuExisting = Get-CimInstance Win32_Process -Filter "Name = 'UnrealEditor-Cmd.exe' OR Name = 'UnrealEditor.exe'" | Where-Object { $_.CommandLine -like ('*' + $taskMenuRoot + '*') }
if ($taskMenuExisting) { throw 'A Catrun editor process is already running; obtain a fresh exclusive lease.' }
$taskMenuLog = Join-Path $taskMenuOutput "author-$Run.log"
$taskMenuArgs = @((Join-Path $taskMenuRoot 'Catrun.uproject'), '-run=pythonscript',
    ('-script=' + (Join-Path $PSScriptRoot $Script)), '-EnablePlugins=UMGToolSet',
    '-unattended', '-nullrhi', '-nosound', '-NoSplash', '-NoSaveConfig', '-nop4', '-culture=en', '-NoCrashDialog',
    ('-abslog=' + $taskMenuLog))
$taskMenuProcess = Start-Process -FilePath 'C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe' -ArgumentList $taskMenuArgs -WindowStyle Hidden -PassThru
$taskMenuProcess.Id | Set-Content (Join-Path $taskMenuOutput 'author-pid.txt')
Write-Output ('PID=' + $taskMenuProcess.Id)
if ($taskMenuProcess.WaitForExit(30000)) {
    $taskMenuProcess.Refresh()
    $taskMenuProcess.ExitCode | Set-Content (Join-Path $taskMenuOutput "author-$Run-exit.txt")
    Write-Output ('EXIT=' + $taskMenuProcess.ExitCode)
    Get-Content $taskMenuLog | Select-String -Pattern 'LogPython: Error|CATRUN_MENU_.*COMPLETE' -Context 0,2
} else {
    Write-Output 'RUNNING'
}
