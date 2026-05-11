import importlib, traceback

try:
    importlib.import_module('transformers')
    print('TRANSFORMERS_IMPORT_OK')
except Exception:
    traceback.print_exc()

try:
    importlib.import_module('torch')
    print('TORCH_IMPORT_OK')
except Exception:
    traceback.print_exc()
