const path = require('path');
const sharp = require('C:/Users/Shan_/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp');
const folder = path.join(__dirname, 'input-layout');
const name = '电池入口与降压输入_布局示意';
sharp(path.join(folder, name + '.svg'))
  .png()
  .toFile(path.join(folder, name + '.png'))
  .then(result => process.stdout.write(JSON.stringify({width: result.width, height: result.height, bytes: result.size}) + '\n'))
  .catch(error => {process.stderr.write(String(error)); process.exitCode = 1;});
