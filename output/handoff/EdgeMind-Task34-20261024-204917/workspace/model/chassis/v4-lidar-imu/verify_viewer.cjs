const fs=require('fs'),path=require('path');
const {pathToFileURL}=require('url');
const {chromium}=require('C:/Users/sc/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
async function renderDrawing(page){
 const drawingPage=await page.context().newPage();
 try{
  await drawingPage.setViewportSize({width:1260,height:1140});
  await drawingPage.setContent('<html><body style="margin:0"><div id="drawing" style="width:1260px;height:1140px">'+fs.readFileSync(path.join(__dirname,'ThirdDeck-drawing.svg'),'utf8')+'</div></body></html>');
  await drawingPage.locator('#drawing').screenshot({path:path.join(__dirname,'preview-drawing.png')});
 }finally{await drawingPage.close();}
}
(async()=>{
 const expected=JSON.parse(fs.readFileSync(path.join(__dirname,'verification.json'),'utf8')).parts.length;
 const browser=await chromium.launch({headless:true,executablePath:'C:/Program Files/Google/Chrome/Application/chrome.exe'});
 try{
  const context=await browser.newContext({viewport:{width:1760,height:1160},deviceScaleFactor:1});
  const page=await context.newPage();
  if(process.argv.includes('--drawing-only')){await renderDrawing(page);console.log('Drawing rendered');return;}
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(pathToFileURL(path.join(__dirname,'查看模型.html')).href);
  await page.waitForFunction(()=>window.chassisViewerState?.rendered,{timeout:60000});
  const initial=await page.evaluate(()=>window.chassisViewerState);
  if(initial.parts!==expected)throw new Error('Mesh count mismatch');
  const imuPlacement=await page.evaluate(()=>{
   const data=JSON.parse(document.getElementById('model-data').textContent);
   const xs=name=>data.find(p=>p.name===name).vertices.map(p=>p[0]);
   const mid=name=>{const a=xs(name);return (Math.min(...a)+Math.max(...a))/2;};
   return {pcb:mid('IMUPCB'),header:mid('IMUHeader'),spacer:mid('IMUSpacer1')};
  });
  if(!(imuPlacement.pcb>0&&imuPlacement.header<imuPlacement.pcb&&imuPlacement.spacer>imuPlacement.pcb))throw new Error('MPU opposite-side orientation mismatch');
  const shot=async n=>page.locator('#view').screenshot({path:path.join(__dirname,n+'.png')});
  await shot('preview-assembled');
  await page.locator('#sensor-focus').click();await shot('preview-sensors');
  await page.locator('#third-only').click();await page.locator('#top').click();
  await page.evaluate(()=>window.setChassisView(-Math.PI/2,.001,550,[0,0,162]));
  const thirdOnly=await page.evaluate(()=>window.chassisViewerState);
  if(thirdOnly.layer_parts.some(p=>p.layer!==3&&p.visible))throw new Error('Third-only view leaked lower layers');
  if(!thirdOnly.layer_parts.some(p=>p.name==='PerfboardSource'&&p.visible))throw new Error('Perfboard missing');
  await shot('preview-third-top');
  await page.locator('#reset').click();
  await page.locator('#explode').evaluate(el=>{el.value=55;el.dispatchEvent(new Event('input',{bubbles:true}))});
  const exploded=await page.evaluate(()=>window.chassisViewerState);
  if(exploded.layer_parts.some(p=>p.lift!==(p.layer===3?110:p.layer===2?55:0)))throw new Error('Layer explosion mismatch');
  await page.evaluate(()=>window.setChassisView(-2.15,1.12,920,[0,-5,150]));await shot('preview-exploded');
  await page.locator('#explode').evaluate(el=>{el.value=0;el.dispatchEvent(new Event('input',{bubbles:true}))});
  await page.locator('#third').uncheck();
  const hidden=await page.evaluate(()=>window.chassisViewerState);
  if(hidden.layer_parts.some(p=>p.layer===3&&p.visible))throw new Error('Third layer visibility mismatch');
  await page.locator('#reset').click();
  await page.screenshot({path:path.join(__dirname,'preview-viewer.png')});
  await renderDrawing(page);
  if(errors.length)throw new Error(JSON.stringify(errors));
  fs.writeFileSync(path.join(__dirname,'viewer-verification.json'),JSON.stringify({mesh_count:expected,imuPlacement,initial,thirdOnly,exploded,third_layer_visibility_checked:true,console_errors:errors},null,2));
  console.log(JSON.stringify({rendered:true,parts:expected,thirdOnly:true,exploded:true,perfboard_visible:true,errors}));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
