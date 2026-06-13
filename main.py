import sys

# Clear sys.modules cache if package is reloaded, manually or after an update.
assert __package__ is not None
prefix = __package__ + ".plugin"
for module_name in [module_name for module_name in sys.modules if module_name.startswith(prefix)]:
    print(f"unloading {module_name}")
    del sys.modules[module_name]
del prefix

from .plugin import *  # noqa: F401,E402,F403 # ty: ignore[unresolved-import]
