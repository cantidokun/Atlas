"""Allow ``python -m atlas_dev_controller TASK_FILE``."""

import sys

from atlas_dev_controller.runner import main

sys.exit(main())
