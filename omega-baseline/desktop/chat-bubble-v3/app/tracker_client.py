"""Parse the helper's narrow actual-compositor geometry protocol."""
import json
MAX_LINE=2048

def parse_report(raw):
    if len(raw)>MAX_LINE:raise ValueError('Oversized tracker report')
    item=json.loads(raw)
    if not isinstance(item,dict) or type(item.get('version')) is not int or item['version']!=1 or type(item.get('active')) is not bool:
        raise ValueError('Invalid tracker report')
    if not item['active']:
        reason=item.get('reason','unavailable')
        if not isinstance(reason,str) or len(reason)>100:raise ValueError('Invalid tracker reason')
        return {'active':False,'reason':reason}
    required=('x','y','width','height','observer_width','observer_height','id')
    if any(type(item.get(key)) is not int for key in required):raise ValueError('Noninteger geometry')
    if item.get('coordinate_space')!='observer':raise ValueError('Unknown coordinate space')
    if type(item.get('fullscreen')) is not bool or type(item.get('maximized')) is not bool:raise ValueError('Invalid state flags')
    if not (0<item['observer_width']<=16384 and 0<item['observer_height']<=16384):raise ValueError('Invalid observer dimensions')
    return {key:item[key] for key in (*required,'active','fullscreen','maximized')}
