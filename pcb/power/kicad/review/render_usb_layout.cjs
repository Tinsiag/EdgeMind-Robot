const path = require('path');
const sharp = require('C:/Users/Shan_/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp');
const folder = path.join(__dirname, 'usb-layout');
const names = ['两路5V与USB供电_布局示意','两路降压核心_放大图','两路USB端口_放大图'];
Promise.all(names.map(async name => {
  const r = await sharp(path.join(folder,name+'.svg')).png().toFile(path.join(folder,name+'.png'));
  return {name,width:r.width,height:r.height,bytes:r.size};
})).then(rows => process.stdout.write(JSON.stringify(rows)+'\n'))
  .catch(e => {process.stderr.write(String(e));process.exitCode=1;});
