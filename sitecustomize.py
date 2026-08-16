"""Atlas runtime path compatibility for the local GitHub Actions runner.

The existing Blender tool resolves .blend filenames relative to the legacy
Desktop\\Atlas directory. GitHub Actions checks the repository out under
GITHUB_WORKSPACE instead. Python imports sitecustomize automatically during
normal interpreter startup, so this bridge keeps the existing tool API intact
while making its root follow the Actions workspace when present.
"""

import os


workspace = os.environ.get("GITHUB_WORKSPACE")
if workspace:
    try:
        from tools import blender

        blender.ATLAS_PROJECTS = os.path.abspath(workspace)
    except Exception:
        # Do not prevent unrelated Python startup if Atlas tooling is not
        # imported successfully. The normal module import will surface the
        # underlying error in the calling process.
        pass
