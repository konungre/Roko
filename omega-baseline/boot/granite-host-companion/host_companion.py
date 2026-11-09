"""Explicit native-host admission for the current bounded portable provider.

The actual Omega contract, prompt renderer, parser and supervised chat are
inherited. This is host inference, never a claim of guest inference.
"""
import json
import os
from pathlib import Path
import socket
import subprocess
import time

from granite_guest import GraniteGuestProvider, verified_file
from runtime_select import choose, resolved_paths, LIBRARIES
import host_model


class HostFile:
    def __init__(self, fd, report):
        self.fd, self.report = fd, report
        self.helper_path = Path(f'/proc/{os.getpid()}/fd/{fd}')
    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None


class HostCompanionProvider(GraniteGuestProvider):
    def start(self):
        self.stop()
        began = time.monotonic()
        deadline = began + 30
        try:
            manifest = json.loads((self.root / 'host-companion.lock.json').read_text())
            if manifest.get('status') != 'host-companion-admitted-for-probe':
                raise ValueError('Host companion awaits explicit execution admission')
            # Actual inherited seccomp restriction, not just offline environment variables.
            try:
                probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            except PermissionError:
                pass
            else:
                probe.close()
                raise ValueError('Host companion requires child-only network denial')
            for relative, expected in manifest['files'].items():
                path = Path(relative)
                if path.is_absolute() or '..' in path.parts:
                    raise ValueError('Unexpected local companion path')
                verified_file(self.root/path, expected, deadline)
            for name, expected in manifest['external_files'].items():
                path = Path(name)
                if not path.is_absolute() or not str(path).startswith(str(host_model.ROOT) + '/'):
                    raise ValueError('Unexpected external companion dependency')
                verified_file(path, expected, deadline)
            closure = Path(manifest['native_closure'])
            system = closure/'system'
            loader = system/'ld-linux-x86-64.so.2'
            common = [str(loader),'--inhibit-cache','--glibc-hwcaps-mask','',
                      '--library-path',str(closure/'avx2/lib')+':'+str(system)]
            proof = None
            try:
                cpuid = subprocess.run([*common,str(closure/'cpuid-probe')],capture_output=True,text=True,
                                       timeout=3,check=True,env={'PATH':'/usr/bin:/bin','LC_ALL':'C'})
                if len(cpuid.stdout)>4096 or cpuid.stderr:
                    raise ValueError('Unbounded CPU diagnostic')
                proof = json.loads(cpuid.stdout)
            except (OSError,ValueError,subprocess.SubprocessError):
                pass
            self.cpu_proof = proof
            self.backend = choose(proof,manifest['optimized_loader_admitted'])
            executable = closure/self.backend/'infer'
            ignored=':'.join([str(executable),*LIBRARIES,*(str(closure/'avx2/lib'/n) for n in LIBRARIES)])
            self.command_prefix = common[:-2]+['--inhibit-rpath',ignored]+common[-2:]+[str(executable)]
            listing=subprocess.run(self.command_prefix[:-1]+['--list',str(executable)],capture_output=True,
                                   text=True,timeout=5,check=True,env={'PATH':'/usr/bin:/bin','LC_ALL':'C'})
            if listing.stderr or len(listing.stdout)>16384:
                raise ValueError('Unexpected host loader output')
            expected={n:str(system/n) for n in ('libc.so.6','libm.so.6','libgcc_s.so.1','libstdc++.so.6','ld-linux-x86-64.so.2')}
            if self.backend=='avx2':
                expected.update({n:str(closure/'avx2/lib'/n) for n in LIBRARIES})
            if resolved_paths(listing.stdout)!=expected:
                raise ValueError('Unadmitted native-host resolution')
            remaining=deadline-time.monotonic()
            if remaining<=0:
                raise TimeoutError('Host startup verification deadline')
            fd, report=host_model.open_model(seconds=remaining)
            self._raw_model=HostFile(fd,report)
            self.model=self._raw_model.helper_path
            self.startup_seconds=round(time.monotonic()-began,3)
            self.ready=True
        except BaseException:
            self.stop()
            raise
