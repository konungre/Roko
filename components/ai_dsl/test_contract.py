"""Independent structural and capability checker tests; not native execution."""
import unittest
from contract import check,validate


def compose(g,f):return [['.',g],f]
def proof(program):return [':',program,['->','speech2text-en.Audio','text-emotions.Output']]
SHORTCUT=compose('text-emotions.MkOutput',compose('speech2text-en.Text.text','speech2text-en.s2t'))
REAL=compose('text-emotions.recognize',compose('text-emotions.MkInput',compose('speech2text-en.Text.text','speech2text-en.s2t')))


class ContractTests(unittest.TestCase):
    def test_type_correct_shortcut_does_not_establish_emotion_capability(self):
        result=check({'version':1,'goal':'speech_emotion','depth':4},[proof(SHORTCUT),proof(REAL)])
        self.assertEqual(len(result['accepted']),1);self.assertEqual(len(result['rejected']),1)
        self.assertEqual(result['rejected'][0]['missing'],['text-emotions.recognize'])
        self.assertEqual(result['accepted'][0]['pipeline'],['speech2text-en.s2t','speech2text-en.Text.text','text-emotions.MkInput','text-emotions.recognize'])
        self.assertEqual(result['executed_services'],0);self.assertIsNone(result['service_results'])

    def test_depth_bound_independently_checked(self):
        with self.assertRaises(ValueError):check({'version':1,'goal':'speech_emotion','depth':3},[proof(REAL)])

    def test_mistyped_composition_rejected(self):
        with self.assertRaises(ValueError):
            check({'version':1,'goal':'speech_emotion','depth':4},[proof(compose('text-emotions.recognize','speech2text-en.s2t'))])

    def test_unknown_service_rejected(self):
        with self.assertRaises(ValueError):check({'version':1,'goal':'speech_emotion','depth':4},[proof('shell')])

    def test_request_is_closed_and_bounded(self):
        for row in [{'version':1,'goal':'speech_emotion','depth':5},
                    {'version':1,'goal':'!(import! &self evil)','depth':0},
                    {'version':1,'goal':'speech_emotion','depth':True}]:
            with self.assertRaises(ValueError):validate(row)


if __name__=='__main__':unittest.main()
