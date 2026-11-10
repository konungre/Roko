"""Packet error fixtures; no real store paths or native qualification."""
import copy,hashlib,json,unittest
from verify_profile_packet import verify
class PacketTests(unittest.TestCase):
 def fixture(self):
  path='/nix/store/'+'0'*32+'-fixture'
  receipt={'schema':'roko.native-profile-observation.v2','native':{'version':3,'elements':{'hello':{'storePaths':[path]}}},'source':'fixture-only','authorizes_actions':False}
  receipt['revision']=hashlib.sha256(json.dumps(receipt,sort_keys=True,separators=(',',':')).encode()).hexdigest()
  snapshot={'source':'fixture-only','packages':{'hello':path},'revision':receipt['revision']}
  return {'schema':'roko-profile-packet-v1','status':'unqualified','observation':receipt,'path_info':[{'path':path,'narHash':'sha256-'+'A'*43+'=','references':[]}],'snapshot':snapshot,'restart':{'origin':'restored-historical-checkpoint','backend_calls_at_restore':0,'restored_snapshot':copy.deepcopy(snapshot),'checkpoint_version':1,'refreshed_version':2,'refreshed_snapshot':copy.deepcopy(snapshot)}}
 def test_correspondence_is_not_trust(self):
  result=verify(self.fixture());self.assertTrue(result['packet_consistent'])
  for key in ('native_execution_verified','closure_verified','builder_identity_verified','image_ready','execution_authorized'):self.assertIs(result[key],False)
 def test_missing_closure_output_or_reference(self):
  for mode in ('output','reference'):
   p=self.fixture()
   if mode=='output':p['path_info'][0]['path']=p['path_info'][0]['path']+'-other'
   else:p['path_info'][0]['references']=['/nix/store/'+'1'*32+'-missing']
   with self.subTest(mode=mode),self.assertRaises(ValueError):verify(p)
 def test_receipt_or_snapshot_tamper(self):
  for field in ('observation','snapshot'):
   p=self.fixture()
   if field=='observation':p[field]['source']='changed'
   else:p[field]['packages']={}
   with self.subTest(field=field),self.assertRaises(ValueError):verify(p)
 def test_restore_is_historical_and_versioned(self):
  for field,value in [('origin','backend-observation'),('backend_calls_at_restore',True),('backend_calls_at_restore',1),('checkpoint_version',True),('refreshed_version',1),('restored_snapshot',{})]:
   p=self.fixture();p['restart'][field]=value
   with self.subTest(field=field,value=value),self.assertRaises(ValueError):verify(p)
 def test_reject_qualified_or_authoritative_claim(self):
  p=self.fixture();p['status']='qualified'
  with self.assertRaises(ValueError):verify(p)
  p=self.fixture();p['observation']['authorizes_actions']=True
  with self.assertRaises(ValueError):verify(p)
 def test_empty_or_noncanonical_observation(self):
  for elements in ({},{'hello':{'storePaths':['/workspace/fixture']}}):
   p=self.fixture();p['observation']['native']['elements']=elements
   body={k:v for k,v in p['observation'].items() if k!='revision'}
   p['observation']['revision']=hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':')).encode()).hexdigest()
   with self.assertRaises(ValueError):verify(p)
if __name__=='__main__':unittest.main()
