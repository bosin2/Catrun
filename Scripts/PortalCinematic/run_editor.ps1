<#
Runs one Unreal process for the portal cinematic work under the shared lock.
  -Mode author  : NullRHI commandlet job_author.py (backs up, copies the Base sequences in, restores on failure)
  -Mode capture : offscreen d3d12 PIE capture (capture_pie.py), saves nothing
Waits (up to 40 min) while any UnrealEditor / UnrealEditor-Cmd / UnrealBuildTool / Build process runs or the lock exists.
#>
param([ValidateSet('author','capture','probe')][string]$Mode = 'author', [string]$Label = 'run')
$ErrorActionPreference = 'Stop'
$Root = 'C:\Users\whghk\Catrun'
$Here = Join-Path $Root 'Scripts\PortalCinematic'
$Out = Join-Path $Root 'Saved\PortalCinematic'
$Lock = Join-Path $Root 'Saved\ClaudeParallel\editor.lock'
$Eng = 'C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64'
New-Item -ItemType Directory -Force $Out | Out-Null

function Join-Quoted($a) { ($a | ForEach-Object { if ($_ -match '\s') { '"' + $_ + '"' } else { $_ } }) -join ' ' }
function Busy { @(Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -match '^(UnrealEditor|UnrealEditor-Cmd|UnrealBuildTool|Build)$' }) }
$deadline = (Get-Date).AddMinutes(40)
$have = $false
while (-not $have) {
    if ((Get-Date) -gt $deadline) { Write-Output 'PORTALCINE_WAIT_TIMEOUT'; exit 3 }
    if ((Busy).Count -eq 0 -and -not (Test-Path $Lock)) {
        try { New-Item -ItemType Directory $Lock -ErrorAction Stop | Out-Null; $have = $true } catch { }
    }
    if (-not $have) { Start-Sleep -Seconds 20 }
}
Set-Content -Path (Join-Path $Lock 'owner.txt') -Value "portal-cinematic $Mode $Label $(Get-Date -Format s) pid $PID"
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$files = @{
    'LS_Stage1_PortalExit.uasset'   = 'Content\Cinematics\Stage1\Portal\LS_Stage1_PortalExit.uasset'
    'LS_Stage2_PortalArrival.uasset' = 'Content\Cinematics\Stage2\Arrival\LS_Stage2_PortalArrival.uasset'
    'BP_Stage2PortalArrival.uasset'  = 'Content\Cinematics\Stage2\Arrival\BP_Stage2PortalArrival.uasset'
}
try {
    Write-Output "PORTALCINE_LOCK_TAKEN $(Get-Date -Format s)"
    $log = Join-Path $Out "$Mode-$Label-$stamp.log"
    $user = Join-Path $Out "User-$Mode-$Label-$stamp"
    $common = @('-unattended', '-NoSplash', '-NoSound', '-nop4', '-NoSaveConfig', '-SaveToUserDir', '-Multiprocess', '-NoLiveCoding',
        "-UserDir=$user", "-abslog=$log",
        '-ini:EditorPerProjectUserSettings:[/Script/UnrealEd.EditorLoadingSavingSettings]:bAutoSaveEnable=False',
        '-ini:EditorPerProjectUserSettings:[/Script/LiveCoding.LiveCodingSettings]:bEnabled=False')
    if ($Mode -eq 'author') {
        $backup = Join-Path $Root "Saved\Backups\PortalCinematic_$stamp"
        New-Item -ItemType Directory $backup | Out-Null
        foreach ($k in $files.Keys) { Copy-Item (Join-Path $Root $files[$k]) (Join-Path $backup $k) }
        Write-Output "PORTALCINE_BACKUP $backup"
        foreach ($k in @('LS_Stage1_PortalExit.uasset', 'LS_Stage2_PortalArrival.uasset')) {
            Copy-Item (Join-Path $Out "Base\$k") (Join-Path $Root $files[$k]) -Force
        }
        $script = (Join-Path $Here 'job_author.py').Replace('\', '/')
        $args_ = @("$Root\Catrun.uproject", '-run=pythonscript', "-script=$script", '-nullrhi',
            '-EnablePlugins=UMGToolSet,EditorToolset', '-culture=en') + $common
        $p = Start-Process -FilePath (Join-Path $Eng 'UnrealEditor-Cmd.exe') -ArgumentList (Join-Quoted $args_) -PassThru -WindowStyle Hidden
    } elseif ($Mode -eq 'probe') {
        $script = (Join-Path $Here 'probe_portal_keys.py').Replace('\', '/')
        $args_ = @("$Root\Catrun.uproject", '-run=pythonscript', "-script=$script", '-nullrhi') + $common
        $p = Start-Process -FilePath (Join-Path $Eng 'UnrealEditor-Cmd.exe') -ArgumentList (Join-Quoted $args_) -PassThru -WindowStyle Hidden
    } else {
        $script = (Join-Path $Here 'capture_pie.py').Replace('\', '/')
        $args_ = @("$Root\Catrun.uproject", '/Game/Maps/Stage1', '-RenderOffscreen', '-d3d12', '-onethread', '-windowed', '-ResX=1280', '-ResY=720',
            '-UseFixedTimeStep', '-FPS=30',
            '-ini:EditorSettings:[/Script/UnrealEd.EditorPerformanceSettings]:bThrottleCPUWhenNotForeground=False',
            '-ini:EditorPerProjectUserSettings:[/Script/UnrealEd.LevelEditorPlaySettings]:LastExecutedPlayModeType=PlayMode_InEditorFloating,[/Script/UnrealEd.LevelEditorPlaySettings]:NewWindowWidth=1280,[/Script/UnrealEd.LevelEditorPlaySettings]:NewWindowHeight=720',
            "-ExecCmds=Slate.bAllowThrottling 0,t.IdleWhenNotForeground 0,py $script") + $common
        $p = Start-Process -FilePath (Join-Path $Eng 'UnrealEditor.exe') -ArgumentList (Join-Quoted $args_) -PassThru -WindowStyle Hidden
    }
    Write-Output "PORTALCINE_STARTED pid=$($p.Id) log=$log"
    $limit = (Get-Date).AddMinutes(35)
    while (-not $p.HasExited) {
        if ((Get-Date) -gt $limit) { Stop-Process -Id $p.Id -Force; Write-Output 'PORTALCINE_KILLED_TIMEOUT'; break }
        if ($Mode -eq 'capture' -and (Test-Path $log) -and (Select-String -Path $log -Pattern 'PORTALCINE_CAPTURE_DONE' -Quiet)) {
            Start-Sleep -Seconds 8
            if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force }
            break
        }
        Start-Sleep -Seconds 5
    }
    Start-Sleep -Seconds 2
    $hits = @()
    if (Test-Path $log) { $hits = Select-String -Path $log -Pattern 'PORTALCINE_|Traceback|AssertionError|Error: ' | ForEach-Object { $_.Line.Substring(0, [Math]::Min(600, $_.Line.Length)) } }
    $hits | Select-Object -Last 40 | ForEach-Object { Write-Output $_ }
    if ($Mode -eq 'author') {
        $text = if (Test-Path $log) { Get-Content $log -Raw } else { '' }
        $ok = @{ 'BP_Stage2PortalArrival.uasset' = ($text -match 'PORTALCINE_BP True'); 'LS_Stage1_PortalExit.uasset' = ($text -match 'PORTALCINE_S1 True');
                 'LS_Stage2_PortalArrival.uasset' = ($text -match 'PORTALCINE_S2 True') }
        foreach ($k in $files.Keys) {
            if (-not $ok[$k]) { Copy-Item (Join-Path $backup $k) (Join-Path $Root $files[$k]) -Force; Write-Output "PORTALCINE_RESTORED $k" }
            else { Write-Output "PORTALCINE_KEPT $k $((Get-FileHash (Join-Path $Root $files[$k])).Hash)" }
        }
    }
    Write-Output "PORTALCINE_EXIT $($p.ExitCode)"
} finally {
    if (Test-Path $Lock) { if ((Get-Content (Join-Path $Lock "owner.txt") -ErrorAction SilentlyContinue) -match "portal-cinematic") { Remove-Item -Recurse -Force $Lock } } else { Write-Output "PORTALCINE_LOCK_ALREADY_GONE" }
    Write-Output "PORTALCINE_LOCK_RELEASED $(Get-Date -Format s)"
}
