"""Provisional OS-state representation checks; no package-manager execution."""
import copy
import unittest
from contract import PHASES,atoms,validate,check_rows,digest,encoded


def packet():
    body={'fixture':True};sha=digest(body)
    return {'schema':'roko.os-state.claims.v0','backend':'synthetic','machine':'m','boot':'b',
        'producer':'test','sequence':0,'evidence':[{'sha256':sha,'body':body}],
        'facts':[{'phase':'desired','subject':'x','generation':'g','value':'!(danger) " \\n',
                  'evidence_sha256':sha}]}


class ClaimsTests(unittest.TestCase):
    def test_unknown_phase_rejected(self):
        data=packet();data['facts'][0]['phase']='authorized'
        with self.assertRaises(ValueError):validate(data)

    def test_evidence_bytes_must_match_digest(self):
        data=packet();data['evidence'][0]['body']['fixture']=False
        with self.assertRaises(ValueError):validate(data)

    def test_missing_evidence_and_duplicate_fact_rejected(self):
        data=packet();data['evidence']=[]
        with self.assertRaises(ValueError):validate(data)
        data=packet();data['facts'].append(copy.deepcopy(data['facts'][0]))
        with self.assertRaises(ValueError):validate(data)

    def test_data_cannot_introduce_executable_expressions(self):
        source='\n'.join(atoms(packet()))
        self.assertNotIn('!(danger)',source)
        self.assertNotIn('authorized',source)
        self.assertIn('unverified',source)

    def test_desired_cannot_satisfy_activated_query(self):
        data=packet();row=data['facts'][0]
        native=[['RokoStateRow','desired',encoded(row['subject']),encoded(row['generation']),
                 encoded(row['value']),'sha_'+row['evidence_sha256'],'unverified']]
        self.assertEqual(check_rows(data,'desired',native),data['facts'])
        self.assertEqual(check_rows(data,'activated',[]),[])
        with self.assertRaises(ValueError):check_rows(data,'activated',native)


if __name__=='__main__':unittest.main()
