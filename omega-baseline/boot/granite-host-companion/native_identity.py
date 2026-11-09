"""Match an actual mapped native executable and locked model, not nested argv."""
from pathlib import Path


def native_identity(arguments, executable, mapped_files, closure, model_path):
    closure=Path(closure)
    loader=str(closure/'system/ld-linux-x86-64.so.2')
    helpers={str(closure/'avx2/infer'),str(closure/'generic/infer')}
    if not arguments or arguments[0] not in helpers|{loader}:
        return None
    if executable not in helpers|{loader}:
        return None
    actual=helpers.intersection(arguments).intersection(mapped_files)
    if len(actual)!=1 or model_path not in mapped_files or '--model' not in arguments:
        return None
    return {'helper':next(iter(actual)), 'executable':executable,
            'mapped_locked_model':model_path, 'native_mapping_verified':True}
