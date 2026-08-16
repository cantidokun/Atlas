$ErrorActionPreference = "Stop"

if (-not $env:GITHUB_WORKSPACE) {
    throw "GITHUB_WORKSPACE is not set."
}

$workspace = (Resolve-Path -LiteralPath $env:GITHUB_WORKSPACE).Path
$source = Join-Path $workspace "goalpost_test.blend"
$correct = Join-Path $workspace "goalpost_test_CONDITIONAL_CORRECT.blend"
$incorrect = Join-Path $workspace "goalpost_test_CONDITIONAL_INCORRECT.blend"

Write-Host "Provisioner current location: $(Get-Location)"
Write-Host "GITHUB_WORKSPACE: $workspace"
Write-Host "Source path: $source"
Write-Host "Correct output path: $correct"
Write-Host "Incorrect output path: $incorrect"

if (-not (Test-Path -LiteralPath $source)) {
    throw "Base Blender fixture not found in GITHUB_WORKSPACE: $source"
}

$blender = (Get-Command blender -ErrorAction SilentlyContinue).Source
if (-not $blender) {
    $candidates = @(
        (Join-Path $env:ProgramFiles "Blender Foundation\Blender\blender.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "Blender Foundation\Blender\blender.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Blender Foundation\Blender\blender.exe")
    )
    $blender = $candidates | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -First 1
}
if (-not $blender) {
    $searchRoots = @($env:ProgramFiles, ${env:ProgramFiles(x86)}, $env:LOCALAPPDATA) | Where-Object { $_ -and (Test-Path -LiteralPath $_) }
    $found = Get-ChildItem -Path $searchRoots -Filter blender.exe -File -Recurse -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($found) { $blender = $found.FullName }
}
if (-not $blender) {
    throw "Blender executable could not be located. Install Blender or add blender.exe to PATH."
}
Write-Host "Using Blender executable: $blender"

$script = Join-Path $env:TEMP "atlas_make_correct.py"
@'
import bpy
import os
import sys

args = sys.argv
if "--" not in args:
    raise RuntimeError("Missing Blender script arguments")
script_args = args[args.index("--") + 1:]
if len(script_args) != 1:
    raise RuntimeError(f"Expected one output path, received: {script_args}")

output = os.path.abspath(script_args[0])
left = bpy.data.objects.get("Goal_Left_post")
right = bpy.data.objects.get("Goal_Right_Post")
if left is None or right is None:
    raise RuntimeError("Required goalpost objects were not found")

left.location = (0.0, 5.233, 0.0)
right.location = (0.0, -5.233, 0.0)

print(f"BLENDER_SOURCE_FILE: {bpy.data.filepath}", flush=True)
print(f"BLENDER_OUTPUT_CORRECT: {output}", flush=True)
bpy.ops.wm.save_as_mainfile(filepath=output)
print(f"BLENDER_SAVED_FILE: {bpy.data.filepath}", flush=True)

if not os.path.isfile(output) or os.path.getsize(output) <= 0:
    raise RuntimeError(f"Blender failed to create correct fixture: {output}")
print(f"CORRECT_FILE_EXISTS: True ({output})", flush=True)
'@ | Set-Content -Encoding UTF8 $script

try {
    & $blender -b $source --python-exit-code 1 --python $script -- $correct
    if ($LASTEXITCODE -ne 0) {
        throw "Blender fixture generation failed with exit code $LASTEXITCODE."
    }
}
finally {
    Remove-Item $script -Force -ErrorAction SilentlyContinue
}

Copy-Item -LiteralPath $source -Destination $incorrect -Force

if (-not (Test-Path -LiteralPath $correct)) {
    throw "Provisioner did not produce expected correct fixture: $correct"
}
if (-not (Test-Path -LiteralPath $incorrect)) {
    throw "Provisioner did not produce expected incorrect fixture: $incorrect"
}

Write-Host "Correct fixture exists: $(Test-Path -LiteralPath $correct)"
Write-Host "Incorrect fixture exists: $(Test-Path -LiteralPath $incorrect)"
Write-Host "Provisioned deterministic conditional Blender fixtures in GITHUB_WORKSPACE."