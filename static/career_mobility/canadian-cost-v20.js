(()=>{'use strict';
const el=id=>document.getElementById(id),money=n=>new Intl.NumberFormat('en-CA',{style:'currency',currency:'CAD',maximumFractionDigits:0}).format(n);
const data=JSON.parse(el('mobility-cost-data').textContent), citations=JSON.parse(el('mobility-citations').textContent);
const required=['current-salary','new-salary','current-rent','new-rent'];
const optional=['current-living','new-living','moving','licensing','one-time','current-net','new-net',...['utilities','transport','groceries','childcare','extra'].flatMap(k=>['current-'+k,'new-'+k])];
const ids=[...required,...optional];
const num=(id,blankZero=false)=>{const v=el(id).value.trim();if(!v)return blankZero?0:null;const n=Number(v);return Number.isFinite(n)&&n>=0&&n<=100000000?n:null};
const normalize=v=>v.trim().toLocaleLowerCase('en-CA').replace(/\s+/g,' ');
const findCity=v=>Object.keys(data).find(k=>normalize(k)===normalize(v));
const opts=el('pt-city-options');Object.keys(data).sort().forEach(k=>{const o=document.createElement('option');o.value=k;opts.append(o)});
function note(){const a=el('origin').value.trim(),b=el('destination').value.trim(),target=el('data-note');target.replaceChildren();const x=findCity(a),y=findCity(b);el('use-benchmarks').disabled=!(x||y);
if(!a||!b){target.textContent='Enter two Canadian communities. Published benchmarks are optional.';return}if(normalize(a)===normalize(b)){target.textContent='Choose two different communities.';return}
for(const [label,k] of [['Current',x],['Destination',y]]){if(!k){target.append(document.createTextNode(label+': no published benchmark. Use your own figures. '));continue}for(const [kind,src] of Object.entries(citations[k]||{})){if(!src.url)continue;const a=document.createElement('a');a.href=src.url;a.target='_blank';a.rel='noopener noreferrer';a.textContent=label+' '+kind+' source ('+src.verified+')';target.append(a,document.createTextNode(' · '))}}}
function put(id,value){const x=el(id);if(x)x.textContent=value===null?'—':money(value)}
function render(){const origin=el('origin').value.trim(),destination=el('destination').value.trim();const values=Object.fromEntries(ids.map(id=>[id,num(id,!required.includes(id)&&!['current-net','new-net'].includes(id))]));
const v=id=>values[id];const ready=!!(origin&&destination&&normalize(origin)!==normalize(destination)&&required.every(id=>v(id)!==null));
const valid=optional.every(id=>v(id)!==null||['current-net','new-net'].includes(id));
const extra=side=>['utilities','transport','groceries','childcare','extra'].reduce((total,k)=>total+v(side+'-'+k),0);
const currentLiving=v('current-living')+extra('current'),newLiving=v('new-living')+extra('new');
const currentCost=v('current-rent')+currentLiving,newCost=v('new-rent')+newLiving;
const hasNet=v('current-net')!==null&&v('new-net')!==null;
const currentIncome=hasNet?v('current-net'):v('current-salary')/12,newIncome=hasNet?v('new-net'):v('new-salary')/12;
const current=ready&&valid?currentIncome-currentCost:null,future=ready&&valid?newIncome-newCost:null;
const delta=current===null?null:future-current,upfront=v('moving')+v('licensing')+v('one-time');
put('pay-diff',ready?hasNet?newIncome-currentIncome:(v('new-salary')-v('current-salary'))/12:null);
put('monthly-diff',delta);put('total-move',valid?upfront:null);put('mob-current-budget',current);put('mob-new-budget',future);
put('annual-diff',delta===null?null:delta*12);put('first-year-diff',delta===null?null:delta*12-upfront);
put('housing-difference',ready?v('current-rent')-v('new-rent'):null);
put('living-difference',ready&&valid?currentLiving-newLiving:null);
put('total-cost-difference',ready&&valid?currentCost-newCost:null);
put('annual-cost-difference',ready&&valid?(currentCost-newCost)*12:null);
put('three-year-difference',delta===null?null:delta*36-upfront);put('five-year-difference',delta===null?null:delta*60-upfront);
const max=Math.max(1,ready&&valid?Math.max(0,current,future):0);el('mob-bar-current').style.width=delta===null?'0%':Math.max(0,current)/max*100+'%';el('mob-bar-new').style.width=delta===null?'0%':Math.max(0,future)/max*100+'%';
el('income-method').textContent=hasNet?'Using your supplied monthly take-home pay for both locations. Verify that both estimates use the same assumptions.':'Using gross annual salary divided by 12. Income taxes and payroll deductions are not deducted. To compare after-tax cash flow, enter take-home pay for both locations.';
el('break-even').textContent=!ready?'Enter two locations, both annual salaries and both monthly housing costs to calculate.':!valid?'Correct invalid expense values.':delta<=0?'The destination does not improve estimated monthly cash flow; upfront costs are not recovered through this comparison.':upfront===0?'No upfront moving costs entered. Monthly cash flow improves by '+money(delta)+'.':'Estimated recovery of upfront costs: '+Math.ceil(upfront/delta)+' months, based on a '+money(delta)+' monthly improvement.';
el('print-plan').disabled=delta===null;el('save-relocation').dataset.ready=delta===null?'no':'yes';}
el('use-benchmarks').addEventListener('click',()=>{const a=data[findCity(el('origin').value)]||{},b=data[findCity(el('destination').value)]||{};for(const [id,x] of [['current-salary',a.salary],['new-salary',b.salary],['current-rent',a.rent],['new-rent',b.rent],['current-living',a.living],['new-living',b.living]])if(el(id).value.trim()===''&&x!==undefined&&x!==null&&x!=='')el(id).value=x;render()});
for(const id of ['origin','destination'])el(id).addEventListener('input',()=>{note();render()});ids.forEach(id=>el(id).addEventListener('input',render));
el('print-plan').addEventListener('click',()=>{if(!el('print-plan').disabled)window.print()});
el('save-relocation').addEventListener('click',async()=>{const status=el('save-status');if(el('save-relocation').dataset.ready!=='yes'){status.textContent='Complete the cost comparison first.';return}const token=document.cookie.split('; ').find(x=>x.startsWith('csrftoken='))?.split('=')[1]||document.querySelector('[name=csrfmiddlewaretoken]')?.value;if(!token){status.textContent='Reload to restore your session before saving.';return}const inputs=Object.fromEntries(['origin','destination',...ids].map(id=>[id,el(id).value]));try{const r=await fetch('/career-resources/salary-comparison/save/',{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':decodeURIComponent(token)},credentials:'same-origin',body:JSON.stringify({plan_type:'relocation',title:inputs.origin+' to '+inputs.destination,inputs})});status.textContent=r.ok?'Comparison saved.':'Unable to save. Sign in with a Canadian job seeker account.'}catch{status.textContent='Connection failed. Try again.'}});
note();render();})();