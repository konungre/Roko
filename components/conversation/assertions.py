"""Finite, provenance-preserving affirmative inheritance grammar.

This is a controlled-language parser, not general semantic extraction. It never
stems nouns, resolves synonyms/pronouns, treats negation as a category, or accepts
instructions/conditionals as facts. Engine identifiers are separate from labels.
"""
from dataclasses import dataclass
import hashlib
import re
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from components.nars_hyperon.source.contract import make_premise

NOUN=r'[a-z][a-z0-9_]*(?:[ -][a-z][a-z0-9_]*){0,2}'
ARTICLE=r'(?:(?:a|an|the|all|every|each)\s+)?'
CLAUSE=ARTICLE+r'(?P<subject>'+NOUN+r')\s+(?:is|are)\s+'+ARTICLE+r'(?P<predicate>'+NOUN+r')'
FIRST=re.compile(CLAUSE+r'(?=\s*(?:[.;]|,?\s+and\b))',re.I)
SECOND=re.compile(CLAUSE+r'(?=\s*(?:\.|$))',re.I)
SEPARATOR=re.compile(r'(?:\s*[.;]\s*|\s*,?\s+and\s+)',re.I)
QUESTION=re.compile(r'(?:what|which|how|does|do|is|are|can)\b[^.!?\n]{0,300}\?',re.I)
RESERVED=frozenset(('not no never some most few many may might could would should if then unless either or neither and is are a an all every each any the these those they we you i it this that '
    'maybe perhaps probably possibly allegedly reportedly apparently supposedly sometimes usually often rarely suspected possible likely unlikely non').split())


@dataclass(frozen=True)
class ParsedAssertions:
    request: dict
    labels: dict
    mode: str


def parse_assertions(text,revision):
    if type(text) is not str or not 0<len(text)<=4000:return None
    if type(revision) is not int or not 1<=revision<=2**53-1:raise ValueError('Revision domain')
    prefix=re.match(r'\s*(?:(Assume|Suppose)(?:\s+that)?\s+)?',text,re.I)
    mode='hypothetical' if prefix.group(1) else 'user-assertion'
    first=FIRST.match(text,prefix.end())
    if first is None:return None
    separator=SEPARATOR.match(text,first.end())
    if separator is None:return None
    second=SECOND.match(text,separator.end())
    if second is None:return None
    suffix=text[second.end():].strip()
    if suffix.startswith('.'):suffix=suffix[1:].strip()
    if suffix and QUESTION.fullmatch(suffix) is None:return None
    labels={};rows=[]
    for index,match in enumerate((first,second)):
        terms=[]
        for name in ('subject','predicate'):
            label=' '.join(match.group(name).lower().split())
            words=re.split(r'[ _-]+',label)
            if any(word in RESERVED for word in words):return None
            identifier=re.sub(r'[ -]','_',label)
            if not re.fullmatch(r'[a-z][a-z0-9_]{0,31}',identifier):return None
            if identifier in labels and labels[identifier]!=label:return None
            labels[identifier]=label;terms.append(identifier)
        rows.append((index,match.start(),match.end(),*terms))
    if rows[0][4]==rows[1][3]:ordered=rows
    elif rows[1][4]==rows[0][3]:ordered=rows[::-1]
    else:return None
    if len({ordered[0][3],ordered[0][4],ordered[1][4]})!=3:return None
    digest=hashlib.sha256(text.encode()).hexdigest()
    premises=[make_premise('assertion_'+str(index),
        f'{mode}:sha256:{digest}:span:{start}:{end};policy:f=1,c=0.9',subject,predicate,1000,900)
        for index,start,end,subject,predicate in ordered]
    request={'version':1,'operation':'nal1-chain','task_id':'turn_'+str(revision),
             'revision':revision,'premises':premises}
    return ParsedAssertions(request,labels,mode)


def extract(text,revision):
    parsed=parse_assertions(text,revision)
    return None if parsed is None else parsed.request
