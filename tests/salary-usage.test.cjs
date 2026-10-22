const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const {randomUUID}=require('node:crypto');
function harness({ga=true, privacy=false}={}){
  const nodes=new Map(), calls=[], gaCalls=[];
  function node(id){if(!nodes.has(id))nodes.set(id,{value:'',hidden:false,style:{},textContent:'',events:{},addEventListener(type,fn){this.events[type]=fn},append(){},click(){},remove(){},focus(){}});return nodes.get(id)}
  ['salary-app','employee-type','employee-pay','employee-hours','employee-weeks','billing','split','visits','days','weeks','contractor-expenses','unpaid-hours'].forEach(node);
  const window={crypto:{randomUUID},ptSalaryUsageUrl:'/usage/',ptSalaryPdfUrl:'/pdf/',ptSalarySaveUrl:'/save/'};
  if(ga)window.gtag=(...args)=>gaCalls.push(args);
  let succeed=false;
  const context={window,document:{getElementById:node,querySelector:()=>({value:'csrf'}),createElement:()=>node('download'),body:{append(){}}},navigator:{doNotTrack:privacy?'1':'0'},location:{search:''},Intl,URLSearchParams,URL:{createObjectURL:()=>'/blob',revokeObjectURL(){}},setTimeout(){},fetch:async(url,opts)=>{
    calls.push({url,data:JSON.parse(opts.body)});
    return {ok:url==='/usage/'||succeed,status:succeed?200:400,headers:{get:()=> 'application/json'},blob:async()=>({}),json:async()=>succeed?{saved:true}: {error:'Rejected'}};
  }};
  vm.runInNewContext(fs.readFileSync('static/career_mobility/salary-comparison.js','utf8'),context);
  const flush=async()=>{for(let i=0;i<12;i++)await new Promise(resolve=>setImmediate(resolve))};
  return {node,calls,gaCalls,window,flush,succeed(){succeed=true},async fill(){
    for(const [id,v] of Object.entries({'employee-type':'annual','employee-pay':'85000','billing':'100','split':'60','visits':'8','days':'5','weeks':'48'}))node(id).value=v;
    node('employee-pay').events.input();await flush();
  },events:()=>calls.filter(c=>c.url==='/usage/').map(c=>c.data.event)};
}
test('usage works without GA; edits count once and contain no financial input',async()=>{
  const h=harness({ga:false});await h.flush();assert.deepEqual(h.events(),['salary_calculator_view']);
  await h.fill();h.node('employee-pay').events.input();await h.flush();
  assert.deepEqual(h.events(),['salary_calculator_view','salary_calculator_start','salary_comparison_complete']);
  for(const c of h.calls)assert.deepEqual(Object.keys(c.data).sort(),['event','event_id','page_id']);
});
test('failed PDF/save responses do not count; successful responses count once per action',async()=>{
  const h=harness();await h.fill();
  await h.node('print-salary').events.click();await h.node('save-salary').events.click();await h.flush();
  assert.ok(!h.events().includes('salary_pdf_download'));assert.ok(!h.events().includes('salary_comparison_saved'));
  h.succeed();await h.node('print-salary').events.click();await h.node('save-salary').events.click();await h.flush();
  assert.equal(h.events().filter(n=>n==='salary_pdf_download').length,1);assert.equal(h.events().filter(n=>n==='salary_comparison_saved').length,1);
  assert.equal(h.gaCalls.filter(c=>c[1]==='salary_comparison_saved').length,1);
});
test('GA exceptions cannot break the comparison or first-party recording',async()=>{
  const h=harness();h.window.gtag=()=>{throw Error('blocked')};await h.fill();assert.equal(h.node('salary-output').hidden,false);assert.ok(h.events().includes('salary_comparison_complete'));
});
test('browser privacy opt-out disables first-party recording',async()=>{
  const h=harness({ga:false,privacy:true});await h.fill();assert.equal(h.calls.length,0);assert.equal(h.node('salary-output').hidden,false);
});

test('calculator has no location prompt or client-controlled country payload',async()=>{
 const h=harness();await h.fill();
 for(const call of h.calls.filter(c=>c.url==='/usage/'))assert.ok(!('country' in call.data));
 assert.ok(!fs.readFileSync('static/career_mobility/salary-comparison.js','utf8').includes('usage-country'));
});
