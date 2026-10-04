const fs = require('fs');
const path = require('path');
const sharp = require('C:/Users/Shan_/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp');
const out=path.join(__dirname,'all-layout');
(async()=>{
 for(const name of fs.readdirSync(out).filter(f=>f.endsWith('.svg'))){
  await sharp(path.join(out,name)).png().toFile(path.join(out,name.replace('.svg','.png')));
 }
 const names=fs.readdirSync(out).filter(f=>/^\d\d_.*\.png$/.test(f));
 const previews=await Promise.all(names.map(async (f,i)=>({input:await sharp(path.join(out,f)).resize(600,450,{fit:'contain',background:'#f2f6fa'}).png().toBuffer(),left:(i%3)*600,top:Math.floor(i/3)*450})));
 await sharp({create:{width:1800,height:Math.ceil(names.length/3)*450,channels:3,background:'#fff'}}).composite(previews).png().toFile(path.join(out,'图册总览.png'));
 console.log(JSON.stringify({rendered:names.length,contactSheet:path.join(out,'图册总览.png')}));
})();
