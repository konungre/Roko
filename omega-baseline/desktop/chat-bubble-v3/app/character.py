"""Local playful presentation state. Care is optional and never decays."""
import time
class Character:
    def __init__(self):
        self.resting=False
        self.response_until=0
        self.response=0
        self.treats=0
        self.play_sessions=0
    def care(self, action, now=None):
        now=time.monotonic() if now is None else now
        if action=='rest':
            self.resting=not self.resting
            return 'Resting quietly. Wake me whenever you like.' if self.resting else 'Ready when you are.'
        self.resting=False
        if action=='treat':
            self.treats+=1;self.response=5;message='A little treat! Thank you.'
        elif action=='play':
            self.play_sessions+=1;self.response=5;message='Let’s play! You can drag me around the desktop.'
        elif action=='greet':
            self.response=2;message='Hello! What shall we work on?'
        else:raise ValueError('Unknown interaction')
        self.response_until=now+2.5
        return message
    def frame(self,tick,state='idle',walking=False,now=None):
        now=time.monotonic() if now is None else now
        if self.resting:return 3
        if now<self.response_until:return self.response
        if walking:return 6+tick%2
        if state in ('thinking','review','waiting'):return 4
        if state=='complete':return 2
        return (0,0,0,0,1,0)[tick%6]

def rectangle(index):
    if type(index) is not int or not 0<=index<8:raise ValueError('Invalid pose')
    return index%4*192,index//4*208,192,208

def format_report(report):
    lines=[]
    if report.get('error'):lines.append('Could not complete this request:\n'+str(report['error']))
    proposal=report.get('proposal')
    if isinstance(proposal,dict):
        args=proposal.get('arguments',{})
        if 'text' in args:lines.append('Proposed answer:\n'+str(args['text']))
        elif 'invoice' in args and 'total' in args:lines.append('Proposed invoice: '+str(args['invoice'])+'\nTotal: '+str(args['total']))
    if report.get('checked'):
        lines.append('Independent check: '+('passed' if report.get('accepted') is True else 'did not pass'))
    else:lines.append('No verified answer yet.')
    if report.get('state_stale'):lines.append('Saved progress needs reloading; do not assume the last write failed.')
    if report.get('task_id'):lines.append('Task: '+str(report['task_id']))
    lines.append('No external actions were executed. Task remains available for review.')
    return '\n\n'.join(lines)
