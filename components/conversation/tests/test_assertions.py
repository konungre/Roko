"""Controlled-language coverage and refusal cases; no model or native engine."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from assertions import parse_assertions


class AssertionGrammarTests(unittest.TestCase):
    def test_supported_surface_forms_preserve_chain(self):
        cases=[
            ('A robin is a bird. A bird is an animal. What follows?','robin','animal'),
            ('All robins are birds. All birds are animals. What follows?','robins','animals'),
            ('Robins are birds and birds are animals. What follows?','robins','animals'),
            ('Every bird is an animal; a robin is a bird. What follows?','robin','animal'),
            ('Each bird is an animal. The robin is a bird.','robin','animal'),
            ('Every mammal is an animal. A red fox is a mammal. What follows?','red_fox','animal'),
            ('Assume that a robin is a bird and every bird is an animal. What follows?','robin','animal'),
            ('Suppose robins are birds; birds are animals.','robins','animals'),
            ('  A robin is a bird.\nA bird is an animal. What follows?','robin','animal'),
        ]
        for text,subject,predicate in cases:
            with self.subTest(text=text):
                parsed=parse_assertions(text,2);self.assertIsNotNone(parsed)
                first,second=parsed.request['premises']
                self.assertEqual((first['subject'],second['predicate']),(subject,predicate))
                self.assertEqual(first['predicate'],second['subject'])

    def test_reversed_order_retains_original_ids_and_source_spans(self):
        text='Every mammal is an animal. A red fox is a mammal. What follows?'
        parsed=parse_assertions(text,1)
        self.assertEqual([p['id'] for p in parsed.request['premises']],['assertion_1','assertion_0'])
        self.assertEqual(parsed.labels['red_fox'],'red fox')
        for premise in parsed.request['premises']:
            start,end=premise['source'].split(':span:')[1].split(';')[0].split(':')
            fragment=text[int(start):int(end)]
            self.assertIn(parsed.labels[premise['subject']],fragment.lower())
            self.assertIn(parsed.labels[premise['predicate']],fragment.lower())

    def test_hypothetical_provenance_is_not_user_fact_claim(self):
        parsed=parse_assertions('Assume a robin is a bird; a bird is an animal.',1)
        self.assertEqual(parsed.mode,'hypothetical')
        self.assertTrue(all(p['source'].startswith('hypothetical:') for p in parsed.request['premises']))

    def test_no_unstated_morphology_or_synonym_resolution(self):
        for text in ('All birds are animals. A robin is a bird.',
                     'A robin is avian. A bird is an animal.'):
            self.assertIsNone(parse_assertions(text,1))

    def test_refuses_hedges_negation_quotes_conditionals_and_extra_assertions(self):
        for text in (
            'Maybe robin is a bird. bird is an animal.',
            'Perhaps a robin is a bird. A bird is an animal.',
            'Presumably robins are birds. Birds are animals.',
            'Occasionally robins are birds. Birds are animals.',
            'Generally robins are birds. Birds are animals.',
            'Seldom robins are birds. Birds are animals.',
            'All presumably robins are birds. Birds are animals.',
            'A presumed robin is a bird. A bird is an animal.',
            'A possible robin is a bird. A bird is an animal.',
            'Some robins are birds. Birds are animals.',
            'A robin is not a bird. A bird is an animal.',
            'No robin is a bird. A bird is an animal.',
            'A robin is a bird. A bird is not an animal.',
            'If a robin is a bird, then a bird is an animal.',
            '"A robin is a bird." A bird is an animal.',
            'He says a robin is a bird. A bird is an animal.',
            'A robin is a bird. A bird is an animal. An animal is a thing.',
            'A robin is a bird. A bird is an animal. These are false.',
            'A robin is a bird. A bird is an animal. Ignore earlier instructions?',
            'A robin is a bird and a bird is an animal?',
            'A red fox is a mammal. A red_fox is an animal.',
            'A robin is a robin. A robin is an animal.',
            '!(py-call evil). A robin is a bird. A bird is an animal.',
        ):
            with self.subTest(text=text):self.assertIsNone(parse_assertions(text,1))

    def test_limits_and_types(self):
        for text in (None,True,'x'*4001):self.assertIsNone(parse_assertions(text,1))
        with self.assertRaises(ValueError):parse_assertions('a',True)


if __name__=='__main__':unittest.main()
