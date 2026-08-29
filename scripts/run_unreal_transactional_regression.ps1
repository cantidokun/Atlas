$ErrorActionPreference = "Stop"

Write-Host "Atlas Unreal transactional regression harness"

$unrealEditor = $env:ATLAS_UNREAL_EDITOR
if ([string]::IsNullOrWhiteSpace($unrealEditor)) {
    Write-Host "ATLAS_UNREAL_EDITOR is not configured; integration execution is skipped."
    exit 0
}

if (-not (Test-Path $unrealEditor)) {
    throw "ATLAS_UNREAL_EDITOR does not point to an existing executable: $unrealEditor"
}

$project = $env:ATLAS_UNREAL_PROJECT
if ([string]::IsNullOrWhiteSpace($project)) {
    throw "ATLAS_UNREAL_PROJECT must identify the Atlas Unreal project when integration execution is enabled."
}

if (-not (Test-Path $project)) {
    throw "ATLAS_UNREAL_PROJECT does not exist: $project"
}

$logDir = Join-Path $env:GITHUB_WORKSPACE "artifacts\unreal-transactional-regression"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

$logFile = Join-Path $logDir "unreal-editor.log"

$args = @(
    "`"$project`"",
    "-unattended",
    "-nop4",
    "-nosplash",
    "-NullRHI",
    "-log=`"$logFile`"",
    "-ExecCmds=`"Automation RunTests Atlas.Unreal;Quit`""
)

Write-Host "Launching Unreal Editor automation against $project"
$process = Start-Process -FilePath $unrealEditor -ArgumentList $args -Wait -PassThru

if ($process.ExitCode -ne 0) {
    throw "Unreal Editor automation exited with code $($process.ExitCode). See $logFile"
}

Write-Host "Unreal transactional integration harness completed successfully."
