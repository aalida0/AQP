"""Offline tests: never run a real Condor command."""
import importlib.util
import os
from pathlib import Path
import re
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('minimal', Path(__file__).resolve().parents[1] / 'scripts' / 'aqp_condor_patch.py')
minimal = importlib.util.module_from_spec(spec)
spec.loader.exec_module(minimal)

SOURCE = '''import sys
import os
import re
import subprocess
class ClusterManagmentError(RuntimeError): pass
def multiple_try(*args, **kwargs): return lambda f:f
def store_input(): return lambda f:f
class Cluster:
    def check_termination(self, job_id):
        args = self.retry_args[job_id]
        for name in args['required_output']:
            path = os.path.join(args['cwd'], name)
            if not os.path.isfile(path) or not os.stat(path).st_size:
                return 'wait'
        del self.retry_args[job_id]
        self.submitted_ids.remove(job_id)
        return 'done'
class CondorCluster(Cluster):
    jobstatus={'0':'U','1':'I','2':'R','4':'C','7':'S'}
    @multiple_try()
    def submit(self, prog, argument=[], cwd=None, stdout=None, stderr=None, log=None, required_output=[], nb_submit=0):
        text = """Executable = %(prog)s
                   %(requirement)s
                   queue 1"""
        if cwd is None: cwd=os.getcwd()
        if argument: argument='Arguments = %s' % ' '.join(argument)
        else: argument=''
        dico={'prog':prog, 'argument':argument,'requirement':''}
        a = misc.Popen(['condor_submit'], stdout=subprocess.PIPE, stdin=subprocess.PIPE)
        output, _ = a.communicate((text % dico).encode())
        pat = re.compile(r'submitted to cluster (\\d*)', re.MULTILINE)
        output = output.decode(errors='ignore')
        try: id=pat.search(output).groups()[0]
        except: raise ClusterManagmentError('fail to submit')
        self.submitted += 1
        self.submitted_ids.append(id)
        return id
    @store_input()
    @multiple_try()
    def submit2(self, prog, argument=[], cwd=None, stdout=None, stderr=None, log=None, input_files=[], output_files=[], required_output=[], nb_submit=0):
        if not input_files and not output_files:
            return self.submit(prog, argument, cwd, stdout, stderr, log, required_output=required_output, nb_submit=nb_submit)
        text = """Executable = %(prog)s
                   %(requirement)s
                   queue 1"""
        if cwd is None: cwd=os.getcwd()
        if argument: argument='Arguments = %s' % ' '.join(argument)
        else: argument=''
        dico={'prog':prog, 'argument':argument,'requirement':''}
        a = subprocess.Popen(['condor_submit'], stdout=subprocess.PIPE, stdin=subprocess.PIPE)
        output, _ = a.communicate((text % dico).encode())
        pat = re.compile(r'submitted to cluster (\\d*)', re.MULTILINE)
        output = output.decode(errors='ignore')
        try: id=pat.search(output).groups()[0]
        except: raise ClusterManagmentError('fail to submit')
        self.submitted += 1
        self.submitted_ids.append(id)
        return id
    @multiple_try(nb_try=10, sleep=10)
    def control_one_job(self, id): return ''
    @multiple_try(nb_try=10, sleep=10)
    def control(self, me_dir): return 0,0,0,0
'''

class Child:
    def __init__(self, payload, rc): self.payload, self.returncode=payload, rc
    def communicate(self, *args): return self.payload, b''

class Tests(unittest.TestCase):
    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup)
        self.base=Path(tmp.name)
        self.root=self.base/'guard';self.root.mkdir()
        self.cwd=self.base/'channel';self.cwd.mkdir()
        self.prog=self.cwd/'ajob1';self.prog.touch()
        (self.cwd/'G1').mkdir();(self.cwd/'G1'/'results.dat').write_text('ok')
        env=patch.dict(os.environ,{'AQP_CONDOR_GUARD_DIR':str(self.root)})
        env.start();self.addCleanup(env.stop)
        self.calls=[];self.responses=[(b'1 job(s) submitted to cluster 910001.\n',0)]
        def popen(args,**kwargs):
            self.calls.append(args)
            return Child(*self.responses[len(self.calls)-1])
        self.scheduler=lambda args,**kw: SimpleNamespace(returncode=0,stdout='',stderr='')
        p1=patch.object(subprocess,'run',side_effect=lambda args,**kw:self.scheduler(args,**kw))
        p1.start();self.addCleanup(p1.stop)
        p2=patch.object(subprocess,'Popen',side_effect=popen)
        p2.start();self.addCleanup(p2.stop)
        env={'misc':SimpleNamespace(Popen=popen)}
        code=minimal.patch_source(SOURCE)
        self.assertEqual(code.count('@multiple_try()'),0)
        exec(code,env)
        self.c=env['CondorCluster']()
        self.c.submitted=0;self.c.submitted_ids=[];self.c.retry_args={}

    def submit(self):
        return self.c.submit(str(self.prog),['1','F','0','1'],str(self.cwd),required_output=['G1/results.dat'])

    def terminal(self,exitcode=0):
        self.scheduler=lambda args,**kw:SimpleNamespace(returncode=0,stderr='',stdout=(
            '910001 0 4 %s\n'%exitcode if args[0]=='condor_history' else ''))

    def test_success_and_verified_completion(self):
        self.submit();self.terminal()
        self.assertEqual(self.c.control('.'),(0,0,1,0))
        self.assertFalse(self.c.submitted_ids)
        self.assertFalse(list(self.root.glob('*.intent')))

    def test_duplicate_blocked(self):
        self.submit()
        with self.assertRaisesRegex(RuntimeError,'Existing ajob1'):
            self.submit()
        self.assertEqual(len(self.calls),1)

    def test_ambiguous_ack_never_retries(self):
        self.responses=[(b'Submitting job(s).\n',0)]
        with self.assertRaises(RuntimeError):self.submit()
        self.assertEqual(len(self.calls),1)
        with self.assertRaisesRegex(RuntimeError,'Existing ajob1'):self.submit()

    def test_failure_exit(self):
        self.responses=[(b'1 job(s) submitted to cluster 910001.\n',8)]
        with self.assertRaisesRegex(RuntimeError,'nonzero exit'):self.submit()
        self.assertFalse(self.c.submitted_ids)

    def test_guard_required(self):
        del os.environ['AQP_CONDOR_GUARD_DIR']
        with self.assertRaisesRegex(RuntimeError,'Set existing AQP_CONDOR_GUARD_DIR'):self.submit()
        self.assertFalse(self.calls)

    def test_empty_history_blocks(self):
        self.submit()
        with self.assertRaisesRegex(RuntimeError,'No verified successful Condor history'):self.c.control('.')
        self.assertEqual(self.c.submitted_ids,['910001'])

    def test_history_error_blocks(self):
        self.submit();self.terminal(3)
        with self.assertRaisesRegex(RuntimeError,'No verified successful Condor history'):self.c.control('.')

    def test_visible_c_counts_outstanding(self):
        self.submit()
        self.scheduler=lambda args,**kw:SimpleNamespace(returncode=0,stderr='',stdout='910001 0 4\n')
        self.assertEqual(self.c.control('.'),(0,1,0,0))
        self.assertEqual(self.c.control_one_job('910001'),'R')

    def test_missing_output_blocks_without_retry(self):
        self.submit();self.terminal();(self.cwd/'G1'/'results.dat').unlink()
        with self.assertRaisesRegex(RuntimeError,'Missing MadGraph output'):self.c.control('.')
        self.assertEqual(self.c.submitted_ids,['910001'])
        self.assertEqual(len(list(self.root.glob('*.intent'))),1)

    def test_bad_status_blocks(self):
        self.submit()
        self.scheduler=lambda args,**kw:SimpleNamespace(returncode=0,stderr='',stdout='910001 0 5\n')
        with self.assertRaisesRegex(RuntimeError,'Malformed or unexpected'):self.c.control('.')

    def test_bad_query_return_blocks(self):
        self.submit()
        self.scheduler=lambda args,**kw:SimpleNamespace(returncode=17,stderr='error',stdout='')
        with self.assertRaisesRegex(RuntimeError,'Condor query error'):self.c.control('.')

    def test_submit2_delegation(self):
        self.c.submit2(str(self.prog), ['1','F','0','1'],str(self.cwd),required_output=['G1/results.dat'])
        self.assertEqual(len(self.calls),1)

    def test_reusing_worker_after_verified_completion_is_allowed(self):
        self.submit();self.terminal()
        self.c.control('.')
        self.responses.append((b'1 job(s) submitted to cluster 910002.\n',0))
        self.assertEqual(self.submit(), '910002')
        self.assertEqual(len(self.calls),2)

    def test_candidate_repatch_fails(self):
        with self.assertRaises(ValueError):minimal.patch_source(minimal.patch_source(SOURCE))

if __name__=='__main__':unittest.main()
