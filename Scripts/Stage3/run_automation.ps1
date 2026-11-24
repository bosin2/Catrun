param([string]$Filter='Catrun',[string]$Name='Automation_All')
$ErrorActionPreference='Stop'
$stage3Root=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$stage3Out=Join-Path $stage3Root ('Saved\Stage3Integration20261125\'+$Name)
New-Item -ItemType Directory -Force -Path $stage3Out | Out-Null
$stage3Arguments=@(
    ('"{0}\Catrun.uproject"' -f $stage3Root),'-unattended','-nop4','-nosplash','-nosound','-nullrhi','-onethread','-NoSaveConfig','-NoCrashDialog',
    '-SaveToUserDir',('-UserDir="{0}\User"' -f $stage3Out),('-abslog="{0}\run.log"' -f $stage3Out),
    ('-ReportExportPath="{0}\Report"' -f $stage3Out),('-ExecCmds="Automation RunTests {0}"' -f $Filter),'-TestExit="Automation Test Queue Empty"'
)
$stage3Process=Start-Process -FilePath 'C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe' -ArgumentList $stage3Arguments -WorkingDirectory $stage3Root -WindowStyle Hidden -PassThru
@{pid=$stage3Process.Id;log=(Join-Path $stage3Out 'run.log');report=(Join-Path $stage3Out 'Report\index.json')} | ConvertTo-Json -Compress
