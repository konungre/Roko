"""Check self-reported qualification consistency, never native truth or authority."""
import hashlib,json,re
PATH=re.compile(r'/nix/store/[0-9abcdfghijklmnpqrsvwxyz]{32}-[A-Za-z0-9+._?=-]+')
def verify(packet):
 if not isinstance(packet,dict) or set(packet)!={'schema','status','observation','path_info','snapshot','restart'} or packet['schema']!='roko-profile-packet-v1' or packet['status']!='unqualified':raise ValueError('unqualified profile packet required')
 receipt=packet['observation']
 if not isinstance(receipt,dict) or receipt.get('schema')!='roko.native-profile-observation.v2' or receipt.get('authorizes_actions') is not False:raise ValueError('observation boundary')
 if not isinstance(receipt.get('source'),str) or not 1<=len(receipt['source'])<=4096:raise ValueError('observation source required')
 revision=receipt.get('revision');body={k:v for k,v in receipt.items() if k!='revision'}
 if revision!=hashlib.sha256(json.dumps(body,sort_keys=True,separators=(',',':')).encode()).hexdigest():raise ValueError('observation revision mismatch')
 native=receipt.get('native')
 if not isinstance(native,dict) or type(native.get('version')) is not int or native['version']!=3 or not isinstance(native.get('elements'),dict):raise ValueError('native schema')
 packages={}
 for name,element in native['elements'].items():
  if not isinstance(name,str) or not re.fullmatch('[a-z][a-z0-9-]{0,63}',name) or not isinstance(element,dict) or type(element.get('active',True)) is not bool:raise ValueError('native package')
  if not element.get('active',True):continue
  outputs=element.get('storePaths')
  if not isinstance(outputs,list) or len(outputs)!=1 or not isinstance(outputs[0],str) or not PATH.fullmatch(outputs[0]):raise ValueError('canonical single output required')
  packages[name]=outputs[0]
 if not packages:raise ValueError('populated qualification required')
 info=packet['path_info']
 if not isinstance(info,list) or not 1<=len(info)<=100000:raise ValueError('bounded path-info inventory required')
 inventory={}
 for row in info:
  if not isinstance(row,dict) or not isinstance(row.get('path'),str) or not PATH.fullmatch(row['path']) or row['path'] in inventory:raise ValueError('unique canonical closure paths required')
  if not isinstance(row.get('narHash'),str) or not re.fullmatch(r'sha256-[A-Za-z0-9+/]{43}=',row['narHash']) or not isinstance(row.get('references'),list):raise ValueError('closure metadata')
  inventory[row['path']]=row
 if not set(packages.values())<=inventory.keys():raise ValueError('missing package output')
 if any(not isinstance(ref,str) or ref not in inventory for row in info for ref in row['references']):raise ValueError('incomplete recursive inventory')
 expected={'packages':packages,'revision':revision,'source':receipt.get('source')}
 if packet['snapshot']!=expected:raise ValueError('snapshot differs from native receipt')
 restart=packet['restart']
 if not isinstance(restart,dict) or set(restart)!={'origin','backend_calls_at_restore','restored_snapshot','checkpoint_version','refreshed_version','refreshed_snapshot'}:raise ValueError('restart fields')
 if restart['origin']!='restored-historical-checkpoint' or type(restart['backend_calls_at_restore']) is not int or restart['backend_calls_at_restore']!=0:raise ValueError('historical restore required')
 if restart['restored_snapshot']!=expected or restart['refreshed_snapshot']!=expected:raise ValueError('restart snapshot mismatch')
 version=restart['checkpoint_version']
 if type(version) is not int or version<1 or type(restart['refreshed_version']) is not int or restart['refreshed_version']!=version+1:raise ValueError('checkpoint version progression')
 return {'packet_consistent':True,'native_execution_verified':False,'closure_verified':False,'builder_identity_verified':False,'image_ready':False,'execution_authorized':False,'scope':'self-reported packet consistency only'}
