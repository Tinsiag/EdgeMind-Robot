const fs = require('fs');
const path = require('path');
const sharp = require('C:/Users/sc/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/sharp');

const base = __dirname;
const out = path.resolve(base, '../../../output/power-diagnostics');
fs.mkdirSync(out, { recursive: true });
const board = fs.readFileSync(path.join(base, 'current-lower-measure-inspection.png')).toString('base64');
const ground = fs.readFileSync(path.join(base, 'current-ground-measure-inspection.png')).toString('base64');
const esc = s => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const tx = (x, y, s, size = 29, color = '#192838', weight = 'normal') => `<text x="${x}" y="${y}" fill="${color}" font-size="${size}" font-weight="${weight}">${esc(s)}</text>`;
const rounded = (x,y,w,h,fill,stroke='#dae2eb',r=14) => `<rect x="${x}" y="${y}" width="${w}" height="${h}" rx="${r}" fill="${fill}" stroke="${stroke}" stroke-width="2"/>`;
const label = (x,y,w,s,color) => rounded(x,y,w,64,'#fff',color) + tx(x+16,y+44,s,32,color,'bold');
const colors = { a:'#00dcff', b:'#67ff73', c:'#fd81ff', d:'#ffa65a', e:'#67ff73', g:'#00dcff' };
const bx = 60, by = 420, scale = 2.6;
const p = ([x,y]) => [bx+x*scale, by+y*scale];
const A=p([193,62]), B=p([222,62]), C=p([159,62]), D=p([159,90]), E=p([180,256]);
const ring = (pt,color,r=20) => `<circle cx="${pt[0]}" cy="${pt[1]}" r="${r}" fill="none" stroke="#111" stroke-width="9"/><circle cx="${pt[0]}" cy="${pt[1]}" r="${r}" fill="none" stroke="${color}" stroke-width="5"/>`;
const leader = (points,color) => `<polyline points="${points.map(p=>p.join(',')).join(' ')}" fill="none" stroke="#fff" stroke-width="8" stroke-linejoin="round"/><polyline points="${points.map(p=>p.join(',')).join(' ')}" fill="none" stroke="${color}" stroke-width="4" marker-end="url(#${Object.keys(colors).find(k=>colors[k]===color)})"/>`;
const defs = Object.entries(colors).map(([k,v])=>`<marker id="${k}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="9" markerHeight="9" orient="auto-start-reverse"><path d="M0 0 L10 5 L0 10 Z" fill="${v}" stroke="#222" stroke-width="0.4"/></marker>`).join('');
let body = rounded(0,0,1920,1600,'#f3f6fa','#f3f6fa',0);
body += rounded(20,20,1880,98,'#18334c','#18334c') + tx(60,87,'USB4 排查测量位置',55,'#fff','bold');
body += rounded(20,135,1120,1420,'#fff') + rounded(1170,135,730,1420,'#fff');
body += tx(50,180,'下方降压电路：U1 / USB4',30,'#18334c','bold');
body += `<image x="${bx}" y="${by}" width="1040" height="832" href="data:image/png;base64,${board}"/>`;
body += label(45,220,480,'③ R12 上端（FB）','#81349c');
body += label(45,320,480,'④ R12 下端（GND）','#a25608');
body += label(580,220,500,'① R11 左端（FB）','#007c99');
body += label(580,320,500,'② R11 右端（输出）','#147a2c');
body += leader([[525,252],[550,252],[550,445],[C[0]-18,C[1]-20]],colors.c);
body += leader([[290,384],[290,D[1]],[D[0]-22,D[1]]],colors.d);
body += leader([[1080,252],[1115,252],[1115,395],[760,395],[A[0]+12,A[1]-23]],colors.a);
body += leader([[930,384],[930,490],[B[0]+22,B[1]-8]],colors.b);
body += ring(A,colors.a)+ring(B,colors.b)+ring(C,colors.c)+ring(D,colors.d);
body += label(580,1280,500,'⑤ L2 右端（输出）','#147a2c');
body += leader([[790,1280],[790,E[1]],[E[0]+32,E[1]]],colors.e)+ring(E,colors.e,29);
body += tx(60,1410,'记录：① ____ V     ② ____ V',34,'#192838','bold');
body += tx(60,1470,'断电测阻：R11 ____ kΩ    R12 ____ kΩ',32);

body += tx(1200,182,'0 点：CN1 负极 GND',33,'#18334c','bold');
const gx=1290, gy=205, gs=1.6;
body += `<image x="${gx}" y="${gy}" width="448" height="288" href="data:image/png;base64,${ground}"/>`;
const G=[gx+84*gs,gy+95*gs];
body += ring(G,colors.g,60);
body += tx(1200,542,'通电测电压时，黑表笔固定接 0 点。',29);
body += rounded(1190,570,690,58,'#c92f3d','#c92f3d')+tx(1210,612,'第一步：通电测电压（DC V）',31,'#fff','bold');
body += tx(1205,676,'黑表笔接 0，红表笔先接①，再接②。',29);
body += tx(1205,727,'分别记录两个对地电压。',29);
body += tx(1205,778,'测电压时不要使用电阻档。',29,'#b12b38','bold');

body += rounded(1190,817,690,58,'#205fab','#205fab')+tx(1210,860,'第二步：断电测电阻（Ω）',31,'#fff','bold');
const ohms = [
 '拔掉输入和外接设备，确认已放电。',
 '两支表笔分别接①、②，测 R11。',
 '两支表笔分别接③、④，测 R12。',
 'R11 标称82kΩ；核实是否用了100kΩ。',
 'R12 标称11.1kΩ。',
 '板上读数受其他通路影响；',
 '异常时拆起电阻一端确认。'
];
ohms.forEach((s,i)=>body+=tx(1205,925+i*43,s,28));
body += rounded(1190,1255,690,58,'#167949','#167949')+tx(1210,1298,'第三步：断电检查通断',31,'#fff','bold');
body += tx(1205,1360,'② ↔ ⑤    ① ↔ ③    ④ ↔ 0',32,'#167949','bold');
body += tx(1205,1410,'以上三组应导通，接近0Ω。',29);
body += tx(1205,1470,'这是测量位置，不需要焊线。',29,'#18334c','bold');
body += rounded(20,1565,1880,33,'#ffeda4','#ffeda4',5)+tx(42,1589,'表笔插 COM 和 VΩ；通电时禁止使用电阻档。测量时只碰指定焊盘，避免同时碰到相邻焊盘。',24,'#352d0b','bold');
const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1600" viewBox="0 0 1920 1600"><style>text {font-family:'Microsoft YaHei','SimHei',sans-serif;}</style><defs>${defs}</defs>${body}</svg>`;
const svgPath=path.join(out,'usb4-probe-map-precise.svg');
const pngPath=path.join(out,'usb4-probe-map-precise.png');
fs.writeFileSync(svgPath,svg,'utf8');
sharp(Buffer.from(svg)).png().toFile(pngPath).then(()=>console.log(JSON.stringify({svgPath,pngPath,points:{A,B,C,D,E,G}}))).catch(e=>{console.error(e.message);process.exit(1)});
