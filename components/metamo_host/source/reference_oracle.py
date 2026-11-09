"""Independent Python TEST ORACLE only. Never a native fallback or bridge import."""
import math

def score(state, candidate):
    g,m=state['goals'],state['modulators'];c=candidate['correlations']
    ind=1/(1+math.exp(-(g[0]-0.5)*6));trans=1/(1+math.exp(-(g[1]-0.5)*6))
    rows=((2,(3,),ind),(3,(1,),trans),(4,(2,),trans),(6,(4,5),ind),(7,(0,2),(ind+trans)/2),(5,(2,3),(ind+trans)/2))
    base=sum(g[idx]*sum(m[j] for j in mods)/len(mods)*(0.5+0.5*drive)*c[idx] for idx,mods,drive in rows)
    conflict=c[3]*c[6];penalty=math.exp(abs(conflict)*3) if conflict < -0.2 else 0
    risk=0.5*g[0]*(m[4]+m[5])/2*candidate['risk']
    alignment=max(0,sum(c[j] for j in (3,4,5))/3)
    shift=sum(min(1,max(0,round(candidate['delta_goals'][j]*10,8))) for j in (3,4,5))/3
    growth=0.5*g[1]*(m[1]+m[2])/2*(0.7*alignment+0.3*shift)
    return base-risk-penalty+growth
