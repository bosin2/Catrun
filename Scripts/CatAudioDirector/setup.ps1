$ErrorActionPreference = 'Stop'
# Per-user portable package; existing Codex, project, and UE settings are preserved.
python "$PSScriptRoot/cat_audio.py" doctor
if ($LASTEXITCODE -ne 0) {
    winget install --id Gyan.FFmpeg.Essentials --exact --source winget --scope user --accept-package-agreements --accept-source-agreements --disable-interactivity
    if ($LASTEXITCODE -ne 0) { throw 'FFmpeg installation failed.' }
    python "$PSScriptRoot/cat_audio.py" doctor
    if ($LASTEXITCODE -ne 0) { throw 'Audio dependency verification failed.' }
}
Write-Output 'Audio tools ready. Suno login and paid generation are separate steps.'
