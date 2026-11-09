"""Fault injection with process doubles only; never starts a native worker."""
from contextlib import ExitStack
from pathlib import Path
from types import SimpleNamespace
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import gateway as g


class Finalization(unittest.TestCase):
    def process(self):
        return SimpleNamespace(pid=123,returncode=0,**{
            name:Mock(closed=False) for name in ('stdin','stdout','stderr')})

    def invoke(self, process, selector, primary=None, signal_effect=None, stop_effect=None):
        with ExitStack() as stack:
            stack.enter_context(patch.object(g.signal,'getsignal',return_value=g.signal.SIG_IGN))
            signals=stack.enter_context(patch.object(g.signal,'signal',side_effect=signal_effect))
            owned=stack.enter_context(patch.object(g,'stop_owned',side_effect=stop_effect,
                return_value={'reaped':True,'ownership':'owned-through-final-signal','returncode':0}))
            stack.enter_context(patch.object(g,'group_empty',return_value=True))
            result=g.finalize_native(process,selector,g.time.monotonic()+10,primary)
        return result, signals, owned

    def test_all_streams_and_handlers_attempted_despite_multiple_close_faults(self):
        p=self.process(); selector=Mock()
        selector.close.side_effect=OSError('selector broke')
        for name in ('stdin','stdout','stderr'):
            getattr(p,name).close.side_effect=OSError(name+' broke')
        (error,cleanup,empty,failures),signals,owned=self.invoke(p,selector)
        self.assertIsInstance(error,OSError)
        self.assertTrue(cleanup['reaped']); self.assertTrue(empty)
        self.assertEqual(len(failures),4)
        self.assertEqual(signals.call_count,6);owned.assert_called_once()
        for name in ('stdin','stdout','stderr'):getattr(p,name).close.assert_called_once()

    def test_primary_cancellation_preserved(self):
        cancel=KeyboardInterrupt('cancel');selector=Mock()
        selector.close.side_effect=OSError('close')
        (error,_,_,failures),_,_=self.invoke(self.process(),selector,cancel)
        self.assertIs(error,cancel);self.assertEqual(failures[0]['stage'],'selector-close')

    def test_child_cleanup_failure_does_not_skip_descriptor_cleanup(self):
        p=self.process();selector=Mock()
        (_,_,_,failures),signals,_=self.invoke(p,selector,stop_effect=OSError('reap'))
        selector.close.assert_called_once();p.stderr.close.assert_called_once()
        self.assertEqual(signals.call_count,6)
        self.assertEqual(failures[0]['stage'],'owned-child')

    def test_signal_restoration_failure_does_not_skip_later_handlers(self):
        calls=[]
        def signal(number,handler):
            calls.append((number,handler))
            if len(calls)==4:raise OSError('restore')
        (_,_,_,failures),_,_=self.invoke(self.process(),Mock(),signal_effect=signal)
        self.assertEqual(len(calls),6)
        self.assertTrue(failures[0]['stage'].startswith('signal-restore:'))

    def test_deferral_install_failure_still_cleans_child_and_restores_saved_handlers(self):
        calls=[]
        def signal(number,handler):
            calls.append((number,handler))
            if len(calls)==1:raise OSError('install')
        (_,cleanup,_,failures),_,owned=self.invoke(self.process(),Mock(),signal_effect=signal)
        self.assertTrue(cleanup['reaped']);owned.assert_called_once()
        self.assertEqual(len(calls),6)
        self.assertTrue(failures[0]['stage'].startswith('signal-defer:'))

    def test_cancel_during_cleanup_replayed_after_all_restores(self):
        events=[];handlers={}
        def signal(number,handler):
            if callable(handler):handlers[number]=handler
            else:events.append('restore')
        def stop(*args):
            handlers[g.signal.SIGINT](g.signal.SIGINT,None)
            events.append('stop')
            return {'reaped':True,'ownership':'owned-through-final-signal','returncode':0}
        def replay(saved,pending):
            events.append('replay')
            self.assertEqual(pending,[g.signal.SIGINT])
            raise KeyboardInterrupt('deferred')
        with patch.object(g,'replay_deferred_signal',side_effect=replay):
            (error,_,_,failures),_,_=self.invoke(self.process(),Mock(),
                ValueError('primary'),signal_effect=signal,stop_effect=stop)
        self.assertIsInstance(error,KeyboardInterrupt)
        self.assertEqual(events,['stop','restore','restore','restore','replay'])
        self.assertEqual(failures[-1]['stage'],'deferred-signal')

    def test_absent_process_still_finalizes_selector(self):
        selector=Mock()
        (error,cleanup,empty,failures),signals,owned=self.invoke(None,selector)
        self.assertIsNone(error);self.assertIsNone(cleanup)
        self.assertFalse(empty);self.assertEqual(failures,[])
        owned.assert_not_called();selector.close.assert_called_once()
        self.assertEqual(signals.call_count,6)

    def test_full_gateway_retains_observed_bytes_and_receipt_on_close_failure(self):
        self.check_gateway_receipt()

    def test_full_gateway_preserves_cancellation_and_finalization_evidence(self):
        self.check_gateway_receipt(KeyboardInterrupt('cancel after output'))

    def check_gateway_receipt(self, primary=None):
        p=self.process();selector=Mock()
        selector.get_map.side_effect=[True,False]
        selector.select.return_value=[(SimpleNamespace(fileobj=p.stdout,data='stdout'),1)]
        selector.close.side_effect=OSError('selector broke')
        p.stderr.close.side_effect=OSError('stderr broke')
        with ExitStack() as stack:
            for obj,name,value in [
                (g,'parse_request',{}),(g,'available',8*1024**3),
                (g,'verify_inputs',{'host_launcher_python':str(Path(sys.executable).resolve()),
                    'files':{str(Path(sys.executable).resolve()):{}}}),
                (g.shutil,'disk_usage',SimpleNamespace(free=8*1024**3)),
                (g.subprocess,'Popen',p),(g.selectors,'DefaultSelector',selector),
                (g.os,'set_blocking',None),(g.os,'read',b'actual double stdout'),
                (g,'observed_exit',True),(g,'group_empty',True),
                (g,'stop_owned',{'reaped':True,'ownership':'owned-through-final-signal','returncode':0}),
                (g.signal,'getsignal',g.signal.SIG_IGN),(g.signal,'signal',None)]:
                stack.enter_context(patch.object(obj,name,return_value=value))
            stack.enter_context(patch.object(g,'ROOT',Path(tempfile.gettempdir())))
            if primary is not None:
                stack.enter_context(patch.object(g,'observed_exit',side_effect=primary))
            validator=stack.enter_context(patch.object(g,'validate_completed'))
            kind='airis' if 'airis' in str(Path(g.__file__)) else 'metamo'
            with self.assertRaises(type(primary) if primary is not None else RuntimeError) as caught:
                g.run_native(kind,{},'test-only-not-admission',outer_deadline=g.time.monotonic()+10)
        receipt=caught.exception.receipt
        if primary is not None:
            self.assertIs(caught.exception,primary)
            self.assertEqual(receipt['execution_error'],'KeyboardInterrupt: cancel after output')
        self.assertEqual(receipt['stdout'],'actual double stdout')
        self.assertTrue(receipt['cleanup']['reaped'])
        self.assertEqual(receipt['returncode'],0)
        self.assertEqual(receipt['status'],'failed')
        self.assertEqual([x['stage'] for x in receipt['finalization_errors']],
            ['selector-close','stream-close:stderr'])
        self.assertFalse(receipt['authorizes_actions'])
        self.assertEqual(receipt['executed_actions'],0)
        validator.assert_not_called()


if __name__=='__main__':unittest.main()

