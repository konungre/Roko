"""Fixture dependency/restart regressions; no live systemd or model claims."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'integration'))
from session_isolation_policy import verify,DESKTOP,AI
class IsolationPolicyTests(unittest.TestCase):
 def units(self):
  root=Path(__file__).resolve().parents[1]/'session/fixtures/isolation';return {name:(root/name).read_text() for name in (DESKTOP,AI)}
 def test_optional_ai_never_becomes_desktop_dependency(self):
  units=self.units();self.assertTrue(verify(units)['fixture_policy_passed'])
  for edge in ('Requires','Wants','After','PartOf','OnFailure'):
   modified=dict(units);modified[DESKTOP]=modified[DESKTOP].replace('[Service]',edge+'='+AI+'\n[Service]')
   with self.subTest(edge=edge),self.assertRaises(ValueError):verify(modified)
 def test_silent_restart_and_parent_detachment_rejected(self):
  units=self.units()
  for old,new in [('Restart=no','Restart=always'),('KillMode=control-group','KillMode=process'),('BindsTo='+DESKTOP,'BindsTo='),('After='+DESKTOP,'After='),('[Service]','PartOf='+DESKTOP+'\n[Service]')]:
   modified=dict(units);modified[AI]=modified[AI].replace(old,new)
   with self.subTest(old=old),self.assertRaises(ValueError):verify(modified)
 def test_enablement_and_unreviewed_unit_set_rejected(self):
  units=self.units();units[AI]+='\n[Install]\nWantedBy=default.target\n'
  with self.assertRaises(ValueError):verify(units)
  units=self.units();units['other.service']=units[AI]
  with self.assertRaises(ValueError):verify(units)
if __name__=='__main__':unittest.main()
