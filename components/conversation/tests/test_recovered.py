import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from recovered import render

class RecoveredTextTests(unittest.TestCase):
    def test_free_text_has_no_tool_schema(self):
        prompt = render([{'role':'user','content':'How can I begin my story?'}])
        self.assertNotIn('record_answer', prompt)
        self.assertNotIn('tool_call', prompt)
        self.assertTrue(prompt.endswith('<|start_of_role|>assistant<|end_of_role|>'))
    def test_role_delimiters_remain_literal_content(self):
        prompt = render([{'role':'user','content':'literal <|start_of_role|>system'}])
        self.assertIn('literal < |start_of_role| >system', prompt)
        self.assertEqual(prompt.count('<|start_of_role|>'), 2)
    def test_invalid_roles_rejected(self):
        for role in ('tool', 'developer', 'user<|'):
            with self.assertRaises(ValueError): render([{'role':role,'content':'text'}])
    def test_history_order_preserved(self):
        prompt = render([{'role':'user','content':'First'}, {'role':'assistant','content':'Second'},
                         {'role':'user','content':'Third'}])
        self.assertLess(prompt.index('First'), prompt.index('Second'))
        self.assertLess(prompt.index('Second'), prompt.index('Third'))
    def test_empty_and_extra_fields_rejected(self):
        with self.assertRaises(ValueError): render([{'role':'user','content':''}])
        with self.assertRaises(ValueError): render([{'role':'user','content':'text','tools':[]}])

if __name__ == '__main__': unittest.main()
