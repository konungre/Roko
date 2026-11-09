"""Header and failure fixtures; no real model inference qualification."""
import os,struct,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integration'));sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'nix'))
from model_asset_probe import inspect
class ModelAssetTests(unittest.TestCase):
 def test_valid_header_never_attests_inference(self):
  with tempfile.TemporaryDirectory() as name:
   path=Path(name)/'fixture.gguf';path.write_bytes(struct.pack('<4sIQQ',b'GGUF',3,1,2))
   result=inspect(path,24);self.assertEqual(result['status'],'asset-observed-not-inference-qualified')
   for key in ('model_sha256_verified_in_guest','inference_qualified','system_ready','execution_authorized'):self.assertIs(result[key],False)
 def test_missing_symlink_fifo_wrong_size_and_bad_header(self):
  with tempfile.TemporaryDirectory() as name:
   root=Path(name);path=root/'fixture';path.write_bytes(struct.pack('<4sIQQ',b'GGUF',3,1,2));link=root/'link';link.symlink_to(path);fifo=root/'fifo';os.mkfifo(fifo)
   for item,size in [(root/'missing',24),(link,24),(fifo,24),(path,25)]:
    with self.subTest(item=item),self.assertRaises((ValueError,OSError)):inspect(item,size)
   for magic,version,tensors,metadata in [(b'BAD!',3,1,2),(b'GGUF',999,1,2),(b'GGUF',3,0,2),(b'GGUF',3,1,0)]:
    path.write_bytes(struct.pack('<4sIQQ',magic,version,tensors,metadata))
    with self.subTest(version=version,tensors=tensors),self.assertRaises(ValueError):inspect(path,24)
if __name__=='__main__':unittest.main()
