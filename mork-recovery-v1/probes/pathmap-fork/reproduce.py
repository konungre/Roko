"""Link the authored probe against an already reviewed private native build."""
import json
from pathlib import Path
import resource
import subprocess
import sys
root = Path(sys.argv[1]).resolve(strict=True)
here = Path(__file__).resolve().parent
build = root/'sources/PeTTa/mork_ffi/target/release'
meta, = build.rglob('libpathmap-*.rmeta')
lib, = build.rglob('libpathmap-*.rlib')
cmd = [str(root/'toolchain/bin/rustc'), '--edition=2024', '-C', 'target-cpu=native',
       str(here/'fork_probe.rs'), '--extern', 'pathmap='+str(meta), '--extern',
       'pathmap='+str(lib), '-o', str(here/'fork_probe')]
for directory in sorted({p.parent for p in build.rglob('*') if p.suffix in ('.rlib', '.rmeta', '.so')}):
    cmd += ['-L', 'dependency='+str(directory)]
subprocess.run(cmd, check=True, timeout=60)
def bounds():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_AS, (512*1024**2, 512*1024**2))
    resource.setrlimit(resource.RLIMIT_CPU, (5, 5))
r = subprocess.run([str(here/'fork_probe')], capture_output=True, text=True,
                   timeout=10, preexec_fn=bounds)
print(json.dumps({'exit_code':r.returncode, 'stdout':r.stdout, 'stderr':r.stderr}, indent=2))
# Nonzero is deliberately retained: this is an expected-failure qualification.
sys.exit(r.returncode)
