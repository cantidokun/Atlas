from pathlib import Path
import runpy

ROOT = Path(__file__).resolve().parent
runpy.run_path(str(ROOT / "apply_unreal_render_production_boundary.py"), run_name="__main__")
runpy.run_path(str(ROOT / "apply_unreal_render_executor_fix.py"), run_name="__main__")
print("Unreal render boundary migration complete.")
