#!/usr/bin/env python3
"""Own-code child-only resource limits; invoked after seccomp network denial."""
import os
import resource
import sys
if len(sys.argv) != 5:
    raise SystemExit(2)
lib, swipl, worker, bridge = sys.argv[1:]
resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
resource.setrlimit(resource.RLIMIT_CPU, (2, 3))
# Upstream reserves 4 GiB buffers; this is virtual address space, not RSS.
resource.setrlimit(resource.RLIMIT_AS, (16 * 1024**3, 16 * 1024**3))
resource.setrlimit(resource.RLIMIT_FSIZE, (16384, 16384))
resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))
env = dict(os.environ)
env['LD_PRELOAD'] = lib
os.execve(swipl, [swipl, '--stack_limit=32m', '-q', '-f', 'none', '-s', worker, '--', bridge], env)
