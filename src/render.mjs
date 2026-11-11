// Esegui dalla radice del repo: node src/render.mjs test <t1> <t2> ...  |  node src/render.mjs full <start> <end> <step>
import { chromium } from '/opt/node-tools/node_modules/playwright/index.mjs';
import http from 'http'; import fs from 'fs'; import path from 'path';
const root=process.cwd();
const args=process.argv.slice(2);const mode=args[0]||'test';
const port=8700+Math.floor(Math.random()*200);
const srv=http.createServer((req,res)=>{const p=path.join(root,decodeURIComponent(req.url.split('?')[0]));fs.readFile(p,(e,d)=>{if(e){res.writeHead(404);res.end();return;}const ext=path.extname(p);const mt={'.html':'text/html','.js':'application/javascript','.mjs':'application/javascript','.jpg':'image/jpeg','.png':'image/png','.json':'application/json'}[ext]||'application/octet-stream';res.writeHead(200,{'content-type':mt});res.end(d);});}).listen(port);
const browser=await chromium.launch({args:['--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader','--ignore-gpu-blocklist']});
const page=await browser.newPage({viewport:{width:1080,height:1920},deviceScaleFactor:1});
page.on('console',m=>console.log('console:',m.text()));page.on('pageerror',e=>console.log('pageerror:',e.message));
await page.goto(`http://localhost:${port}/src/scene.html`);
await page.waitForFunction(()=>window.ready,null,{timeout:120000});
const TL=JSON.parse(fs.readFileSync('src/timeline.json'));const fps=TL.fps;
if(mode==='test'){
 const times=args.slice(1).map(Number);fs.mkdirSync('test',{recursive:true});
 for(const t of times){const t0=Date.now();await page.evaluate(t=>window.seek(t),t);const buf=await page.screenshot({type:'jpeg',quality:88});fs.writeFileSync(`test/t_${t.toFixed(2)}.jpg`,buf);console.log('t',t,'ms',Date.now()-t0);}
}else{
 const [,start,end,step]=args.map(Number);fs.mkdirSync('frames',{recursive:true});
 const t0=Date.now();let n=0;
 for(let i=start;i<end;i+=step){const f=`frames/f${String(i).padStart(5,'0')}.jpg`;if(fs.existsSync(f))continue;await page.evaluate(t=>window.seek(t),i/fps);const buf=await page.screenshot({type:'jpeg',quality:92});fs.writeFileSync(f,buf);n++;if(n%50===0)console.log(`worker ${start}: frame ${i} avg ${((Date.now()-t0)/n).toFixed(0)}ms`);}
 console.log('done',start,(Date.now()-t0)/1000,'s');
}
await browser.close();srv.close();
