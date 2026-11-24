$ErrorActionPreference='Stop'
$qaRoot=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
$qaOut=Join-Path $qaRoot 'Saved\Stage3Integration20261125'
$qaContent=Join-Path $qaRoot 'Content'
$qaAllow=Join-Path $qaOut 'blueprint_allowlist.txt'
$qaPaths=Get-ChildItem -LiteralPath $qaContent -Recurse -File -Filter *.uasset | ForEach-Object {
    $relative=$_.FullName.Substring($qaContent.Length+1).Replace('\','/')
    '/Game/'+$relative.Substring(0,$relative.Length-7)+'.'+$_.BaseName
}
[IO.File]::WriteAllLines($qaAllow,$qaPaths,[Text.UTF8Encoding]::new($false))
$qaArgs=@(('"{0}\Catrun.uproject"' -f $qaRoot),'-run=CompileAllBlueprints','-AllowListFile=Saved/Stage3Integration20261125/blueprint_allowlist.txt','-nullrhi','-onethread','-unattended','-nosound','-nop4','-NoSaveConfig',('-abslog="{0}\blueprint_compile.log"' -f $qaOut))
$qaProcess=Start-Process 'C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor-Cmd.exe' -ArgumentList $qaArgs -WorkingDirectory $qaRoot -WindowStyle Hidden -PassThru
@{pid=$qaProcess.Id;log=(Join-Path $qaOut 'blueprint_compile.log')}|ConvertTo-Json -Compress
