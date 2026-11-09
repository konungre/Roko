#!/usr/bin/env python3
"""Explicit --run gate for one exact locked model, no copy or host filesystem export.

Requires a coordinated lane grant outside this script. Default only prints the
source plan. Existing accepted root is opened read-only and never copied.
"""
import argparse
import gzip
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "granite-model-guest"))
import host_model
import prepare_extended as prepare

ROOT = prepare.ROOT
HERE = Path(__file__).resolve().parent
RESERVE = 4 * 1024**3


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


archive = load('raw_probe_archive', ROOT / 'boot/build.py')
root_image = load('raw_probe_root_image', ROOT / 'boot/disk-root-guest/image.py')


def disk_free():
    info = os.statvfs(ROOT)
    return info.f_bavail * info.f_frsize


def available():
    for line in Path('/proc/meminfo').read_text().splitlines():
        if line.startswith('MemAvailable:'):
            return int(line.split()[1]) * 1024
    raise ValueError('Missing host memory admission')


def fd_hash(fd, seconds=120):
    deadline = time.monotonic() + seconds
    digest = hashlib.sha256()
    length = os.fstat(fd).st_size
    offset = 0
    while offset < length:
        if time.monotonic() >= deadline:
            raise TimeoutError('Bounded root hash deadline')
        chunk = os.pread(fd, min(4 * 1024**2, length-offset), offset)
        if not chunk:
            raise ValueError('Short root image')
        digest.update(chunk)
        offset += len(chunk)
    return digest.hexdigest()


def unpack(data):
    expected = archive.inspect(data)
    entries = {}
    offset = 0
    while True:
        fields = [int(data[offset+6+i*8:offset+14+i*8], 16) for i in range(13)]
        offset += 110
        name = data[offset:offset+fields[11]-1].decode()
        offset += fields[11]
        offset += -offset % 4
        value = data[offset:offset+fields[6]]
        offset += fields[6]
        offset += -offset % 4
        if name == 'TRAILER!!!':
            break
        entries[name] = (value, fields[1], fields[9], fields[10])
    if set(entries) != set(expected):
        raise ValueError('Archive extractor mismatch')
    return entries


def prepared_delta(execution_admitted=False):
    # Preparation remains disabled. Only explicit --run creates ephemeral test
    # manifests after verifying the successful synthetic receipt and exact source.
    prepare.synthetic_proof()
    import sys
    raw_dir = ROOT / 'boot/granite-raw-block'
    if str(raw_dir) not in sys.path:
        sys.path.append(str(raw_dir))
    raw_prepare = load('raw_transport_delta_preparer', raw_dir / 'prepare.py')
    raw_prepare.tiny_delta()  # Checks accepted bootstrap/source/receipt, no VM.
    original = (ROOT / 'boot/disk-root-guest/init.sh').read_bytes()
    manifest = json.loads((prepare.OUT / 'manifest.json').read_text())
    files = {}
    for name, pin in manifest['files'].items():
        data = (prepare.OUT / 'roko' / name).read_bytes()
        if prepare.sha(data) != pin['sha256'] or len(data) != pin['bytes']:
            raise ValueError('Candidate closure changed')
        files['roko/' + name] = (data, pin['mode'])
    raw_name = 'roko/granite-raw-transport.lock.json'
    runtime_name = 'roko/granite-portable-runtime.lock.json'
    raw = json.loads(files[raw_name][0])
    runtime = json.loads(files[runtime_name][0])
    if execution_admitted:
        raw.update(status='raw-model-transport-admitted', reviewed_admission=True)
        raw_data = (json.dumps(raw, indent=2) + '\n').encode()
        files[raw_name] = (raw_data, 0o444)
        runtime.update(status='candidate-runtime-admitted-for-single-probe', optimized_loader_admitted=True)
        runtime['files']['granite-raw-transport.lock.json'] = prepare.sha(raw_data)
        files[runtime_name] = ((json.dumps(runtime, indent=2) + '\n').encode(), 0o444)
    files['guest_request.py'] = ((HERE / 'guest_request.py').read_bytes(), 0o444)
    shell = b'''#!/bin/sh
[ "$$" = 1 ] || exit 90
exec </dev/console >/dev/console 2>&1
export PATH=/usr/bin:/bin
cd /run/granite-model-probe || exit 91
if ! /bin/busybox sha256sum -c files.sha256; then
    echo ROKO_GRANITE_GUEST_HASH_FAILURE
    /bin/busybox poweroff -f
    while :; do /bin/busybox sleep 1; done
fi
/usr/bin/python3.13 -I /run/granite-model-probe/guest_request.py
rc=$?
echo ROKO_GRANITE_GUEST_EXIT "$rc"
/bin/busybox poweroff -f
while :; do /bin/busybox sleep 1; done
'''
    files['init'] = (shell, 0o755)
    files['files.sha256'] = ((''.join(prepare.sha(data) + '  ' + name + '\n' for name,(data,_) in sorted(files.items()))).encode(),0o444)
    insertion = b'$BB mkdir -m 700 /newroot/run/granite-model-probe || fail model-probe-dir\n$BB cp -a /granite-model-probe/. /newroot/run/granite-model-probe/ || fail model-probe-copy\n'
    init = original.replace(raw_prepare.SOURCE_HOOK, insertion).replace(raw_prepare.SWITCH_HOOK, b'exec /bin/busybox switch_root /newroot /run/granite-model-probe/init\n')
    entries = {'init': (init,stat.S_IFREG|0o755,0,0), 'granite-model-probe':(b'',stat.S_IFDIR|0o700,0,0)}
    for name,(data,mode) in files.items():
        destination = 'granite-model-probe/' + name
        entries[destination] = (data,stat.S_IFREG|mode,0,0)
        for parent in Path(destination).parents:
            if str(parent) != '.':
                entries.setdefault(str(parent),(b'',stat.S_IFDIR|0o700,0,0))
    total = sum(len(row[0]) for row in entries.values())
    if total > 20 * 1024**2:
        raise ValueError('Model probe payload exceeds 20 MiB')
    plan = {'status':'explicit-single-probe-admission' if execution_admitted else 'prepared-awaiting-execution-grant',
            'payload_bytes':total,'model_included':False,'model_copy_created':False,
            'guest_root_build_id':raw_prepare.ROOT_ID,'root_sha256':raw_prepare.ROOT_SHA,
            'base_bootstrap_sha256':raw_prepare.BOOTSTRAP_SHA,
            'candidate_manifest_sha256':prepare.sha((prepare.OUT/'manifest.json').read_bytes()),
            'synthetic_receipt_sha256':prepare.RECEIPT_SHA,
            'bounds':{'guest_memory_mib':6144,'tcg_cpus':1,'emulated_cpu':'max','native_rss_bytes':5*1024**3,
                      'guest_available_floor_bytes':512*1024**2,'native_rlimit_as_bytes':6*1024**3,
                      'sampler_sleep_seconds':0.1,'startup_seconds':120,'native_seconds':900,'provider_seconds':930,
                      'vm_seconds':1200,'host_available_floor_bytes':2*1024**3,'host_disk_floor_bytes':RESERVE},
            'request':'Calculate 7 * 8. Use record_answer with text containing only the integer result.',
            'expected':'56','input_token_cap':512,'output_token_cap':64,'no_action_dispatch':True,
            'limitations':'Emulated CPUID does not describe host or user target hardware; fit, hash cost and TCG latency unproven.'}
    return entries,plan


def assemble(out):
    delta,plan = prepared_delta(execution_admitted=True)
    base = ROOT / 'build/disk-root-guest/bootstrap.cpio.gz'
    raw = gzip.decompress(base.read_bytes())
    manifest = json.loads((base.parent / 'bootstrap.json').read_text())
    if archive.inspect(raw) != manifest['entries']:
        raise ValueError('Base archive entries changed')
    entries = unpack(raw)
    if set(entries) & set(delta) != {'init'}:
        raise ValueError('Unexpected runtime delta collision')
    entries.update(delta)
    stream = b''.join(archive.entry(name,value,mode,index+1,major,minor)
                      for index,(name,(value,mode,major,minor)) in enumerate(sorted(entries.items())))
    stream += archive.entry('TRAILER!!!',b'',0,len(entries)+1)
    stream += b'\0' * (-len(stream)%512)
    zipped = gzip.compress(stream,compresslevel=1,mtime=0)
    if len(zipped)>20*1024**2:
        raise ValueError('Runtime bootstrap exceeds 20 MiB')
    target = out/'bootstrap.cpio.gz'
    with target.open('xb') as destination:
        destination.write(zipped)
    target.chmod(0o444)
    plan.update(initramfs_sha256=prepare.sha(zipped),initramfs_bytes=len(zipped),assembled=True,
                entries=archive.inspect(stream))
    (out/'assembly.json').write_text(json.dumps(plan,indent=2)+'\n')
    return target,plan


def command(assets, bootstrap, root_fd, model_fd, admitted):
    args = [assets['qemu']['path'], '-no-user-config', '-nodefaults', '-machine', 'q35,accel=tcg',
            '-m', '6144', '-smp', '1', '-cpu', 'max', '-display', 'none', '-monitor', 'none', '-serial', 'stdio',
            '-nic', 'none', '-no-reboot', '-kernel', assets['kernel']['path'], '-initrd', str(bootstrap),
            '-append', 'console=ttyS0 rdinit=/init panic=1']
    args += root_image.attach(root_fd)  # vda, accepted root, O_RDONLY.
    args += host_model.attachment(model_fd, admitted)  # vdb, exact locked model inode, O_RDONLY.
    return args


def terminate(proc):
    if proc is not None and proc.poll() is None:
        os.killpg(proc.pid, signal.SIGTERM)
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            proc.wait(timeout=3)


def run():
    before_free = disk_free()
    if before_free < RESERVE + 64 * 1024**2 or available() < 8 * 1024**3:
        raise ValueError('Requires 4 GiB free disk plus 64 MiB output allowance and 8 GiB host MemAvailable')
    build_parent = ROOT / 'build/granite-model-guest'
    result_parent = ROOT / 'results/granite-model-guest'
    build_parent.mkdir(mode=0o700, exist_ok=True)
    result_parent.mkdir(mode=0o700, exist_ok=True)
    attempt = 1
    while (build_parent / f'attempt-{attempt}').exists() or (result_parent / f'attempt-{attempt}').exists():
        attempt += 1
    out = build_parent / f'attempt-{attempt}'
    result = result_parent / f'attempt-{attempt}'
    out.mkdir(mode=0o700)
    result.mkdir(mode=0o700)
    report = {'passed': False, 'boot_tested': False, 'model_attached': False, 'model_loaded': False,
              'host_directory_shared': False, 'network_enabled': False, 'memory_mib': 6144,
              'tcg_cpus': 1, 'vm_wall_seconds': 1200, 'host_rss_cap_bytes': 7 * 1024**3,
              'host_available_reserve_bytes': 2 * 1024**3, 'free_disk_before': before_free,
              'errors': [], 'result_path': str(result.relative_to(ROOT)), 'runtime_payload_assembled': False}
    root_fd = model_fd = None
    proc = None
    try:
        integrity = load('raw_probe_tooling_integrity', ROOT / 'boot/verify-tooling.py').verify()
        if not integrity['success']:
            raise ValueError('Pinned QEMU/tooling runtime integrity failed')
        report['tooling_integrity'] = integrity
        assets = json.loads((ROOT / 'boot/boot-assets.lock.json').read_text())
        for name in ('qemu', 'kernel'):
            if prepare.sha(Path(assets[name]['path']).read_bytes()) != assets[name]['sha256']:
                raise ValueError('Pinned executable asset changed: ' + name)
        report['assets'] = {name: assets[name] for name in ('qemu', 'kernel')}
        bootstrap, plan = assemble(out)
        report['runtime_payload_assembled'] = True
        report['assembly'] = plan
        hash_start = time.monotonic()
        model_fd, report['model_before'] = host_model.open_model()
        report['host_model_hash_before_seconds'] = round(time.monotonic()-hash_start,3)
        root_fd = root_image.open_image(ROOT)
        hash_start = time.monotonic()
        report['root_sha256_before'] = fd_hash(root_fd)
        report['host_root_hash_before_seconds'] = round(time.monotonic()-hash_start,3)
        if report['root_sha256_before'] != plan['root_sha256']:
            raise ValueError('Accepted immutable root hash changed')
        if disk_free() < RESERVE or available() < 8 * 1024**3:
            raise ValueError('Resource reserve changed before VM launch')
        args = command(assets, bootstrap, root_fd, model_fd, report['model_before'])
        report['command'] = args
        with (result / 'serial.txt').open('xb') as serial, (result / 'qemu-stderr.txt').open('xb') as err:
            start = time.monotonic()
            proc = subprocess.Popen(args, stdin=subprocess.DEVNULL, stdout=serial, stderr=err,
                                    pass_fds=(root_fd, model_fd), start_new_session=True,
                                    env={'PATH': '/usr/bin:/bin', 'LC_ALL': 'C'})
            report['boot_tested'] = True
            report['model_attached'] = True
            report['peak_qemu_rss_kib'] = 0
            while proc.poll() is None:
                if time.monotonic() - start > 1200:
                    raise TimeoutError('Real-model VM wall deadline exceeded')
                try:
                    status = Path(f'/proc/{proc.pid}/status').read_text()
                    for line in status.splitlines():
                        if line.startswith(('VmHWM:', 'VmRSS:')):
                            report['peak_qemu_rss_kib'] = max(report['peak_qemu_rss_kib'], int(line.split()[1]))
                except FileNotFoundError:
                    pass
                if report['peak_qemu_rss_kib'] * 1024 > report['host_rss_cap_bytes']:
                    raise MemoryError('Real-model QEMU RSS cap exceeded')
                if available() < report['host_available_reserve_bytes']:
                    raise MemoryError('Host available memory reserve crossed')
                if disk_free() < RESERVE or serial.tell() + err.tell() > 8 * 1024**2:
                    raise ValueError('Real-model log/disk reserve exceeded')
                time.sleep(.1)
            report['elapsed_seconds'] = round(time.monotonic()-start, 3)
            report['qemu_returncode'] = proc.returncode
        log = (result / 'serial.txt').read_text(errors='replace')
        markers = [line.removeprefix('ROKO_GRANITE_GUEST_RESULT ') for line in log.splitlines()
                   if line.startswith('ROKO_GRANITE_GUEST_RESULT ')]
        if len(markers) != 1:
            raise ValueError('Expected one guest transport receipt')
        report['guest'] = json.loads(markers[0])
        report['model_loaded'] = report['guest'].get('model_loaded')
        report['format_valid'] = report['guest'].get('format_valid', False)
        report['accuracy_passed'] = report['guest'].get('accuracy_passed', False)
        report['lifecycle_passed'] = proc.returncode == 0 and any('ROKO_GRANITE_GUEST_EXIT ' + str(code) in log for code in (0, 1)) and 'Power down' in log
        if not report['guest'].get('passed') or not report['lifecycle_passed']:
            raise ValueError('Real-model inference/accuracy or lifecycle gate failed')
    except BaseException as error:
        report['errors'].append(type(error).__name__ + ': ' + str(error))
    finally:
        terminate(proc)
        if proc is not None:
            report['elapsed_seconds'] = round(time.monotonic()-start,3)
            report['qemu_returncode'] = proc.returncode
        report['qemu_running_after_cleanup'] = proc is not None and proc.poll() is None
        if model_fd is not None:
            try:
                hash_start = time.monotonic()
                report['model_after'] = host_model.verify(model_fd, report.get('model_before'))
                report['host_model_hash_after_seconds'] = round(time.monotonic()-hash_start,3)
                report['model_unchanged'] = report['model_after'] == report.get('model_before')
            except BaseException as error:
                report['errors'].append('Model postcheck: ' + str(error))
            os.close(model_fd)
        if root_fd is not None:
            try:
                hash_start = time.monotonic()
                report['root_sha256_after'] = fd_hash(root_fd)
                report['host_root_hash_after_seconds'] = round(time.monotonic()-hash_start,3)
                report['root_unchanged'] = report['root_sha256_after'] == report.get('root_sha256_before') == report['assembly']['root_sha256']
            except BaseException as error:
                report['errors'].append('Root postcheck: ' + str(error))
            os.close(root_fd)
        report['free_disk_after'] = disk_free()
        report['passed'] = (not report['errors'] and report.get('lifecycle_passed') is True
                            and report.get('model_unchanged') is True and report.get('root_unchanged') is True)
        for name in ('serial.txt', 'qemu-stderr.txt'):
            path = result / name
            if path.exists():
                report[name + '_sha256'] = prepare.sha(path.read_bytes())
        report['source_sha256'] = {p.name: prepare.sha(p.read_bytes()) for p in HERE.glob('*.py')}
        (result / 'validation.json').write_text(json.dumps(report, indent=2) + '\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', action='store_true')
    args = parser.parse_args()
    if not args.run:
        _, plan = prepared_delta(execution_admitted=False)
        print(json.dumps(plan, indent=2))
    else:
        outcome = run()
        print(json.dumps({k: outcome[k] for k in ['passed', 'boot_tested', 'result_path', 'errors', 'free_disk_after']}, indent=2))
        raise SystemExit(0 if outcome['passed'] else 1)
