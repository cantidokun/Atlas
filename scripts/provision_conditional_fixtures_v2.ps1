$ErrorActionPreference = "Stop"
$base = "C:\Users\Gavin's PC\Desktop\Atlas\goalpost_test.blend"
$correct = "C:\Users\Gavin's PC\Desktop\Atlas\goalpost_test_CONDITIONAL_CORRECT.blend"
$incorrect = "C:\Users\Gavin's PC\Desktop\Atlas\goalpost_test_CONDITIONAL_INCORRECT.blend"
if (-not (Test-Path $base)) { throw "Base Blender fixture not found: $base" }
$blender = (Get-Command blender -ErrorAction SilentlyContinue).Source
if (-not $blender) { throw "Blender executable not found on PATH." }
$script = Join-Path $env:TEMP "atlas_make_correct.py"
@'
import bpy, sys
from pathlib import Path
output = Path(sys.argv[-1])
left = bpy.data.objects.get("Goal_Left_post")
right = bpy.data.objects.get("Goal_Right_Post")
if left is None or right is None: raise RuntimeError("Required goalpost objects were not found")
left.location = (0.0, 5.233, 0.0)
right.location = (0.0, -5.233, 0.0)
bpy.ops.wm.save_as_mainfile(filepath=str(output))
'@ | Set-Content -Encoding UTF8 $script
try { & $blender -b $base --python $script -- $correct; if ($LASTEXITCODE -ne 0) { throw "Blender fixture generation failed." } }
finally { Remove-Item $script -Force -ErrorAction SilentlyContinue }
Copy-Item $base $incorrect -Force
Write-Host "Provisioned deterministic conditional Blender fixtures."
