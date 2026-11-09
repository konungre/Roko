"""Storage handoff tests. Kernel/privileged writes are explicit doubles only."""
import ast,copy,hashlib,importlib.util,io,json,os,stat,sys,unittest
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch,Mock
ROOT=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'source'),str(ROOT/'capsule-bridge')]
import backing_identity as ident,work_fs,context_policy
spec=importlib.util.spec_from_file_location('bootstrap_producer',ROOT/'root-bootstrap/context_backing.py')
producer=importlib.util.module_from_spec(spec);spec.loader.exec_module(producer)
MOUNTS=b'''1 0 0:1 / / ro - overlay overlay ro,lowerdir=/lower,upperdir=/run/roko-live-cow/upper,workdir=/run/roko-live-cow/work
2 1 0:2 / /run/roko-guest-cognition ro,nodev,nosuid - tmpfs tmpfs rw,size=196608k
3 1 0:3 / /var/lib/roko/live-requests rw,nodev,nosuid,noexec - tmpfs tmpfs rw,size=131072k,mode=700,uid=1000,gid=1000
4 1 0:4 / /run/roko-live-cow rw,nodev,nosuid - tmpfs tmpfs rw,size=786432k,mode=700
'''
SOURCES={str(p):'a'*64 for p in ident.SOURCES}
def metadata(device='0:3',owner=1000,mode=0o700,inode=88):
 return dict(device=device,inode=inode,owner=owner,group=owner,mode=mode)
def view():return dict(boot_id='12345678-1234-1234-1234-123456789abc',mount_namespace='mnt:[27]',mounts=ident.mounts(MOUNTS),request_root=metadata(),request_total_bytes=ident.TOTAL)
def receipt():return dict(version=1,purpose='guest-storage-observation-only',public=view(),backing={str(p):metadata('0:4',0) for p in (ident.COW,ident.COW/'upper',ident.COW/'work')},sources=SOURCES,authorizes_actions=False,executed_actions=0)
def fs(free=ident.FLOOR,total=ident.TOTAL):return SimpleNamespace(f_blocks=total//4096,f_frsize=4096,f_bavail=free//4096)
def file_stat(**updates):
 d=dict(st_mode=stat.S_IFREG|0o440,st_uid=0,st_gid=1000,st_nlink=1,st_size=len(ident.canonical(receipt())),st_dev=7,st_ino=19,st_mtime_ns=1,st_ctime_ns=2);d.update(updates);return SimpleNamespace(**d)

class IdentityTests(unittest.TestCase):
 def test_valid_receipt_and_same_boot_endpoint_restart(self):
  self.assertEqual(ident.validate(receipt(),view(),SOURCES),receipt())
  self.assertEqual(ident.validate(copy.deepcopy(receipt()),view(),SOURCES),receipt())
 def test_source_pins_actual_and_shared_copies_equal(self):
  self.assertEqual((ROOT/'root-bootstrap/backing_identity.py').read_bytes(),(ROOT/'capsule-bridge/backing_identity.py').read_bytes())
  for path,digest in context_policy.BOOTSTRAP_SOURCES.items():self.assertEqual(hashlib.sha256((ROOT/'root-bootstrap'/Path(path).name).read_bytes()).hexdigest(),digest)
 def test_changed_boot_namespace_mount_and_request_identity_rejected(self):
  for change in (lambda v:v.update(boot_id='other'),lambda v:v.update(mount_namespace='mnt:[28]'),lambda v:v['mounts']['request'].update(id=99),lambda v:v['request_root'].update(inode=99),lambda v:v['request_root'].update(device='0:9'),lambda v:v.update(request_total_bytes=ident.TOTAL-4096)):
   with self.subTest(change=change):
    current=view();change(current)
    with self.assertRaises(ValueError):ident.validate(receipt(),current,SOURCES)
 def test_wrong_source_no_authority_and_schema_rejected(self):
  for change in (lambda r:r['sources'].update({str(ident.SOURCES[0]):'b'*64}),lambda r:r.update(authorizes_actions=True),lambda r:r.update(executed_actions=1),lambda r:r.update(version=True),lambda r:r.update(extra=1)):
   r=copy.deepcopy(receipt());change(r)
   with self.assertRaises(ValueError):ident.validate(r,view(),SOURCES)
 def test_backing_malformed_or_wrong_device_rejected(self):
  for field,value in [('device','0:9'),('inode',True),('owner',1000),('group',1000),('mode',0o777)]:
   r=receipt();r['backing'][str(ident.COW)][field]=value
   with self.assertRaises(ValueError):ident.validate(r,view(),SOURCES)
 def test_duplicate_nonfinite_or_oversize_json_rejected(self):
  for raw in (b'{"x":1,"x":2}',b'{"x":NaN}',b' '*8193):
   with self.assertRaises(ValueError):ident.decode(raw)
 def test_mount_policy_rejects_rw_root_and_missing_request_flags(self):
  for raw in (MOUNTS.replace(b'/ / ro -',b'/ / rw -'),MOUNTS.replace(b'rw,nodev,nosuid,noexec',b'rw,nodev,nosuid'),MOUNTS.replace(b'- tmpfs tmpfs rw,size=131072k',b'- ext4 disk rw,size=131072k')):
   with self.assertRaises(ValueError):ident.mounts(raw)
 def test_nested_mounts_rejected(self):
  for path in (str(ident.REQUEST/'native-work'),str(ident.RUNTIME/'hidden'),str(ident.COW/'upper'),str(ident.COW/'work')):
   raw=MOUNTS+f'5 1 8:1 / {path} rw - ext4 disk rw\n'.encode()
   with self.assertRaises(ValueError):ident.mounts(raw)
 def test_protected_root_submounts_rejected_even_if_readonly(self):
  for path in ('/usr/lib/roko-unprivileged','/opt/roko/desktop','/var/lib/roko','/usr'):
   for flags in ('rw','ro'):
    with self.assertRaises(ValueError):ident.mounts(MOUNTS+f'5 1 8:1 / {path} {flags} - ext4 disk rw\n'.encode())
 def test_mutable_allowlist_matches_existing_bootstrap(self):
  tree=ast.parse((ROOT/'root-bootstrap/prepare_session.py').read_text())
  value=next(ast.literal_eval(n.value) for n in tree.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='MUTABLE_TREES' for t in n.targets))
  self.assertEqual(ident.MUTABLE_TREES,value)
 def test_duplicate_fixed_mount_rejected(self):
  with self.assertRaises(ValueError):ident.mounts(MOUNTS+b'5 1 0:5 / /var/lib/roko/live-requests rw,nodev,nosuid,noexec - tmpfs tmpfs rw\n')
 def test_metadata_rejects_symlink_or_bad_owner(self):
  with patch.object(Path,'resolve',return_value=Path('/elsewhere')):
   with self.assertRaises(ValueError):ident.metadata(ident.REQUEST,1000,0o700)
  with patch.object(Path,'resolve',return_value=ident.REQUEST),patch.object(Path,'lstat',return_value=SimpleNamespace(st_mode=stat.S_IFDIR|0o700,st_uid=0,st_gid=0)):
   with self.assertRaises(ValueError):ident.metadata(ident.REQUEST,1000,0o700)
 def test_public_view_checks_capacity_and_device_without_private_backing(self):
  def proc(path,cap):return MOUNTS if path.endswith('mountinfo') else b'12345678-1234-1234-1234-123456789abc\n'
  with patch.object(ident,'small_proc',side_effect=proc),patch.object(ident.os,'readlink',return_value='mnt:[27]'),patch.object(ident,'metadata',return_value=metadata()) as meta,patch.object(ident.os,'statvfs',return_value=fs()):
   self.assertEqual(ident.public_view(),view());meta.assert_called_once_with(ident.REQUEST,1000,0o700)
  with patch.object(ident,'small_proc',side_effect=proc),patch.object(ident.os,'readlink',return_value='mnt:[27]'),patch.object(ident,'metadata',return_value=metadata('0:9')),patch.object(ident.os,'statvfs',return_value=fs()):
   with self.assertRaises(ValueError):ident.public_view()
 def receipt_read(self,before=None,after=None,pathinfo=None,raw=None):
  raw=ident.canonical(receipt()) if raw is None else raw;before=before or file_stat();after=after or before;pathinfo=pathinfo or before
  with ExitStack() as s:
   s.enter_context(patch.object(ident,'control_directory'));s.enter_context(patch.object(ident,'public_view',return_value=view()))
   opened=s.enter_context(patch.object(ident.os,'open',return_value=17));s.enter_context(patch.object(ident.os,'fstat',side_effect=[before,after]));s.enter_context(patch.object(ident.os,'read',return_value=raw));s.enter_context(patch.object(Path,'lstat',return_value=pathinfo));closed=s.enter_context(patch.object(ident.os,'close'))
   try:return ident.read_receipt(SOURCES)
   finally:closed.assert_called_once_with(17);self.assertTrue(opened.call_args.args[1]&os.O_NOFOLLOW)
 def test_receipt_descriptor_and_digest(self):self.assertEqual(self.receipt_read(),(receipt(),hashlib.sha256(ident.canonical(receipt())).hexdigest()))
 def test_receipt_wrong_mode_or_owner_rejected(self):
  for info in (file_stat(st_mode=stat.S_IFREG|0o640),file_stat(st_uid=1000),file_stat(st_nlink=2)):
   with self.assertRaises(ValueError):self.receipt_read(before=info)
 def test_receipt_replacement_or_metadata_change_rejected(self):
  for info in (file_stat(st_ino=20),file_stat(st_ctime_ns=3),file_stat(st_mode=stat.S_IFREG|0o640)):
   with self.assertRaises(ValueError):self.receipt_read(pathinfo=info)
 def test_receipt_missing_denies_without_write_or_fallback(self):
  with patch.object(ident,'control_directory'),patch.object(ident.os,'open',side_effect=FileNotFoundError),patch.object(ident,'public_view') as p:
   with self.assertRaises(FileNotFoundError):ident.read_receipt(SOURCES)
   p.assert_not_called()

class WorkTests(unittest.TestCase):
 def invoke(self,target,space=None,meta=None):
  with patch.object(ident,'read_receipt',return_value=(receipt(),'b'*64)),patch.object(work_fs.os,'statvfs',return_value=space or fs()) as f,patch.object(ident,'metadata',return_value=meta or metadata()) as m:
   result=target();return result,f.call_args,m.call_args
 def test_admit_existing_root_before_native_work_creation(self):
  r,f,m=self.invoke(work_fs.admit_request);self.assertEqual(f.args,(ident.REQUEST,));self.assertIsNone(m);self.assertEqual(r['free_bytes'],32*1024**2)
 def test_each_native_child_checks_work_exact_filesystem(self):
  r,f,m=self.invoke(work_fs.checked_free);self.assertEqual(f.args,(ident.WORK,));self.assertEqual(m.args,(ident.WORK,1000,0o700));self.assertEqual(r['statvfs_path'],str(ident.WORK))
 def test_low_floor_and_wrong_capacity_fail(self):
  for space in (fs(free=ident.FLOOR-4096),fs(total=ident.TOTAL-4096)):
   with self.assertRaises(ValueError):self.invoke(work_fs.admit_request,space)
 def test_wrong_work_device_fails(self):
  with self.assertRaises(ValueError):self.invoke(work_fs.checked_free,meta=metadata('0:9'))
 def test_receipt_failure_never_falls_back_to_statvfs(self):
  with patch.object(ident,'read_receipt',side_effect=PermissionError),patch.object(work_fs.os,'statvfs') as statfs:
   with self.assertRaises(PermissionError):work_fs.checked_free()
   statfs.assert_not_called()

class ProducerTests(unittest.TestCase):
 def producer_environment(self,stack):
  stack.enter_context(patch.object(producer,'__file__',str(ident.INSTALL/'context_backing.py')))
  stack.enter_context(patch.object(ident,'__file__',str(ident.INSTALL/'backing_identity.py')))
  stack.enter_context(patch.object(producer.os,'getpid',return_value=1));stack.enter_context(patch.object(producer.os,'getresuid',return_value=(0,0,0)));stack.enter_context(patch.object(producer.os,'getresgid',return_value=(0,0,0)))
  stack.enter_context(patch.object(ident,'control_directory'));stack.enter_context(patch.object(ident,'public_view',return_value=view()));stack.enter_context(patch.object(ident,'metadata',return_value=metadata('0:4',0)));stack.enter_context(patch.object(ident,'source_hashes',return_value=SOURCES));stack.enter_context(patch.object(ident,'read_receipt',return_value=(receipt(),'a'*64)))
  calls=[];opened=stack.enter_context(patch.object(producer.os,'open',side_effect=lambda *a:(calls.append(('open',*a)) or (31 if a[0]==ident.RECEIPT else 32))))
  stream=Mock();stream.__enter__=Mock(return_value=stream);stream.__exit__=Mock(return_value=False)
  stream.write.side_effect=lambda raw:calls.append(('write',len(raw)))
  stack.enter_context(patch.object(producer.os,'fdopen',return_value=stream))
  for name in ('fsync','fchown','fchmod','close'):
   stack.enter_context(patch.object(producer.os,name,side_effect=lambda *args,n=name:calls.append((n,*args))))
  return calls,opened
 def test_one_shot_publication_order_and_no_action_authority(self):
  with ExitStack() as s:
   calls,opened=self.producer_environment(s);self.assertEqual(producer.capture(),dict(status='recorded',authorizes_actions=False,executed_actions=0))
   self.assertEqual([c[0] for c in calls],['open','write','fsync','fchown','fchmod','fsync','close','open','fsync','close'])
   self.assertTrue(calls[0][2]&os.O_EXCL);self.assertTrue(calls[0][2]&os.O_NOFOLLOW);self.assertEqual(calls[3],('fchown',31,0,1000));self.assertEqual(calls[4],('fchmod',31,0o440))
 def test_existing_receipt_not_retried_or_removed(self):
  with ExitStack() as s:
   calls,opened=self.producer_environment(s);opened.side_effect=FileExistsError
   with patch.object(producer.os,'unlink') as remove:
    with self.assertRaises(FileExistsError):producer.capture()
    self.assertEqual(opened.call_count,1);remove.assert_not_called()
 def test_partial_publication_error_closes_and_never_retries(self):
  with ExitStack() as s:
   calls,opened=self.producer_environment(s)
   with patch.object(producer.os,'fchown',side_effect=OSError('explicit-double-failure')),patch.object(producer.os,'unlink') as remove:
    with self.assertRaises(OSError):producer.capture()
    self.assertEqual(opened.call_count,1);self.assertEqual(calls[-1],('close',31));remove.assert_not_called()
 def test_backing_permission_error_has_no_publication(self):
  with ExitStack() as s:
   _,opened=self.producer_environment(s)
   with patch.object(ident,'metadata',side_effect=PermissionError):
    with self.assertRaises(PermissionError):producer.capture()
    opened.assert_not_called()
 def test_changed_identity_before_publish_has_no_write(self):
  with ExitStack() as s:
   _,opened=self.producer_environment(s)
   with patch.object(ident,'public_view',side_effect=[view(),dict(view(),mount_namespace='mnt:[28]')]):
    with self.assertRaises(ValueError):producer.capture()
    opened.assert_not_called()
 def test_capture_rejects_non_pid1_before_side_effects(self):
  with patch.object(producer.os,'getpid',return_value=9),patch.object(ident,'control_directory') as c:
   with self.assertRaises(ValueError):producer.capture()
   c.assert_not_called()
 def test_bootstrap_default_off_hook_after_mount_validation_before_supervisor(self):
  tree=ast.parse((ROOT/'root-bootstrap/prepare_session.py').read_text());values={n.targets[0].id:n.value.value for n in tree.body if isinstance(n,ast.Assign) and len(n.targets)==1 and isinstance(n.targets[0],ast.Name) and isinstance(n.value,ast.Constant)}
  self.assertIs(values['NATIVE_CONTEXT_RECEIPT'],False)
  source=(ROOT/'root-bootstrap/prepare_session.py').read_text();self.assertLess(source.index('    verify_mounts(text)'),source.index('        context_backing.capture()'));self.assertLess(source.index('        context_backing.capture()'),source.index('runpy.run_path'))

if __name__=='__main__':
 with patch('subprocess.Popen',side_effect=AssertionError('Native forbidden')),patch('subprocess.run',side_effect=AssertionError('Native forbidden')),patch('os.execve',side_effect=AssertionError('Native forbidden')):unittest.main(verbosity=2)
