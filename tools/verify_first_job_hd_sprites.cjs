/* Browser regression check for the frozen accepted first-job review. */
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {chromium}=require(process.env.FIRST_JOB_PLAYWRIGHT_MODULE||'C:/Users/Administrator/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const work=path.resolve(__dirname,'../Assets/HDFirstJobs/accepted-v1');
const url=process.env.FIRST_JOB_REVIEW_URL||'http://127.0.0.1:8771/accepted-v1/review.html';
(async()=>{
 const browser=await chromium.launch({headless:true,executablePath:process.env.FIRST_JOB_EDGE_PATH||'C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe'});
 try{
  const page=await browser.newPage({viewport:{width:1400,height:1100}}),errors=[];
  page.on('pageerror',e=>errors.push(String(e)));page.on('requestfailed',r=>errors.push(r.url()));
  page.on('response',r=>{if(r.status()>=400)errors.push(r.status()+' '+r.url())});
  await page.goto(url,{waitUntil:'networkidle'});
  const coverage=await page.evaluate(async()=>{
   playback(false);let actions=0,variants=0,pendingPairs=0;
   for(const p of data){$('job').value=p.job;$('sex').value=p.sex;if(p.pending)pendingPairs++;
    for(const a of p.actions){$('group').value=Math.floor(a.action/8);$('direction').value=a.direction;
     for(const fi of [...new Set([0,a.frames.length-1])]){frameIndex=fi;
      for(const headed of [true,false]){$('heads').checked=headed;await draw();if(drawError)throw Error(drawError);
       const pix={};for(const name of ['native','hd']){const c=$(name);pix[name]=c.getContext('2d').getImageData(0,0,c.width,c.height).data;if(!pix[name].some((v,i)=>i%4===3&&v))throw Error('Empty '+name)}
       if(p.pending){if(pix.native.some((v,i)=>v!==pix.hd[i]))throw Error('Pending native reference changed');if(!$('hdTitle').textContent.includes('pending'))throw Error('Pending pair mislabeled')}
       else if(!$('status').textContent.includes('user-accepted'))throw Error('Accepted pair mislabeled');
       variants++;
      }
     }actions++;
    }
   }
   if(data.length!==12||pendingPairs!==1)throw Error('Unexpected accepted/pending scope');
   return {displayed_pairs:data.length,accepted_pairs:data.length-pendingPairs,pending_pairs:pendingPairs,actions,frame_head_variants:variants};
  });
  const playbackCoverage=await page.evaluate(async()=>{
   const result=[];
   for(const p of data){playback(false);$('job').value=p.job;$('sex').value=p.sex;$('group').value=1;$('direction').value=0;$('heads').checked=true;frameIndex=0;const a=action();
    await Promise.all(a.frames.flatMap(f=>[getImage(f.native),getImage(f.hd),getImage(f.head)]));await draw();
    const seen=new Set(),signatures=new Set();let prior=-1;const start=performance.now();playback(true);
    await new Promise(resolve=>{function observe(t){if(frameIndex!==prior){prior=frameIndex;seen.add(frameIndex);const pix=$('hd').getContext('2d').getImageData(0,0,640,640).data;let h=2166136261;for(let i=0;i<pix.length;i+=16)h=Math.imul(h^pix[i]^pix[i+1]^pix[i+2]^pix[i+3],16777619);signatures.add(h>>>0)}if(t-start>=a.ms*(a.frames.length+4)){playback(false);resolve()}else requestAnimationFrame(observe)}requestAnimationFrame(observe)});
    if(seen.size!==a.frames.length||signatures.size<Math.min(4,a.frames.length))throw Error('Incomplete walk '+p.job+' '+p.sex);
    result.push({job:p.job,sex:p.sex,frames_seen:seen.size,distinct_canvas_frames:signatures.size});
   }return result;
  });
  await page.evaluate(async()=>{playback(false);$('job').value='mage';$('sex').value='male';$('group').value=12;$('direction').value=2;frameIndex=0;await draw()});
  await page.screenshot({path:path.join(work,'verification/browser-mage-casting.png'),fullPage:true});
  await page.check('#grid');await page.selectOption('#background','magenta');await page.uncheck('#heads');await page.evaluate(async()=>{await draw();if(drawError)throw Error(drawError)});
  if(errors.length)throw Error(errors.join('\n'));
  fs.writeFileSync(path.join(work,'verification/browser.json'),JSON.stringify({status:'passed',browser:await browser.version(),coverage,playback:playbackCoverage,errors,review_sha256:crypto.createHash('sha256').update(fs.readFileSync(path.join(work,'review.html'))).digest('hex'),game_files_modified:false},null,2));
  console.log(JSON.stringify({status:'passed',coverage,playback_pairs:playbackCoverage.length,errors:0}));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
