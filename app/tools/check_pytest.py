# tools/check_pytest.py
import importlib
try:
    pytest = importlib.import_module("pytest")
    print("pytest import OK, version:", getattr(pytest, "__version__", "unknown"))
except Exception as e:
    print("pytest import FAILED:", repr(e))
