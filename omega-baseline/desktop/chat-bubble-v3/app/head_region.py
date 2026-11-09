"""Conservative local alpha cells; no screen/global mapping or occlusion oracle."""
import math

def head_region(alpha, width, height, origin, head_roi, active_rect, canvas,
                *, enabled=False, perched=False, visible=False, settled=False,
                mapping_verified=False, scene_exposure_verified=False):
    """Return horizontal 1px rectangles, only fully opaque cells outside active.

    scene_exposure_verified is an explicit controlled-scene precondition, NOT
    inferred from active geometry. Current tracker cannot establish it generally.
    Alpha must be for the exact currently drawn pose, no stale crossfade mask.
    """
    if not all((enabled,perched,visible,settled,mapping_verified,scene_exposure_verified)):
        return ()
    if type(width) is not int or type(height) is not int or not 0<width<=192 or not 0<height<=208:
        raise ValueError('sprite bounds')
    if len(alpha)!=width*height:raise ValueError('alpha length')
    if any(type(v) is not int or not 0<=v<=255 for v in alpha):raise ValueError('alpha')
    values=(*origin,*head_roi,*active_rect,*canvas)
    if any(type(v) not in (int,float) or not math.isfinite(v) for v in values):raise ValueError('geometry')
    ox,oy=origin;hx,hy,hw,hh=head_roi;ax,ay,aw,ah=active_rect;cw,ch=canvas
    if any(v!=int(v) for v in (*head_roi,*active_rect,*canvas)):raise ValueError('integer geometry')
    if not (0<=hx<hx+hw<=width and 0<=hy<hy+hh<=height and aw>0 and ah>0 and 0<cw<=16384 and 0<ch<=16384):raise ValueError('geometry bounds')
    # Fractional filtered painting can blend neighboring alpha. Disable until
    # a separately verified conservative transformed mask exists.
    if ox!=int(ox) or oy!=int(oy):return ()
    ox,oy=int(ox),int(oy);result=[]
    for y in range(int(hy),int(hy+hh)):
        start=None
        for x in range(int(hx),int(hx+hw)+1):
            px,py=ox+x,oy+y
            opaque=x<hx+hw and alpha[y*width+x]==255
            outside=px+1<=ax or px>=ax+aw or py+1<=ay or py>=ay+ah
            eligible=opaque and outside and 0<=px<cw and 0<=py<ch
            if eligible and start is None:start=px
            if not eligible and start is not None:
                result.append((start,py,px-start,1));start=None
    if len(result)>192*208:raise ValueError('region budget')
    return tuple(result)
