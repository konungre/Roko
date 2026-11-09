const assert = require('node:assert/strict');
const {motionAt,bodyWave,motionAnchor,sceneMotion,TASK_FLIGHTS,AUTO_FLIGHTS,MOTION_FPS} = require('./render-serpentine-demo.cjs');
assert.equal(MOTION_FPS,24);
for(const flights of [TASK_FLIGHTS,AUTO_FLIGHTS]) {
  for(const segment of flights) {
    for(const boundary of segment.slice(0,2)) {
      const before=motionAt(boundary-1e-5,flights),after=motionAt(boundary+1e-5,flights);
      assert(Math.abs(before.strength-after.strength)<.001);
      assert(Math.abs(before.lift-after.lift)<.001);
      for(const fn of [Math.sin,Math.cos])assert(Math.abs(fn(before.roll*Math.PI/180)-fn(after.roll*Math.PI/180))<.001);
      const a=motionAnchor(1000,400,320,boundary-1e-5,flights),b=motionAnchor(1000,400,320,boundary+1e-5,flights);
      assert(Math.hypot(a[0]-b[0],a[1]-b[1])<.01);
    }
    for(let t=segment[0];t<segment[1];t+=1/MOTION_FPS) {
      const q=sceneMotion(1000,400,320,t,flights);
      assert([q.x,q.y,q.width,q.m.roll,q.m.lift].every(Number.isFinite));
      assert(q.width>=320*.769 && q.width<=320);
    }
  }
}
// Distinct head/tail displacement proves deformation, not whole-sprite bobbing.
const differential=Array.from({length:60},(_,i)=>Math.abs(bodyWave(650,i/24,1)-bodyWave(160,i/24,1)));
assert(Math.max(...differential)>25);
assert.notEqual(bodyWave(650,4.5,1),bodyWave(650,4.7,1));
assert.equal(sceneMotion(1000,400,320,5.3,TASK_FLIGHTS).depth,'window');
assert.equal(sceneMotion(1000,400,300,10.25,AUTO_FLIGHTS).depth,'widget');
console.log('PASS: 24 fps, continuous transforms, independent body/tail wave and depth planes');
// Optional visual regression: generate ROKO_PREVIEW_DIR with the renderer first.
if(process.env.ROKO_PREVIEW_DIR)(async()=>{
  const sharp=require('sharp'),path=require('path');
  const crop=(file,left,top,width,height)=>sharp(path.join(process.env.ROKO_PREVIEW_DIR,file)).extract({left,top,width,height}).removeAlpha().raw().toBuffer();
  const editor=await crop('task-4.5.png',50,123,654,432);
  for(const t of ['5','5.5','6'])assert(editor.equals(await crop(`task-${t}.png`,50,123,654,432)),`Editor occlusion at ${t}`);
  const widget=await crop('auto-12.5.png',810,320,336,169);
  assert(widget.equals(await crop('auto-10.5.png',810,320,336,169)),'Widget occlusion');
  console.log('PASS: opaque editor/widget interiors are pixel-identical during behind-surface passes');
})().catch(error=>{console.error(error);process.exitCode=1;});
