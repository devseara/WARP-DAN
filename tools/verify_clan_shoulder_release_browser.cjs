const fs=require('node:fs'),path=require('node:path');
const {chromium}=require('C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const workArg=process.argv.slice(2).find(a=>a.startsWith('--work='));
const work=workArg?workArg.slice(7):'shoulder-motion-v2';
if(!/^[a-z0-9-]+$/.test(work))throw Error('Invalid review directory');
const out=path.resolve(__dirname,'../Assets/ClanBodySkins',work);
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
 try{
  const page=await browser.newPage({viewport:{width:1560,height:1050}}),errors=[];page.on('pageerror',e=>errors.push(String(e)));page.on('requestfailed',r=>errors.push(r.url()));
  await page.goto('http://127.0.0.1:8808/'+work+'/review.html',{waitUntil:'networkidle'});await page.waitForFunction(()=>document.body.dataset.ready==='true');
  const onlyJobs=process.argv.slice(2).filter(a=>!a.startsWith('--work='));const jobs=(await page.locator('#job option').evaluateAll(n=>n.map(v=>v.value))).filter(j=>!onlyJobs.length||onlyJobs.includes(j));let loaded=0;const loops=[];
  for(const job of jobs)for(const sex of ['male','female']){
   await page.selectOption('#job',job);await page.selectOption('#sex',sex);
   // Load every action's first and last frames; the Python proof covers every
   // intermediate frame and checks reconstructed review bytes against the SPR.
   const frames=await page.evaluate(async()=>{playing=false;schedule();let checked=0;for(let a=0;a<104;a++){document.getElementById('group').value=Math.floor(a/8);document.getElementById('dir').value=a%8;for(const f of new Set([0,current().actions[a].frames.length-1])){frame=f;await draw();checked++;if(views.some(v=>!v.raw||v.raw.length===0))throw Error('Empty review canvas')}}return checked});loaded+=frames;
   await page.selectOption('#group','1');
   for(let direction=0;direction<8;direction++){
    await page.selectOption('#dir',String(direction));await page.evaluate(async()=>{frame=0;for(const r of current().actions[action()].frames){await rendered(r,0,true);await rendered(r,1,true);await rendered(r,2,true)}await draw()});
    const count=await page.evaluate(()=>new Promise((resolve,reject)=>{const seen=new Set(),obs=new MutationObserver(()=>{seen.add(document.getElementById('slider').value);if(seen.size===8){clearTimeout(timeout);obs.disconnect();playing=false;schedule();resolve(seen.size)}});const timeout=setTimeout(()=>{obs.disconnect();playing=false;schedule();reject(Error('Walk did not play all frames'))},6000);obs.observe(document.getElementById('status'),{childList:true,subtree:true});playing=true;schedule()}));loops.push({job,sex,direction,frames:count});
   }
   console.log(JSON.stringify({job,sex,action_boundary_frames:frames,walks:8}));
  }
  for(const [job,sex,a,f] of [['acolyte','male',16,0],['acolyte','female',10,2],['mage','male',34,2],['mage','female',12,0],['swordman','female',32,0],['archer','male',46,2],['thief','male',98,1],['acolyte','male',13,6],['acolyte','female',15,2],['archer','male',15,6],['archer','female',13,5],['archer','male',12,5],['archer','female',12,2],['archer','female',10,6]]){
   if(onlyJobs.length&&!onlyJobs.includes(job))continue;await page.selectOption('#job',job);await page.selectOption('#sex',sex);await page.selectOption('#group',String(Math.floor(a/8)));await page.selectOption('#dir',String(a%8));await page.selectOption('#crop','neck');await page.selectOption('#zoom','2');await page.evaluate(async f=>{frame=f;await draw()},f);
   await page.screenshot({path:path.join(out,'review',`browser-${job}-${sex}-a${a}-f${f}.png`),fullPage:true});
   await page.locator('#heads').uncheck();await page.evaluate(async()=>{await draw()});await page.locator('#heads').check();await page.selectOption('#bg','magenta');await page.evaluate(async()=>{await draw()});await page.selectOption('#bg','slate');
  }
  if(errors.length)throw Error(errors.join('\n'));
  fs.writeFileSync(path.join(out,onlyJobs.length?'browser-refresh-verification.json':'browser-verification.json'),JSON.stringify({status:'passed',review_data_sha256:require('node:crypto').createHash('sha256').update(fs.readFileSync(path.join(out,'review-data.json'))).digest('hex'),browser:await browser.version(),pairs:jobs.length*2,actions:jobs.length*2*104,action_boundary_frames_loaded:loaded,walking_cycles:loops.length,loops,errors,visual_acceptance:false,live_client_validation:false},null,2));console.log(JSON.stringify({status:'passed',action_boundary_frames_loaded:loaded,walking_cycles:loops.length}));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
