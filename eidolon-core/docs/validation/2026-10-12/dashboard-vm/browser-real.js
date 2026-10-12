"use strict";
const fs=require("fs"),path=require("path");
const {chromium}=require("/home/toytoy/eidolon-validation/browser-qa/node_modules/playwright");
const input=JSON.parse(fs.readFileSync(0,"utf8"));
(async()=>{
 const browser=await chromium.launch();
 const checks=[];
 try {
  fs.mkdirSync(input.captures,{recursive:true});
  for(const width of [1280,360]){
   const page=await browser.newPage({viewport:{width,height:900}});
   const errors=[],monitor=[],comm=[];
   page.on("pageerror",e=>errors.push(String(e)));
   page.on("request",r=>{if(r.url().includes("/v1/monitor/"))monitor.push(r.method());if(r.url().includes("/v1/comm/"))comm.push(r.method());});
   await page.goto(input.url);
   await page.fill("#conv-key",input.key);await page.press("#conv-key","Enter");
   await page.waitForSelector("#conv-body:not([hidden])");
   await page.waitForTimeout(300);
   checks.push({width,check:"capture_off_and_no_background_reads",ok:await page.evaluate(()=>["mic","speaker","camera"].every(k=>!document.getElementById("comm-"+k+"-on").checked)) && monitor.length===0 && comm.length===0});
   await page.click("#monitor-refresh");
   await page.waitForFunction(()=>document.querySelectorAll("#monitor-machines .monitor-card").length===3);
   const cards=await page.$$eval("#monitor-machines .monitor-card",els=>els.map(e=>e.textContent));
   checks.push({width,check:"real_core_metrics_visible",ok:/Mémoire/.test(cards[0])&&/Disque du journal/.test(cards[0])&&/CPU/.test(cards[0]),detail:cards[0]});
   checks.push({width,check:"uncovered_machines_explicit",ok:cards.slice(1).every(c=>/Non surveillé/.test(c)&&!/Gio|%/.test(c))});
   checks.push({width,check:"manual_single_read_and_no_overflow",ok:monitor.length===1&&(await page.evaluate(()=>document.documentElement.scrollWidth===document.documentElement.clientWidth))&&errors.length===0,errors});
   const html=await page.content();
   checks.push({width,check:"key_not_in_markup_or_persistent_storage",ok:!html.includes(input.key)&&await page.evaluate(()=>localStorage.length===0&&document.cookie.length===0)});
   await page.locator("#monitor").screenshot({path:path.join(input.captures,"dashboard-real-monitor-"+width+".png")});
   await page.click("#conv-close");
   await page.waitForSelector("#monitor",{state:"hidden"});
   checks.push({width,check:"close_hides_and_stops_monitor",ok:await page.locator("#monitor-machines li").count()===0});
   await page.close();
  }
 } finally {await browser.close();}
 const out={passed:checks.filter(c=>c.ok).length,total:checks.length,checks,physical_devices_tested:false};
 fs.writeFileSync(input.output,JSON.stringify(out,null,2));console.log(JSON.stringify(out));
 if(out.passed!==out.total)process.exitCode=1;
})().catch(e=>{console.error(String(e));process.exit(1)});
