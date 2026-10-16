const {chromium}=require('C:/Users/sc/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
const fs=require('fs'),path=require('path');
(async()=>{
 const browser=await chromium.launch({executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe',headless:true});
 const page=await browser.newPage({viewport:{width:1000,height:1300},deviceScaleFactor:1});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto('file:///'+path.join(__dirname,'pair-preview.html').replaceAll('\\','/'));
 await page.frameLocator('iframe').locator('[data-pair-wire]').first().waitFor();
 const frame=page.frames().find(f=>f.parentFrame());
 const groups=['left-drive','right-drive','left-encoder','right-encoder','power'];
 for(const group of groups){
  await frame.locator('#pair-group').selectOption(group);
  if(await frame.locator('[data-pair-wire]').count()!==2)throw Error('Not exactly two wires');
  const exported=await frame.evaluate(()=>{
   const original=document.querySelector('#pair-svg'),clone=original.cloneNode(true);
   const a=[original,...original.querySelectorAll('*')],b=[clone,...clone.querySelectorAll('*')];
   a.forEach((el,i)=>{const cs=getComputedStyle(el);for(const k of ['fill','stroke','stroke-width','stroke-linejoin','stroke-linecap','font-family','font-size','font-weight','paint-order','opacity'])b[i].style.setProperty(k,cs.getPropertyValue(k));});
   clone.setAttribute('xmlns','http://www.w3.org/2000/svg');clone.setAttribute('width','1800');clone.setAttribute('height','1400');
   clone.style.width='1800px';clone.style.height='1400px';return clone.outerHTML;
  });
  fs.writeFileSync(path.join(__dirname,group+'.svg'),exported);
  const flat=await browser.newPage({viewport:{width:1800,height:1400},deviceScaleFactor:1});
  await flat.setContent('<style>body{margin:0;background:white}</style>'+exported);
  await flat.locator('svg').screenshot({path:path.join(__dirname,group+'.png')});await flat.close();
 }
 await frame.locator('#pair-group').selectOption('left-drive');
 await frame.locator('#pair-p7').click();
 if(await frame.locator('svg').getAttribute('viewBox')!=='135 640 540 300')throw Error('P7 zoom failed');
 await frame.locator('#pair-lr').click();
 if(await frame.locator('svg').getAttribute('viewBox')!=='1270 385 470 270')throw Error('LR zoom failed');
 await frame.locator('#pair-fit').click();
 await frame.locator('#acg720-pair-wiring').screenshot({path:path.join(__dirname,'pair-inline-qa.png')});
 await page.setViewportSize({width:360,height:1000});
 const overflow=await frame.evaluate(()=>document.documentElement.scrollWidth>document.documentElement.clientWidth+1);
 if(overflow||errors.length)throw Error(JSON.stringify({overflow,errors}));
 fs.writeFileSync(path.join(__dirname,'pair-verification.json'),JSON.stringify({groups,wire_count_each:2,zoom:true,mobile_overflow:overflow,errors},null,2));
 await browser.close();console.log('PASS: five views, exactly two solid wires each, two zooms, no mobile overflow or runtime errors.');
})();
