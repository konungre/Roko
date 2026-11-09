import importlib.util
import json
from pathlib import Path
import sys
import unittest

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
STAGE=ROOT/'build-src/granite-portable-stage/source-v2/opt/roko'
sys.path[:0]=[str(HERE),str(STAGE/'adapters'),str(STAGE/'vendor/guest-python'),str(STAGE/'vendor/PeTTa/repos/Omega/src')]
import runtime_select
import granite_guest
import providers


class SelectionTests(unittest.TestCase):
    def good(self):
        return dict(architecture='x86_64',all_allowed_cpus=True,tested_cpus=1,**{k:True for k in runtime_select.REQUIRED})
    def test_complete_cpu_and_loader_admission_required(self):
        self.assertEqual(runtime_select.choose(self.good(),True),'avx2')
        self.assertEqual(runtime_select.choose(self.good(),False),'generic')
        for key in runtime_select.REQUIRED:
            proof=self.good();proof[key]=False
            self.assertEqual(runtime_select.choose(proof,True),'generic')
        for proof in (None,{},[],dict(self.good(),tested_cpus=0),dict(self.good(),all_allowed_cpus=False)):
            self.assertEqual(runtime_select.choose(proof,True),'generic')
    def test_invalid_types_cannot_claim_cpu_support(self):
        for value in (1,'true',None):
            proof=self.good();proof['os_avx_state']=value
            self.assertEqual(runtime_select.choose(proof,True),'generic')
    def test_loader_is_explicit_no_environment_path(self):
        cmd=runtime_select.loader_command(Path('/opt/roko'))
        self.assertEqual(cmd[0],runtime_select.LOADER)
        self.assertIn('--inhibit-cache',cmd)
        self.assertEqual(cmd[-1],'/opt/roko/runtime/granite/avx2/infer')
        self.assertEqual(cmd[cmd.index('--library-path')+1],'/opt/roko/runtime/granite/avx2/lib:/usr/lib/x86_64-linux-gnu')
    def test_missing_or_unrecognized_loader_output_rejected(self):
        for output in ('libllama.so.0 => not found','unexpected loader line'):
            with self.assertRaises(ValueError):runtime_select.resolved_paths(output)
        self.assertEqual(runtime_select.resolved_paths('libc.so.6 => /usr/lib/x86_64-linux-gnu/libc.so.6 (0x123)\n'),{'libc.so.6':'/usr/lib/x86_64-linux-gnu/libc.so.6'})
    def test_loader_interpreter_alias_and_duplicate_are_explicit(self):
        value=runtime_select.resolved_paths('/lib64/ld-linux-x86-64.so.2 => /copied/ld-linux-x86-64.so.2 (0x1)\n')
        self.assertEqual(value,{'ld-linux-x86-64.so.2':'/copied/ld-linux-x86-64.so.2'})
        with self.assertRaises(ValueError):
            runtime_select.resolved_paths('libc.so.6 => /one/libc.so.6 (0x1)\nlibc.so.6 => /two/libc.so.6 (0x2)\n')
    def test_staged_variant_has_no_native_admission(self):
        p=granite_guest.GraniteGuestProvider(STAGE)
        with self.assertRaisesRegex(ValueError,'awaits binary and loader admission'):p.start()
        self.assertFalse(p.ready)
    def test_actual_omega_contract_and_inert_parser(self):
        tool=providers.LLMTool().with_name('record_answer').with_description('inert').add_parameter(providers.LLMToolParameter().with_name('text'))
        request=providers.LLMRequest().with_messages([providers.llmRequestMessage('user','ready')]).with_max_tokens(64).with_tools([tool])
        response=granite_guest.parse_tool('<tool_call>{"name":"record_answer","arguments":{"text":"ready"}}</tool_call>',request)
        response=providers._validate_response(request,response)
        self.assertFalse(response.is_error())
        self.assertEqual(providers.llmResponseToSExpr(response),'((granite-guest-proposal-0 (record_answer "ready")))')


if __name__=='__main__':unittest.main()
