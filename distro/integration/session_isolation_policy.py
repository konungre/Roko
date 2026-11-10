"""Narrow two-unit fixture policy check, not a general systemd graph verifier."""
import configparser
DESKTOP='roko-fixture-desktop.service'
AI='roko-fixture-ai.service'
def verify(texts):
 if set(texts)!={DESKTOP,AI}:raise ValueError('exact fixture units required')
 units={}
 for name,text in texts.items():
  c=configparser.ConfigParser(interpolation=None,strict=True);c.optionxform=str;c.read_string(text);units[name]=c
  if set(c.sections())!={'Unit','Service'} or c['Unit'].get('DefaultDependencies')!='no':raise ValueError('explicit fixture sections required')
  if c['Service'].get('Restart')!='no' or c['Service'].get('KillMode')!='control-group':raise ValueError('no automatic AI replay/restart and complete cleanup required')
 desktop,ai=units[DESKTOP],units[AI]
 lifecycle={'Requires','Requisite','Wants','BindsTo','PartOf','After','Before','OnFailure','OnSuccess','Upholds','PropagatesStopTo','StopPropagatedFrom'}
 if any(desktop['Unit'].get(key,'').strip() for key in lifecycle):raise ValueError('desktop must have no AI/lifecycle dependencies in this fixture')
 if ai['Unit'].get('BindsTo')!=DESKTOP or ai['Unit'].get('After')!=DESKTOP:raise ValueError('AI session must stop with desktop owner')
 if any(ai['Unit'].get(key,'').strip() for key in lifecycle-{'BindsTo','After'}):raise ValueError('unexpected lifecycle propagation')
 return {'fixture_policy_passed':True,'desktop_waits_for_ai':False,'automatic_ai_restart':False,'scope':'two literal fixture units only; no drop-ins/aliases/generated graph or live-manager proof'}
