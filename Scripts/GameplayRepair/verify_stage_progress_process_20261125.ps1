[CmdletBinding()]
param(
    [string]$Editor = 'C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe',
    [string]$Project = (Join-Path $PSScriptRoot '..\..\Catrun.uproject'),
    [ValidateRange(30, 3600)]
    [int]$TimeoutSeconds = 240
)

$ErrorActionPreference = 'Stop'
$editorPath = (Resolve-Path -LiteralPath $Editor).Path
$projectPath = (Resolve-Path -LiteralPath $Project).Path
$projectDirectory = Split-Path -Parent $projectPath
$testName = 'Catrun.LevelFlow.StageProgressCrossProcess'
$runId = [Guid]::NewGuid().ToString('N')
$runRoot = Join-Path ([IO.Path]::GetTempPath()) "CatrunStageProgressProcess-$runId"
$userDirectory = Join-Path $runRoot 'User'
$slotPath = Join-Path $userDirectory 'Saved\SaveGames\CatrunProgress.sav'
$chapterSeedPath = Join-Path $runRoot 'chapter-seed.sav'
New-Item -ItemType Directory -Path $runRoot | Out-Null
New-Item -ItemType Directory -Path $userDirectory | Out-Null
Set-Content -LiteralPath (Join-Path $runRoot 'progress-process.marker') -Value $runId -Encoding ascii
Write-Host "Stage progress process evidence: $runRoot"

$results = @()
foreach ($phase in @('write', 'read', 'reset', 'readreset')) {
    $logPath = Join-Path $runRoot "$phase.log"
    $reportPath = Join-Path $runRoot "$phase-report"
    $arguments = @(
        ('"{0}"' -f $projectPath)
        '-unattended'
        '-nop4'
        '-nosplash'
        '-nullrhi'
        '-nosound'
        '-SaveToUserDir'
        ('-UserDir="{0}"' -f $userDirectory)
        ('-CatrunProgressProcessRoot="{0}"' -f $runRoot)
        ('-CatrunProgressProcessMode={0}' -f $phase)
        ('-abslog="{0}"' -f $logPath)
        ('-ReportExportPath="{0}"' -f $reportPath)
        ('-ExecCmds="Automation RunTests {0}"' -f $testName)
        '-TestExit="Automation Test Queue Empty"'
    )
    $process = Start-Process -FilePath $editorPath -WorkingDirectory $projectDirectory -ArgumentList $arguments -WindowStyle Hidden -PassThru
    try {
        $processId = $process.Id
        Write-Host "$phase started in process $processId"
        if (-not $process.WaitForExit($TimeoutSeconds * 1000)) {
            $process.Kill()
            throw "$phase exceeded $TimeoutSeconds seconds. Evidence: $runRoot"
        }
        if ($process.ExitCode -ne 0) {
            throw "$phase exited $($process.ExitCode). Log: $logPath"
        }
    }
    finally {
        $process.Dispose()
    }

    $indexPath = Join-Path $reportPath 'index.json'
    if (-not (Test-Path -LiteralPath $indexPath -PathType Leaf)) {
        throw "$phase exited without an automation report. Log: $logPath"
    }
    $report = Get-Content -LiteralPath $indexPath -Raw | ConvertFrom-Json
    $tests = @($report.tests | Where-Object { $_.fullTestPath -eq $testName })
    if ($tests.Count -ne 1 -or $tests[0].state -ne 'Success') {
        throw "$phase did not pass $testName. Report: $indexPath"
    }
    $modeEvidence = "Cross-process stage progress [$phase]"
    $ranRequestedMode = Select-String -LiteralPath $logPath -SimpleMatch -Pattern $modeEvidence -Quiet
    if (-not $ranRequestedMode) {
        throw "$phase did not confirm its isolated slot. Log: $logPath"
    }
    if (-not (Test-Path -LiteralPath $slotPath -PathType Leaf)) {
        throw "$phase completed without an isolated progress file. Log: $logPath"
    }
    $slotHash = (Get-FileHash -LiteralPath $slotPath -Algorithm SHA256).Hash
    if ($phase -ne 'write') {
        if ($slotHash -ne $results[-1].slot_sha256) {
            throw "$phase changed the Stage2 chapter slot. Evidence: $runRoot"
        }
    }
    if ($phase -eq 'read') {
        Copy-Item -LiteralPath $slotPath -Destination $chapterSeedPath
        $chapterSeedHash = (Get-FileHash -LiteralPath $chapterSeedPath -Algorithm SHA256).Hash
        if ($chapterSeedHash -ne $slotHash) {
            throw "Chapter seed bytes differ from the verified slot. Evidence: $runRoot"
        }
    }
    $results += [pscustomobject]@{
        phase = $phase
        process_id = $processId
        report = $indexPath
        log = $logPath
        slot_sha256 = $slotHash
    }
}

$summary = [pscustomobject]@{
    status = 'passed'
    run_root = $runRoot
    slot = $slotPath
    chapter_seed = $chapterSeedPath
    chapter_seed_sha256 = $chapterSeedHash
    phases = $results
}
$summaryPath = Join-Path $runRoot 'result.json'
$summary | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $summaryPath -Encoding UTF8
$summary
