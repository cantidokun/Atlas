$ErrorActionPreference = "Stop"

$projectRoot = "C:\Users\Gavin's PC\Desktop\Atlas"
$base = Join-Path $projectRoot "goalpost_test.blend"
$workspace = $env:GITHUB_WORKSPACE
if (-not $workspace) { throw "GITHUB_WORKSPACE is not set." }
if (-not (Test-Path $base)) { throw "Base Blender fixture not found: $base" }

$blender = (Get-Command blender -ErrorAction SilentlyContinue).Source
if (-not $blender) {
    $candidates = @(
        "C:\Program Files\Blender Foundation\Blender 4.4\blender.exe",
        "C:\Program Files\Blender Foundation\Blender 4.3\blender.exe"
    )
    $blender = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if (-not $blender) { throw "Blender executable not found on PATH or known install locations." }

$workspaceBase = Join-Path $workspace "goalpost_test_BASE_ATLAS_TEST.blend"
$workspaceBefore = Join-Path $workspace "goalpost_test_BEFORE_ATLAS_TEST.blend"
$workspaceCorrect = Join-Path $workspace "goalpost_test_CONDITIONAL_CORRECT.blend"
$workspaceIncorrect = Join-Path $workspace "goalpost_test_CONDITIONAL_INCORRECT.blend"
$projectCorrect = Join-Path $projectRoot "goalpost_test_CONDITIONAL_CORRECT.blend"
$projectIncorrect = Join-Path $projectRoot "goalpost_test_CONDITIONAL_INCORRECT.blend"
$correctScript = Join-Path $env:TEMP "atlas_make_correct.py"
$incorrectScript = Join-Path $env:TEMP "atlas_make_incorrect.py"

Copy-Item $base $workspaceBase -Force
Copy-Item $base $workspaceBefore -Force

@'
import bpy
import sys
from pathlib import Path

output = Path(sys.argv[-1])
left = bpy.data.objects.get("Goal_Left_post")
right = bpy.data.objects.get("Goal_Right_Post")
if left is None or right is None:
    raise RuntimeError("Required goalpost objects were not found")
left.location = (0.0, 5.233, 0.0)
right.location = (0.0, -5.233, 0.0)
bpy.ops.wm.save_as_mainfile(filepath=str(output))
'@ | Set-Content -Encoding UTF8 $correctScript

@'
import bpy
import sys
from pathlib import Path

output = Path(sys.argv[-1])
left = bpy.data.objects.get("Goal_Left_post")
right = bpy.data.objects.get("Goal_Right_Post")
if left is None or right is None:
    raise RuntimeError("Required goalpost objects were not found")
# Explicitly construct a known-wrong state. Do not inherit the base fixture's state.
left.location = (0.0, 5.302, 0.0)
right.location = (0.0, -5.164, 0.0)
bpy.ops.wm.save_as_mainfile(filepath=str(output))
'@ | Set-Content -Encoding UTF8 $incorrectScript

try {
    & $blender -b $workspaceBase --python $correctScript -- $workspaceCorrect
    if ($LASTEXITCODE -ne 0) { throw "Blender correct-fixture generation failed." }

    & $blender -b $workspaceBase --python $incorrectScript -- $workspaceIncorrect
    if ($LASTEXITCODE -ne 0) { throw "Blender incorrect-fixture generation failed." }
}
finally {
    Remove-Item $correctScript -Force -ErrorAction SilentlyContinue
    Remove-Item $incorrectScript -Force -ErrorAction SilentlyContinue
}

Copy-Item $workspaceCorrect $projectCorrect -Force
Copy-Item $workspaceIncorrect $projectIncorrect -Force

Write-Host "Provisioned deterministic conditional Blender fixtures."
Write-Host "Workspace correct fixture: $workspaceCorrect"
Write-Host "Workspace incorrect fixture: $workspaceIncorrect"
Write-Host "Project correct fixture: $projectCorrect"
Write-Host "Project incorrect fixture: $projectIncorrect"
