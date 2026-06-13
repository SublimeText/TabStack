import sys

print(__package__)
# clear modules cache if package is reloaded (after update?)
prefix = __package__ + ".plugin"  # don't clear the base package
for module_name in [
    module_name
    for module_name in sys.modules
    if module_name.startswith(prefix)
]:
    print(f"unloading {module_name}")
    del sys.modules[module_name]
del prefix

from .plugin import *  # noqa: F401,E402,F403
