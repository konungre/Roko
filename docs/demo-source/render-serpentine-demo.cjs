// Illustrative desktop simulations only. No app, model or external actions run.
const fs = require('fs');
const path = require('path');
const sharp = require('sharp');
const root = path.resolve(__dirname, '../..');
const out = path.join(root, 'docs/media');
const data = name => fs.readFileSync(path.join(__dirname, 'assets', name)).toString('base64');
const plate = data('desktop-plate.png');
const poses = data('roko-poses.png');
const esc = s => String(s).replace(/[&<>]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
const text = (x,y,s,size=22,color='#e8e9df',weight=400,mono=false) => `<text xml:space="preserve" x="${x}" y="${y}" font-family="${mono?'DejaVu Sans Mono':'DejaVu Sans'},sans-serif" font-size="${size}" fill="${color}" font-weight="${weight}">${esc(s)}</text>`;
const rect = (x,y,w,h,fill='#1c2427',r=0,stroke='none') => `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${r}" fill="${fill}" stroke="${stroke}"/>`;
const line = (x,y,x2,y2,color='#3f4949') => `<path d="M${x} ${y}L${x2} ${y2}" stroke="${color}"/>`;
const ease = u => (u=Math.max(0,Math.min(1,u)),u*u*(3-2*u));
function position(t,points){let i=points.findIndex((p,i)=>i<points.length-1&&t>=p[0]&&t<points[i+1][0]);if(i<0)i=points.length-2;let a=points[i],b=points[i+1],u=ease((t-a[0])/(b[0]-a[0]));return [a[1]+(b[1]-a[1])*u,a[2]+(b[2]-a[2])*u];}
function shell(){return `<svg xmlns="http://www.w3.org/2000/svg" width="1672" height="941"><defs><linearGradient id="glass" x2="0" y2="1"><stop stop-color="#283134"/><stop offset="1" stop-color="#151d20"/></linearGradient></defs><image href="data:image/png;base64,${plate}" width="1672" height="941"/>${rect(43,114,505,29,'#10261d',14,'#6b6742')}${text(58,134,'SIMULATED INTERACTION · NOT RUNTIME FOOTAGE',15,'#dec581',600)}`;}
function roko(x,y,pose=0,width=290){let sx=(pose%2)*768,sy=Math.floor(pose/2)*512;return `<svg x="${x}" y="${y}" width="${width}" height="${width*2/3}" viewBox="${sx} ${sy} 768 512"><image href="data:image/png;base64,${poses}" width="1536" height="1024"/></svg>`;}
// A continuous piecewise-affine ribbon rig: head stays steady while a wave
// travels independently through the torso and tail. Bands share tangents so
// they join without the staircase edges of translated sprite strips.
const MOTION_FPS = 24;
let flightData = ''; // Prepared once at output-scale resolution, not per band.
const TASK_FLIGHTS = [[3.8,6.8,0,2,true,'window'],[9,11,2,2,false],[13,15,2,2,true]];
const AUTO_FLIGHTS = [[1.6,3.8,3,2,true],[6,8,2,2,false],[9,11.5,2,2,true,'widget']];
function motionAt(t, flights) {
  const segment = flights.find(a => t >= a[0] && t <= a[1]);
  const idleRoll=3*Math.sin(2*Math.PI*t/3.2),idleLift=-2*Math.sin(2*Math.PI*t/2.4);
  if (!segment) return {active:false, roll:idleRoll, lift:idleLift, strength:.16, blend:1};
  const u=(t-segment[0])/(segment[1]-segment[0]);
  const envelope=Math.sin(Math.PI*u)**2;
  const strength=.16+.84*envelope;
  return {active:true,u,segment,strength,
    roll:idleRoll+(segment[4]?360*ease(u):18*Math.sin(2*Math.PI*u)*envelope),
    lift:idleLift-24*envelope,
    blend:1};
}
function bodyWave(pixelX,t,strength) {
  const u=pixelX/768;
  const tail=Math.max(0,(u-.22)/.78);
  const amplitude=3+43*tail**1.5;
  return strength*amplitude*Math.sin(2*Math.PI*(1.35*u-1.15*t));
}
function sceneMotion(x,y,width,t,flights) {
  const m=motionAt(t,flights);
  const depth=m.active?m.segment[5]:null;
  const recession=m.active?(m.strength-.16)/.84:0;
  const scale=1-(depth ? .23 : .07)*recession;
  return {m,depth,x:x+(depth==='window'?-340*recession:0)+width*(1-scale)/2,
    y:y+width/3*(1-scale),width:width*scale};
}
function motionAnchor(x,y,width,t,flights) {
  const q=sceneMotion(x,y,width,t,flights),m=q.m,a=m.roll*Math.PI/180;
  const dx=-.23*q.width,dy=-.13*q.width;
  return [q.x+q.width/2+dx*Math.cos(a)-dy*Math.sin(a),
    q.y+q.width/3+dx*Math.sin(a)+dy*Math.cos(a)+m.lift];
}
let maskCounter=0;
function behindSurface(markup,depth) {
  if(!depth)return markup;
  const maskId='depth-occlusion-'+(++maskCounter);
  const surface=depth==='window'?[64,161,879,585]:[1075,421,460,238];
  return `<defs><mask id="${maskId}" maskUnits="userSpaceOnUse" x="0" y="0" width="1672" height="941"><rect width="1672" height="941" fill="white"/>${rect(...surface,'black',13)}</mask></defs><g mask="url(#${maskId})">${markup}</g>`;
}
function headHidden(x,y,width,t,flights) {
  const q=sceneMotion(x,y,width,t,flights),a=motionAnchor(x,y,width,t,flights);
  if(!q.depth)return false;
  const b=q.depth==='window'?[64,161,943,746]:[1075,421,1535,659];
  return a[0]>=b[0]&&a[0]<=b[2]&&a[1]>=b[1]&&a[1]<=b[3];
}
function animatedRoko(x,y,pose,width,t,flights) {
  const q=sceneMotion(x,y,width,t,flights),m=q.m;
  x=q.x;y=q.y;width=q.width;
  // Use the same articulated flight rig even while hovering: no ghosted
  // crossfades or abrupt swaps between unrelated drawn poses.
  let body=`<defs><image id="ribbon-source" href="data:image/png;base64,${flightData}" width="768" height="512"/></defs>`;
  const step=12;
  for(let p=0;p<768;p+=step){
    const dy=bodyWave(p,t,m.strength);
    const slope=(bodyWave(p+.5,t,m.strength)-bodyWave(p-.5,t,m.strength));
    body+=`<g transform="matrix(1 ${slope} 0 1 0 ${dy-p*slope})"><svg x="${p}" y="0" width="${step+1}" height="512" viewBox="${p} 0 ${step+1} 512"><use href="#ribbon-source"/></svg></g>`;
  }
  const painted=`<g opacity="1" transform="translate(${x} ${y+m.lift}) scale(${width/768}) rotate(${m.roll} 384 256)">${body}</g>`;
  return behindSurface(painted,q.depth);
}
function bubble(x,y,lines,ax,ay,width=450){let h=lines.length*31+38;return `<path d="M${x+80} ${y+h-1}Q${x+90} ${y+h+25} ${ax} ${ay}L${x+120} ${y+h-1}" fill="#14271f" stroke="#c9a855" stroke-width="2"/><path d="M${x+30} ${y}Q${x+width*.4} ${y-9} ${x+width*.7} ${y}Q${x+width} ${y-4} ${x+width} ${y+35}L${x+width} ${y+h-28}Q${x+width} ${y+h+10} ${x+width-35} ${y+h}Q${x+width*.5} ${y+h-7} ${x+30} ${y+h}Q${x} ${y+h+1} ${x} ${y+h-30}L${x} ${y+30}Q${x} ${y} ${x+30} ${y}Z" fill="#14271f" stroke="#c9a855" stroke-width="2"/>${lines.map((s,i)=>text(x+25,y+35+i*31,s,22,'#f0e7c9')).join('')}`;}
function pointer(x,y,click=false){return `<g transform="translate(${x},${y})">${click?'<circle r="23" fill="none" stroke="#f4d58b" stroke-width="3"/>':''}<path d="M0 0L24 21L14 23L20 34L14 37L8 27L0 35Z" fill="#fffbe4" stroke="#17271e" stroke-width="2"/></g>`;}
function ide(fixed=false,tests=false,review=false){let s=rect(64,161,879,585,'#1b2328',13,'#74766b')+rect(65,162,877,52,'url(#glass)',12)+text(92,195,'▣  Code · roko-demo',21,'#e4e7df',600)+text(808,195,'−   □   ×',20)+rect(65,214,877,30,'#222b2f')+text(84,235,'File   Edit   Selection   View   Run   Terminal   Help',15,'#c3cbc7');
s+=rect(65,244,48,466,'#1c2529')+text(79,281,'▣',24,'#d8c37f')+text(78,333,'⌕',28,'#a5b3ae')+text(79,388,'⑂',24,'#a5b3ae')+text(78,445,'▷',24,'#a5b3ae');
s+=rect(113,244,200,466,'#20292e')+text(130,273,'EXPLORER',13,'#9caeaa',600)+text(129,311,'⌄ ROKO-DEMO',15,'#d6ded7')+rect(114,325,198,32,'#35413e')+text(145,347,'▸ example.py',15,'#dcc480')+text(145,384,'▸ test_example.py',14,'#b0c1b8')+text(145,421,'▸ README.md',14,'#b0c1b8');
s+=rect(313,244,630,36,'#182126')+rect(313,244,175,36,'#29343a')+text(330,268,'example.py    ×',15,'#e5cf8d')+text(506,268,review?'Review changes':'test_example.py',14,'#90a39b')+text(336,308,'roko-demo  ›  example.py  ›  average',13,'#819b8d');
const code=fixed||review?['def average(values):','    if not values:','        return None','    return sum(values) / len(values)']:['def average(values):','    return sum(values) / len(values)'];
code.forEach((c,i)=>{let y=351+i*37;if((fixed||review)&&(i===1||i===2))s+=rect(315,y-26,626,35,'#254636');s+=text(329,y,String(i+1),17,'#81958b',400,true)+text(366,y,c,17,i===0?'#d8ca93':'#c8dfd1',400,true);});
s+=line(313,520,942,520)+rect(313,521,629,189,'#162126')+text(333,548,'TERMINAL    PROBLEMS    OUTPUT',13,'#b7c6bf',600)+text(333,581,'$ pytest -q',17,'#c6dabf',400,true)+text(333,615,tests?'2 passed in 0.04s':fixed?'Running tests…':'Ready to run local example tests',16,tests?'#a9dca4':'#8ea89a',400,true)+text(333,655,tests?'✓ Empty list handled safely':'Demo project · illustrative output',14,'#a9bfa9');
s+=rect(65,710,877,35,'#2b3b36')+text(83,734,'main*   ◉ 0   △ 0',14,'#e1dcc4')+text(685,734,'Python 3.12   UTF-8',14,'#c4d4c7');
if(review)s+=rect(715,469,198,43,'#d8ba6c',9)+text(738,497,'Apply patch',18,'#182820',600);return s;}
function browser(kind,phase=0){let s=rect(64,161,879,585,'#f0f1e9',13,'#74766b')+rect(65,162,877,48,'url(#glass)',12)+rect(83,172,282,38,'#34413f',10)+text(101,197,kind==='shopping'?'Keyboard finder   ×':'Local AI reading list   ×',16)+text(385,196,'+',24)+text(809,195,'−   □   ×',20)+rect(65,210,877,51,'#273432')+text(83,243,'‹   ›   ↻',27,'#c4d0c6')+rect(201,220,681,31,'#152420',14)+text(217,242,'⌑  https://example.org/'+(kind==='shopping'?'keyboards':'local-ai'),16,'#c7d6c8')+text(904,243,'⋮',24);
s+=rect(65,261,877,36,'#dde4d8')+text(85,286,'★  Reading list     Documentation     Saved notes',15,'#3a5846')+text(98,341,'FIELDNOTES',17,'#42624b',700)+text(710,341,'Guides   About',16,'#526d58');
if(kind==='shopping'){s+=text(98,389,'Find your quiet keyboard',31,'#223e2b',700)+text(98,422,'Compact keyboards · Budget under $100',18,'#58735e');[['Linen Mini','$79','Quiet switches','Compact · wired'],['Moss Wireless','$89','Low-profile keys','Wireless · 75%'],['Slate Studio','$95','Soft tactile feel','Compact · USB-C']].forEach((a,i)=>{let x=98+i*270;s+=rect(x,450,245,215,'#fffdf5',12,'#c7d0be')+rect(x+21,472,200,54,'#37463d',9);for(let r=0;r<3;r++)for(let c=0;c<10;c++)s+=rect(x+29+c*18,480+r*13,14,9,'#849381',2);s+=text(x+15,555,a[0],19,'#263f2c',600)+text(x+15,584,a[1],24,'#2c5941',700)+text(x+15,611,a[2],14,'#5c735b')+text(x+15,633,a[3],13,'#5c735b');});s+=text(99,706,'Illustrative products & prices · No purchase placed',14,'#58735e');}
else{s+=text(98,389,'A practical guide to local AI',31,'#223e2b',700)+text(98,422,'Example article · fictional source material for this demo',16,'#58735e');[['01','Compare the trade-offs','Model size, latency and resource requirements.'],['02','Keep evidence close','Link each useful claim to its original source.'],['03','Build a reading list','Save sources to revisit and check later.']].forEach((a,i)=>{let y=457+i*68;s+=text(100,y+22,a[0],18,'#9a8b51',700)+text(146,y+19,a[1],21,'#2d4d35',600)+text(146,y+45,a[2],16,'#56715b');});s+=text(98,708,phase>=3?'★ Saved to Roko’s local reading list':'Example content · no research claims verified',15,'#58735e');if(phase>=2)s+=rect(684,304,228,45,'#e3dfbc',10,'#b4a66c')+text(702,333,phase>=3?'★ Saved locally':'★ Save this source',16,'#3b4d32',600);}
return s;}
function savedCard(x=1075,y=421){return rect(x,y,460,238,'#1c2927',16,'#b0a36c')+text(x+25,y+38,'▤  Roko’s reading list',23,'#e4d5a8',600)+line(x+20,y+58,x+440,y+58)+text(x+25,y+96,'Local AI · starter guide',21,'#eceddf')+text(x+25,y+128,'example.org/local-ai',17,'#9eb9a4')+text(x+25,y+173,'Saved with source link',17,'#c9d3bd')+text(x+25,y+211,'Private draft · no external sharing',15,'#9cb49e');}
function demo(t){let review=t>=6.8&&t<9,fix=t>=9,tests=t>=12;let s=shell()+ide(fix,tests,review);let [x,y]=position(t,[[0,1110,440],[3.8,1110,440],[6.8,955,320],[7.3,818,320],[9,818,320],[11,696,574],[13,696,574],[15,1015,595],[16,1015,595]]);let flying=(t>3.8&&t<6.8)||(t>9&&t<11)||(t>13&&t<15);let pose=flying?1:review||fix?2:0;let lines=t<3.8?['Ask Roko to fix this edge case.']:review?['I found the empty-list case.','Review this small guard?']:tests?['Tests passed.','Your change is ready.']:fix?['I’ll check the local tests.']:['Let me look at the function.'];
let bx=t<3.8?1060:Math.min(1125,x+170),by=t<3.8?180:y-160;const anchor=motionAnchor(x,y,320,t,TASK_FLIGHTS);if(!headHidden(x,y,320,t,TASK_FLIGHTS))s+=bubble(bx,by,lines,anchor[0],anchor[1],450);if(t<3.8){let q='Fix the empty-list crash.';s+=rect(1082,280,419,56,'#11241d',24,'#b99e60')+text(1103,315,t<.8?'Ask Roko…':q.slice(0,Math.floor((t-.8)*10)),20,'#e3dec8')+text(1461,316,'➤',24,'#dabe73');}
s+=animatedRoko(x,y,pose,320,t,TASK_FLIGHTS);if(review)s+=`<circle cx="811" cy="489" r="37" fill="none" stroke="#dfc577" stroke-width="2"/>`;if(t>10.9&&t<12)s+=rect(322,560,325,41,'none',7,'#d5ba68');let [cx,cy]=position(t,[[0,1230,315],[3.8,1480,309],[5.2,1480,309],[8.8,815,491],[9.2,815,491],[11,1240,745],[16,1240,745]]);s+=pointer(cx,cy,Math.abs(t-9)<.15)+text(72,794,t<3.8?'1 / Ask for a fix':review?'2 / Roko flies to the code and proposes an edit':tests?'4 / Roko checks the result in the terminal':fix?'3 / Apply, then verify the change':'2 / Roko glides behind the editor, then emerges',22,'#e0d6b3');return s+'</svg>';}
function autonomous(t){let phase=t<3?0:t<6?1:t<9?2:3;let s=shell()+browser('research',phase);let [x,y]=position(t,[[0,622,680],[1.6,622,680],[3.8,820,390],[6,820,390],[8,746,271],[9,746,271],[11.5,1135,665],[14,1135,665]]);let flying=(t>1.6&&t<3.8)||(t>6&&t<8)||(t>9&&t<11.5);let lines=[['My goal: build a useful','local AI reading list.'],['I’m checking this example','and keeping its source link.'],['I’ll save this guide','to my private reading list.'],['Saved with its source.','Ready for a future conversation.']][phase];const anchor=motionAnchor(x,y,300,t,AUTO_FLIGHTS);if(!headHidden(x,y,300,t,AUTO_FLIGHTS))s+=bubble(1040,183,lines,anchor[0],anchor[1],485);if(phase>=3)s+=savedCard();if(phase===2)s+=`<circle cx="794" cy="327" r="38" fill="none" stroke="#d5b05f" stroke-width="3"/>`;if(t>9&&t<11.5){let [cx,cy]=position(t,[[9,786,331],[11.5,1120,451]]);s+=behindSurface(rect(cx,cy,174,46,'#e3dcac',9,'#a99954')+text(cx+12,cy+29,'★ Source link',17,'#304731',600),'widget');}
s+=animatedRoko(x,y,flying?1:phase===0?3:2,300,t,AUTO_FLIGHTS)+text(72,794,['Self-chosen goal / Build a reading list','Browse / Inspect a source in the browser','Organize / Carry the source into a local note','Complete / Save the source, not just a summary'][phase],21,'#e0d6b3')+text(1065,129,'SIMULATED AUTONOMY · NO EXTERNAL ACTION',14,'#cbb980');return s+'</svg>';}
function still(kind){if(kind==='coding'){let s=shell()+ide(false,false,true);s+=bubble(1080,200,['This guard handles an empty list.','Review it before applying.'],970,447,475)+roko(824,392,2,355)+`<circle cx="812" cy="489" r="38" fill="none" stroke="#dbbf75" stroke-width="3"/>`+text(73,795,'Coding concept / Roko reaches into the IDE to highlight a proposed patch',21,'#e0d6b3');return s+'</svg>';}
if(kind==='shopping'){let s=shell()+browser('shopping');s+=bubble(1055,191,['This option fits your budget.','Want to compare the details?'],862,485,505)+roko(785,433,2,350)+rect(633,445,252,223,'none',12,'#b7a05d')+text(73,795,'Shopping concept / Roko highlights an option inside the browser',21,'#e0d6b3');return s+'</svg>';}
let s=shell()+browser('research',3)+savedCard(1155,425)+bubble(1060,185,['I’ll keep the source attached','to your research note.'],920,415,490)+roko(795,365,1,330)+rect(956,475,190,48,'#e3dcac',10,'#a99954')+text(972,506,'★ Source link',18,'#304731',600)+text(73,795,'Research concept / Roko carries a source from the browser to a note',21,'#e0d6b3');return s+'</svg>';}
function fluidStill(kind) {
  if(kind==='research') {
    let frame=autonomous(11.1);
    return frame.replace('Complete / Save the source, not just a summary','Research concept / Roko carries a source behind the note');
  }
  const t=6.3,x=955,y=kind==='coding'?365:435,width=355;
  const anchor=motionAnchor(x,y,width,t,TASK_FLIGHTS);
  let frame=shell()+(kind==='coding'?ide(false,false,true):browser('shopping'));
  frame+=bubble(1070,191,kind==='coding'?['I’ll come around the editor.','Let’s review this small guard.']:['This option fits your budget.','Let’s compare the details.'],anchor[0],anchor[1],490);
  frame+=animatedRoko(x,y,1,width,t,TASK_FLIGHTS);
  if(kind==='shopping')frame+=rect(633,445,252,223,'none',12,'#b7a05d');
  frame+=text(73,795,kind==='coding'?'Coding concept / Roko emerges around the editor to review a change':'Shopping concept / Roko glides around the browser to compare options',21,'#e0d6b3');
  return frame+'</svg>';
}
async function save(svg,file,width=1672){await sharp(Buffer.from(svg)).resize({width}).png().toFile(file);}
if(require.main===module)(async()=>{
  flightData=(await sharp(Buffer.from(poses,'base64')).extract({left:768,top:0,width:768,height:512}).resize(384,256).png().toBuffer()).toString('base64');
  if(process.env.ROKO_STATIC_ONLY==='1'){for(const kind of ['coding','shopping','research'])await save(fluidStill(kind),path.join(out,`roko-${kind}-concept-v3.png`));return;}
  const preview=process.env.ROKO_PREVIEW_DIR;
  if(preview){fs.mkdirSync(preview,{recursive:true});for(const t of [4.1,4.5,5,5.5,6,6.5,6.8,7.3,13.5,14])await save(demo(t),path.join(preview,`task-${t}.png`),1254);for(const t of [9.5,10,10.5,11,11.5,12.5])await save(autonomous(t),path.join(preview,`auto-${t}.png`),1254);return;}
  if(process.env.ROKO_FRAME_DIR){fs.mkdirSync(process.env.ROKO_FRAME_DIR,{recursive:true});for(let i=0;i<16*MOTION_FPS;i++)await save(demo(i/MOTION_FPS),path.join(process.env.ROKO_FRAME_DIR,String(i).padStart(4,'0')+'.png'),1254);}
  if(process.env.ROKO_AUTO_DIR){fs.mkdirSync(process.env.ROKO_AUTO_DIR,{recursive:true});for(let i=0;i<14*MOTION_FPS;i++)await save(autonomous(i/MOTION_FPS),path.join(process.env.ROKO_AUTO_DIR,String(i).padStart(4,'0')+'.png'),1254);}
})();
module.exports={motionAt,bodyWave,motionAnchor,sceneMotion,headHidden,TASK_FLIGHTS,AUTO_FLIGHTS,MOTION_FPS};
