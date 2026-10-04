const path = require('path');
const sharp = require('C:/Users/Shan_/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp');
const folder = path.join(__dirname, 'lm393-layout');
sharp(path.join(folder, 'U22_U23_布局示意.svg'))
  .png()
  .toFile(path.join(folder, 'U22_U23_布局示意.png'))
  .then(result => process.stdout.write(JSON.stringify({width: result.width, height: result.height, bytes: result.size}) + '\n'))
  .catch(error => {process.stderr.write(String(error)); process.exitCode = 1;});
