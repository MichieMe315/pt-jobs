(() => {
  'use strict';
  const $ = id => document.getElementById(id);
  if (!$('salary-app')) return;
  const fields = ['employee-type','employee-pay','employee-hours','employee-weeks','billing','split','visits','days','weeks','contractor-expenses','unpaid-hours'];
  const money = n => new Intl.NumberFormat('en-CA',{style:'currency',currency:'CAD',maximumFractionDigits:0}).format(n);
  const value = id => {
    const input = $(id);
    if (!input || input.value.trim() === '') return null;
    const n = Number(input.value);
    return Number.isFinite(n) ? n : null;
  };
  const positive = (id,max=Infinity) => value(id)!==null && value(id)>0 && value(id)<=max;
  const set = (id,text) => { if ($(id)) $(id).textContent=text; };
  const chart = (employee,contractor) => {
    const a = employee ?? 0, b = contractor ?? 0, max=Math.max(a,b,1);
    $('bar-employee').style.width = `${a/max*100}%`;
    $('bar-contractor').style.width = `${b/max*100}%`;
    set('employee-cash',employee===null?'Add employee pay':money(employee));
    set('contractor-cash',contractor===null?'Add contractor details':money(contractor));
    set('salary-chart-note',employee!==null&&contractor!==null?'Both offers entered. Chart updates automatically.':(employee!==null||contractor!==null?'One offer entered. Add the other to compare.':'Enter either offer to start the chart. It updates as you type.'));
  };
  let last=null;
  function render() {
    const annual=$('employee-type').value==='annual';
    $('employee-hours-wrap').hidden=annual;
    $('employee-weeks-wrap').hidden=annual;
    $('pay-label').innerHTML=(annual?'Annual salary':'Hourly wage')+' (CAD) <span>*</span>';
    const employeeValid=['annual','hourly'].includes($('employee-type').value)&&positive('employee-pay')&&(annual||(positive('employee-hours',80)&&positive('employee-weeks',52)));
    const contractorValid=positive('billing')&&positive('split',100)&&positive('visits',60)&&positive('days',7)&&positive('weeks',52);
    const extrasValid=['contractor-expenses','unpaid-hours'].every(id=>value(id)===null||value(id)>=0) && (value('unpaid-hours')===null||value('unpaid-hours')<=100);
    const employee=employeeValid?(annual?value('employee-pay'):value('employee-pay')*value('employee-hours')*value('employee-weeks')):null;
    const perVisit=contractorValid?value('billing')*value('split')/100:null;
    const contractor=contractorValid?perVisit*value('visits')*value('days')*value('weeks'):null;
    chart(employee,contractor);
    const valid=employee!==null&&contractor!==null&&extrasValid;
    $('salary-output').hidden=!valid;
    ['salary-details','salary-insight','per-visit'].forEach(id=>{if($(id))$(id).hidden=!valid;});
    $('print-salary').disabled=!valid;
    if($('save-salary'))$('save-salary').disabled=!valid;
    $('input-hint').hidden=valid;
    if(!valid){last=null;if($('effective-hourly'))$('effective-hourly').hidden=true;return;}
    const expenses=value('contractor-expenses')??0;
    const unpaid=value('unpaid-hours')??0;
    const contractorNet=contractor-expenses;
    const grossDifference=contractor-employee;
    const netDifference=contractorNet-employee;
    set('employee-result',money(employee));
    set('contractor-result',money(contractor));
    set('difference',(grossDifference>0?'+':'')+money(grossDifference));
    set('difference-explain',grossDifference>=0?'Contractor revenue is higher before business expenses.':'Employee gross pay is higher before benefits.');
    set('employee-monthly',money(employee/12));
    set('contractor-monthly',money(contractor/12));
    set('contractor-net',money(contractorNet));
    set('net-difference',(netDifference>0?'+':'')+money(netDifference));
    const visitsNeeded=(employee+expenses)/(perVisit*value('days')*value('weeks'));
    set('breakeven',`Including the entered annual contractor expenses, approximately ${visitsNeeded.toFixed(1)} completed visits per clinical day would match employee gross earnings before income tax.`);
    set('per-visit',`Contractor share per completed visit: ${money(perVisit)}. Actual income depends on completed and paid visits.`);
    if($('effective-hourly'))$('effective-hourly').hidden=!(unpaid>0);
    set('effective-hourly',unpaid>0?`Illustrative contractor hourly revenue including unpaid time: ${money(contractor/(value('days')*value('weeks')*8+unpaid*value('weeks')))}. Assumes eight clinical hours per day; not an after-tax rate.`:'');
    last=Object.fromEntries(fields.map(id=>[id,$(id).value]));
    last.employee_gross=employee;
    last.contractor_gross=contractor;
    last.contractor_after_expenses=contractorNet;
    last.annual_difference_after_expenses=netDifference;
  }
  fields.forEach(id=>$(id)?.addEventListener('input',render));
  $('employee-type').addEventListener('change',render);
  $('salary-clear').addEventListener('click',()=>{
    fields.forEach(id=>{$(id).value='';});
    set('save-status','');
    render();
    $('employee-type').focus();
  });
  const token=()=>document.querySelector('[name=csrfmiddlewaretoken]')?.value || '';
  $('print-salary').addEventListener('click',async()=>{
    if(!last){set('input-hint','Enter both offers before downloading a report.');return;}
    const button=$('print-salary'),label=button.textContent;
    button.disabled=true;button.textContent='Preparing PDF…';
    try{
      const response=await fetch(window.ptSalaryPdfUrl,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':token()},body:JSON.stringify(last)});
      if(!response.ok)throw new Error('PDF could not be generated');
      const blob=await response.blob(),url=URL.createObjectURL(blob),link=document.createElement('a');
      link.href=url;link.download='ptjc-salary-vs-split.pdf';document.body.append(link);link.click();link.remove();
      setTimeout(()=>URL.revokeObjectURL(url),30000);
    }catch(err){set('input-hint','PDF unavailable. Please try again.');$('input-hint').hidden=false;}
    finally{button.disabled=false;button.textContent=label;}
  });
  const save=$('save-salary');
  if(save)save.addEventListener('click',async()=>{
    const status=$('save-status');
    if(!last){status.textContent='Enter both offers before saving.';return;}
    save.disabled=true;status.textContent='Saving comparison…';
    try{
      const response=await fetch(window.ptSalarySaveUrl,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':token()},body:JSON.stringify({plan_type:'salary',title:'Salary vs. Split comparison',inputs:last})});
      const contentType=response.headers.get('content-type')||'';
      const result=contentType.includes('application/json')?await response.json():{};
      if(!response.ok||!result.saved)throw new Error(result.error||`Unable to save (${response.status})`);
      status.textContent='Saved to your job seeker dashboard. ';
      if(result.url){const a=document.createElement('a');a.href=result.url;a.textContent='Open job seeker dashboard';status.append(a);}
    }catch(err){status.textContent=err.message||'Unable to save. Please try again.';}
    finally{save.disabled=false;}
  });
  render();
  const savedId = new URLSearchParams(location.search).get('saved');
  if (savedId && /^\d+$/.test(savedId) && window.ptSalaryLoadPrefix) {
    fetch(window.ptSalaryLoadPrefix + savedId + '/', {credentials:'same-origin'})
      .then(async response => {if (!response.ok) throw new Error('This saved comparison is unavailable.');return response.json();})
      .then(data => {
        if (!data.inputs || typeof data.inputs !== 'object') throw new Error('Saved data is invalid.');
        fields.forEach(id => {if (Object.prototype.hasOwnProperty.call(data.inputs,id) && $(id)) $(id).value = data.inputs[id];});
        render();
        set('save-status','Saved comparison loaded. You can adjust the figures and save a new comparison.');
      })
      .catch(error => {set('save-status',error.message);});
  }
})();
