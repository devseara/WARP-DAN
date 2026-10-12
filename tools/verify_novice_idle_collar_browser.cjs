/* Exercise the Novice reviewer in a separate headless Edge process. */
const fs=require('node:fs');
const path=require('node:path');
const {chromium}=require('C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const work=path.resolve(__dirname,'../Assets/HDNovice/idle-collar-v5');
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
 try{
  const page=await browser.newPage({viewport:{width:1500,height:1150}}),errors=[];
  page.on('pageerror',e=>errors.push(String(e)));
  page.on('requestfailed',r=>errors.push(r.url()+': '+r.failure()?.errorText));
  page.on('response',r=>{if(r.status()>=400)errors.push(r.status()+' '+r.url())});
  await page.goto('http://127.0.0.1:8770/idle-collar-v5/full-action-review.html',{waitUntil:'networkidle'});
  const coverage=await page.evaluate(async()=>{
   let sets=0;
   for(let ai=0;ai<104;ai++){
    document.querySelector('#group').value=Math.floor(ai/8);document.querySelector('#direction').value=ai%8;
    for(let fi=0;fi<data.male[ai].frames.length;fi++){
     frame=fi;await render();
     for(const canvas of document.querySelectorAll('canvas')){
      const pixels=canvas.getContext('2d').getImageData(0,0,336,352).data;let any=false;
      for(let i=3;i<pixels.length;i+=4)if(pixels[i]){any=true;break;}
      if(!any)throw new Error('Blank '+ai+'/'+fi+'/'+canvas.dataset.sex+'/'+canvas.dataset.kind);
     }sets++;
    }
   }return {actions:104,frame_sets:sets,canvas_renders:sets*6};
  });
  const sequences=[0,1,2,6,7,8,9,10,11,12,13,14,15].map(action=>({sex:'male',action})),loops=[];
  for(const row of sequences){
   await page.evaluate(async ai=>{playing=false;document.querySelector('#group').value=Math.floor(ai/8);document.querySelector('#direction').value=ai%8;frame=0;await render();},row.action);
   const seen=await page.evaluate(()=>new Promise((resolve,reject)=>{
    const frames=new Set(),count=data.male[action()].frames.length,start=performance.now();playing=true;last=performance.now();
    const timer=setInterval(()=>{frames.add(frame);if(frames.size===count){clearInterval(timer);playing=false;resolve([...frames].sort((a,b)=>a-b));}else if(performance.now()-start>5000){clearInterval(timer);playing=false;reject(Error('Playback did not traverse action '+action()));}},8);
   }));loops.push({sex:row.sex,action:row.action,frames_seen:seen});
  }
  for(const [name,group,fi,bg] of [['idle-front',0,0,'slate'],['idle-head2',0,1,'slate'],['idle-alpha',0,0,'magenta']]){
   await page.evaluate(async ({group,fi,bg})=>{playing=false;document.querySelector('#group').value=group;document.querySelector('#direction').value=0;document.querySelector('#background').value=bg;frame=fi;await render();},{group,fi,bg});
   await page.screenshot({path:path.join(work,`browser-${name}.png`),fullPage:true});
  }
  await page.check('#onion');await page.selectOption('#zoom','4');await page.click('#previous');await page.click('#next');
  await page.goto('http://127.0.0.1:8770/idle-collar-v5/pixel-review.html',{waitUntil:'networkidle'});
  await page.waitForFunction(()=>[...document.images].every(im=>im.complete&&im.naturalWidth>0));
  await page.goto('http://127.0.0.1:8770/idle-collar-v5/idle-walk-review.html',{waitUntil:'networkidle'});
  const transitions=await page.evaluate(async()=>{let sets=0;for(let d=0;d<8;d++){document.querySelector('#direction').value=d;for(let h=0;h<3;h++){document.querySelector('#head').value=h;for(let p=0;p<data[d+8].frames.length;p++){phase=p;await draw();sets++;}}}return {directions:8,idle_head_poses:3,frame_sets:sets};});
  await page.evaluate(async()=>{document.querySelector('#direction').value=0;document.querySelector('#head').value=0;phase=0;await draw();});
  await page.screenshot({path:path.join(work,'browser-idle-walk.png'),fullPage:true});
  await page.click('#play');await page.waitForFunction(()=>phase===4);await page.click('#play');
  if(errors.length)throw new Error(errors.join('\n'));
  fs.writeFileSync(path.join(work,'browser-verification.json'),JSON.stringify({status:'passed',browser:await browser.version(),coverage,loops,transitions,javascript_errors:errors,live_client_acceptance:false},null,2));
  console.log(JSON.stringify({status:'passed',coverage,played_sequences:loops.length,transitions,errors:errors.length}));
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
