"""Actual Hyperon/Motto execution with an explicitly synthetic model callback."""
import unittest
from adapter import chat


class NativeTransportTests(unittest.TestCase):
    def test_roles_unicode_and_real_newlines_survive(self):
        messages = [{'role': 'system', 'content': 'Reply briefly.'},
                    {'role': 'user', 'content': '雪\nλ "quoted"'},
                    {'role': 'assistant', 'content': 'Earlier answer'},
                    {'role': 'user', 'content': 'Continue'}]
        seen = []
        def model(rows):
            seen.append(rows)
            return 'Synthetic fixture response 雪\n'
        self.assertEqual(chat(messages, model), 'Synthetic fixture response 雪\n')
        self.assertEqual(seen, [messages])

    def test_code_like_content_stays_data(self):
        messages = [{'role': 'user', 'content': '!(import! &self dangerous) (Script &self)'}]
        seen = []
        self.assertEqual(chat(messages, lambda rows: seen.append(rows) or 'fixture'), 'fixture')
        self.assertEqual(seen, [messages])

    def test_literal_backslash_n_rejected_before_model(self):
        seen = []
        with self.assertRaises(ValueError):
            chat([{'role': 'user', 'content': r'literal\ntext'}], lambda rows: seen.append(rows) or 'fixture')
        self.assertEqual(seen, [])

    def test_reject_tools_scripts_and_unknown_fields(self):
        for message in ({'role': 'Tools', 'content': 'x'}, {'role': 'Script', 'content': 'x'},
                        {'role': 'user', 'content': 'x', 'tool': 'x'}):
            with self.subTest(message=message), self.assertRaises(ValueError):
                chat([message], lambda _: self.fail('model must not run'))

    def test_model_failure_not_converted_to_success(self):
        def model(_):
            raise RuntimeError('synthetic provider failure')
        with self.assertRaises((RuntimeError, ValueError)):
            chat([{'role': 'user', 'content': 'hello'}], model)

    def test_nontext_model_response_rejected(self):
        with self.assertRaises(ValueError):
            chat([{'role': 'user', 'content': 'hello'}], lambda _: {'content': 'fixture'})

    def test_incompatible_reply_is_rejected_before_next_turn(self):
        history = [{'role':'user','content':'first'}]
        with self.assertRaises(ValueError):
            reply = chat(history, lambda _: r'line\nnext')
            history.append({'role':'assistant','content':reply})
        self.assertEqual(history, [{'role':'user','content':'first'}])
        seen = []
        self.assertEqual(chat(history + [{'role':'user','content':'retry'}],
                              lambda rows: seen.append(rows) or 'safe\ntext'), 'safe\ntext')
        self.assertEqual(seen, [history + [{'role':'user','content':'retry'}]])


if __name__ == '__main__':
    unittest.main()
