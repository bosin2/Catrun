[CmdletBinding()]
param(
    [switch]$Compile,
    [string]$PythonExecutable = 'python'
)

# Default: prepare the QA project only. -Compile performs compile-only + staged link.
# Never launches/kills an editor, hot reloads, or writes main Binaries/Win64.
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 3.0

$revisionMain = 'C:\Users\whghk\Catrun'
$revisionCandidate = 'C:\Users\whghk\.codex\workspaces\ElevatorRevision3_20261125_01a21074\Catrun'
$revisionEngine = 'C:\Program Files\Epic Games\UE_5.8\Engine'
$revisionBuild = Join-Path $revisionEngine 'Build\BatchFiles\Build.bat'
$revisionSource = Join-Path $revisionEngine 'Source'
$revisionPrepare = Join-Path $PSScriptRoot 'prepare_revision3_candidate.py'
$revisionHeader = Join-Path $revisionMain 'Source\Catrun\LevelFlow\CatrunElevatorTransition.h'
$revisionCpp = Join-Path $revisionMain 'Source\Catrun\LevelFlow\CatrunElevatorTransition.cpp'
$revisionGenerated = Join-Path $revisionMain 'Intermediate\Build\Win64\UnrealEditor\Inc\Catrun\UHT\CatrunElevatorTransition.gen.cpp'
$revisionResponse = Join-Path $revisionMain 'Intermediate\Build\Win64\x64\UnrealEditor\Development\Catrun\UnrealEditor-Catrun.dll.rsp'
$revisionBinaries = Join-Path $revisionCandidate 'Binaries\Win64'
$revisionDll = Join-Path $revisionBinaries 'UnrealEditor-Catrun_ElevatorRevision3.dll'
$revisionPdb = Join-Path $revisionBinaries 'UnrealEditor-Catrun_ElevatorRevision3.pdb'

function Get-RevisionFingerprint([string]$Path) {
    $item = Get-Item -LiteralPath $Path
    [pscustomobject]@{
        Path = $item.FullName
        Length = $item.Length
        LastWriteTimeUtc = $item.LastWriteTimeUtc.ToString('o')
        SHA256 = (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
    }
}

function Assert-RevisionFingerprints($Before, $After, [switch]$IncludeTimestamp) {
    if (@($Before).Count -ne @($After).Count) { throw 'Fingerprint count changed.' }
    for ($i = 0; $i -lt @($Before).Count; $i++) {
        if ($Before[$i].Path -ne $After[$i].Path -or
            $Before[$i].Length -ne $After[$i].Length -or
            $Before[$i].SHA256 -ne $After[$i].SHA256 -or
            ($IncludeTimestamp -and $Before[$i].LastWriteTimeUtc -ne $After[$i].LastWriteTimeUtc)) {
            throw ('File changed during candidate build: ' + $Before[$i].Path)
        }
    }
}

function Invoke-RevisionNative([string]$Executable, [string[]]$Arguments, [string]$LogPath) {
    # Windows PowerShell wraps redirected native stderr as ErrorRecords. Preserve
    # native output and use the process exit code rather than treating warnings as fatal.
    $savedPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = 'Continue'
        & $Executable @Arguments 2>&1 | Tee-Object -FilePath $LogPath | ForEach-Object { Write-Host $_ }
        $nativeCode = $LASTEXITCODE
        if ($null -eq $nativeCode) { throw ('No native exit code: ' + $Executable) }
        return [int]$nativeCode
    }
    finally { $ErrorActionPreference = $savedPreference }
}

if (-not (Test-Path -LiteralPath $revisionPrepare -PathType Leaf)) {
    throw ('Missing preparation script: ' + $revisionPrepare)
}
& $PythonExecutable $revisionPrepare --source-root $revisionMain --workspace $revisionCandidate
if ($LASTEXITCODE -ne 0) { throw ('Candidate preparation failed: ' + $LASTEXITCODE) }
if (-not $Compile) {
    Write-Host 'Prepared candidate only. No compilation, linking, or editor control performed.'
    Write-Host ('To compile and link: & "' + $PSCommandPath + '" -Compile')
    return
}

$revisionProtected = @(
    (Join-Path $revisionMain 'Binaries\Win64\UnrealEditor.modules'),
    (Join-Path $revisionMain 'Binaries\Win64\UnrealEditor-Catrun.dll')
)
$revisionOwnSources = @($revisionHeader, $revisionCpp)
foreach ($required in @($revisionBuild, $revisionGenerated, $revisionResponse) + $revisionProtected + $revisionOwnSources) {
    if (-not (Test-Path -LiteralPath $required -PathType Leaf)) { throw ('Missing required file: ' + $required) }
}
# -NoHotReload cleans files listed in HotReloadState.json. Stop rather than deleting
# another session's hot-reload outputs. No such state existed during investigation.
$revisionHotReloadStates = @(Get-ChildItem -LiteralPath (Join-Path $revisionMain 'Intermediate\Build') -Filter 'HotReloadState.json' -File -Recurse)
if ($revisionHotReloadStates.Count -gt 0) {
    throw ('Hot-reload state exists; review before running -NoHotReload: ' + ($revisionHotReloadStates.FullName -join ', '))
}
$revisionRun = Join-Path $revisionCandidate ('Saved\ElevatorTransitionRevision3\Build_' + [DateTime]::UtcNow.ToString('yyyyMMdd_HHmmss_ffff'))
New-Item -ItemType Directory -Path $revisionRun | Out-Null
$revisionReport = Join-Path $revisionRun 'build-report.json'
$revisionProtectedBefore = @($revisionProtected | ForEach-Object { Get-RevisionFingerprint $_ })
$revisionSourceBefore = @($revisionOwnSources | ForEach-Object { Get-RevisionFingerprint $_ })
$revisionResult = [ordered]@{
    StartedUtc = [DateTime]::UtcNow.ToString('o')
    MainProject = $revisionMain
    CandidateProject = $revisionCandidate
    MainProtectedBefore = $revisionProtectedBefore
    OwnSourceBefore = $revisionSourceBefore
    CompileExitCode = $null
    LinkExitCode = $null
    CandidateDll = $revisionDll
    CandidatePdb = $revisionPdb
    MainProtectedUnchanged = $false
    OwnSourceContentUnchanged = $false
    Status = 'running'
    Failure = $null
}
$revisionResult | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $revisionReport -Encoding UTF8
$revisionFailure = $null
try {
    # Force UHT/header dependency consideration and recompilation of the generated
    # unit even when UHT decides its generated bytes are unchanged.
    $revisionTouchTime = [DateTime]::UtcNow
    [System.IO.File]::SetLastWriteTimeUtc($revisionHeader, $revisionTouchTime)
    [System.IO.File]::SetLastWriteTimeUtc($revisionGenerated, $revisionTouchTime)
    $revisionResult.ForcedTimestampUtc = $revisionTouchTime.ToString('o')
    $revisionArguments = @(
        'CatrunEditor', 'Win64', 'Development',
        ('-Project=' + (Join-Path $revisionMain 'Catrun.uproject')),
        '-WaitMutex', '-NoHotReload', '-NoHotReloadFromIDE', '-NoUBA',
        '-NoEngineChanges', '-ActionTypeFilter=Compile'
    )
    $revisionResult.CompileArguments = $revisionArguments
    $revisionResult.CompileExitCode = Invoke-RevisionNative $revisionBuild $revisionArguments (Join-Path $revisionRun 'compile.log')
    if ($revisionResult.CompileExitCode -ne 0) { throw ('Compile-only failed: ' + $revisionResult.CompileExitCode) }
    $revisionSourceAfterCompile = @($revisionOwnSources | ForEach-Object { Get-RevisionFingerprint $_ })
    $revisionProtectedAfterCompile = @($revisionProtected | ForEach-Object { Get-RevisionFingerprint $_ })
    $revisionResult.OwnSourceAfterCompile = $revisionSourceAfterCompile
    $revisionResult.MainProtectedAfterCompile = $revisionProtectedAfterCompile
    Assert-RevisionFingerprints $revisionSourceBefore $revisionSourceAfterCompile
    Assert-RevisionFingerprints $revisionProtectedBefore $revisionProtectedAfterCompile -IncludeTimestamp

    # Use the CURRENT response file produced by UBT, including its adaptive unity
    # membership. Never substitute an old hand-maintained list of object files.
    $revisionLines = [System.IO.File]::ReadAllLines($revisionResponse)
    if (@($revisionLines | Where-Object { $_ -match '^/OUT:' }).Count -ne 1 -or
        @($revisionLines | Where-Object { $_ -match '^/PDB:' }).Count -ne 1) {
        throw 'Expected exactly one /OUT and /PDB in the current link response.'
    }
    foreach ($requiredSwitch in @('/NOIMPLIB', '/NOEXP', '/MANIFEST:NO')) {
        if ($revisionLines -notcontains $requiredSwitch) { throw ('Re-review link outputs: missing ' + $requiredSwitch) }
    }
    if (@($revisionLines | Where-Object { $_ -match '^/(IMPLIB|ILK|MAP|MANIFESTFILE|PGD|PDBSTRIPPED|LINKREPRO)(:|$)' }).Count -gt 0) {
        throw 'The response includes additional write destinations; inspect before linking.'
    }
    $revisionToolRoots = @($revisionLines | ForEach-Object {
        if ($_ -match '^/LIBPATH:"(?<ToolRoot>.+/VC/Tools/MSVC/[^/]+)/lib/x64"$') { $Matches.ToolRoot }
    } | Select-Object -Unique)
    if ($revisionToolRoots.Count -ne 1) { throw 'Cannot identify the matching MSVC toolchain from current response.' }
    $revisionLinker = Join-Path $revisionToolRoots[0] 'bin\Hostx64\x64\link.exe'
    if (-not (Test-Path -LiteralPath $revisionLinker -PathType Leaf)) { throw ('Matching linker is absent: ' + $revisionLinker) }
    $revisionStagedResponse = Join-Path $revisionRun 'UnrealEditor-Catrun_ElevatorRevision3.dll.rsp'
    $revisionPatchedLines = @($revisionLines | ForEach-Object {
        if ($_ -match '^/OUT:') { '/OUT:"' + $revisionDll.Replace('\', '/') + '"' }
        elseif ($_ -match '^/PDB:') { '/PDB:"' + $revisionPdb.Replace('\', '/') + '"' }
        else { $_ }
    })
    [System.IO.File]::WriteAllLines($revisionStagedResponse, $revisionPatchedLines, [System.Text.UTF8Encoding]::new($false))
    $revisionResult.OriginalResponseSHA256 = (Get-FileHash -LiteralPath $revisionResponse -Algorithm SHA256).Hash
    $revisionResult.StagedResponse = $revisionStagedResponse
    $revisionResult.Linker = $revisionLinker
    Push-Location -LiteralPath $revisionSource
    try {
        $revisionResult.LinkExitCode = Invoke-RevisionNative $revisionLinker @('@' + $revisionStagedResponse) (Join-Path $revisionRun 'link.log')
    }
    finally { Pop-Location }
    if ($revisionResult.LinkExitCode -ne 0) { throw ('Candidate link failed: ' + $revisionResult.LinkExitCode) }
    foreach ($candidateOutput in @($revisionDll, $revisionPdb)) {
        if (-not (Test-Path -LiteralPath $candidateOutput -PathType Leaf) -or (Get-Item -LiteralPath $candidateOutput).Length -eq 0) {
            throw ('Missing or empty candidate output: ' + $candidateOutput)
        }
    }
    $revisionResult.CandidateOutputs = @(@($revisionDll, $revisionPdb) | ForEach-Object { Get-RevisionFingerprint $_ })
    $revisionCandidateManifest = Get-Content -LiteralPath (Join-Path $revisionBinaries 'UnrealEditor.modules') -Raw | ConvertFrom-Json
    $revisionMainManifest = Get-Content -LiteralPath $revisionProtected[0] -Raw | ConvertFrom-Json
    if ($revisionCandidateManifest.BuildId -ne $revisionMainManifest.BuildId -or
        $revisionCandidateManifest.Modules.Catrun -ne [System.IO.Path]::GetFileName($revisionDll)) {
        throw 'Candidate manifest does not identify this DLL with the current engine BuildId.'
    }
    $revisionResult.BuildId = $revisionCandidateManifest.BuildId
    $revisionResult.Status = 'linked_candidate_pending_cold_qa'
}
catch {
    $revisionFailure = $_.Exception.Message
    $revisionResult.Status = 'failed'
    $revisionResult.Failure = $revisionFailure
}
finally {
    try {
        $revisionProtectedAfter = @($revisionProtected | ForEach-Object { Get-RevisionFingerprint $_ })
        $revisionSourceAfter = @($revisionOwnSources | ForEach-Object { Get-RevisionFingerprint $_ })
        $revisionResult.MainProtectedAfter = $revisionProtectedAfter
        $revisionResult.OwnSourceAfter = $revisionSourceAfter
        Assert-RevisionFingerprints $revisionProtectedBefore $revisionProtectedAfter -IncludeTimestamp
        $revisionResult.MainProtectedUnchanged = $true
        Assert-RevisionFingerprints $revisionSourceBefore $revisionSourceAfter
        $revisionResult.OwnSourceContentUnchanged = $true
    }
    catch {
        $revisionFailure = (@($revisionFailure, $_.Exception.Message) | Where-Object { $_ }) -join ' | '
        $revisionResult.Status = 'failed'
        $revisionResult.Failure = $revisionFailure
    }
    $revisionResult.FinishedUtc = [DateTime]::UtcNow.ToString('o')
    $revisionResult | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $revisionReport -Encoding UTF8
    Write-Host ('Build report: ' + $revisionReport)
}
if ($revisionFailure) { throw $revisionFailure }
Write-Host ('Candidate linked, cold QA not yet run: ' + $revisionDll)
Write-Host 'Main DLL and module manifest are unchanged. No editor was controlled.'
