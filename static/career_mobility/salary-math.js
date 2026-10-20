/* Pure comparison engine. Gross values only; no invented taxes or benefits. */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;root.PTJCSalaryMath=api;})(typeof window!=='undefined'?window:globalThis,function(){
'use strict';
const positive=(v,max=Infinity)=>v!==''&&v!==null&&v!==undefined&&Number.isFinite(Number(v))&&Number(v)>0&&Number(v)<=max;
function calculate(data){
 const type=data.employeeType;
 if(!['hourly','annual'].includes(type))return null;
 const req=[['employeePay',10000000],['billing',100000],['split',100],['visits',60],['days',7],['weeks',52]];
 if(type==='hourly')req.push(['employeeHours',80],['employeeWeeks',52]);
 if(!req.every(([key,max])=>positive(data[key],max)))return null;
 const employee=type==='annual'?Number(data.employeePay):Number(data.employeePay)*Number(data.employeeHours)*Number(data.employeeWeeks);
 const perVisit=Number(data.billing)*Number(data.split)/100;
 const contractor=perVisit*Number(data.visits)*Number(data.days)*Number(data.weeks);
 const denominator=Number(data.days)*Number(data.weeks)*perVisit;
 if(![employee,contractor,denominator].every(Number.isFinite)||denominator<=0)return null;
 return {employee,contractor,difference:contractor-employee,perVisit,visitsNeeded:employee/denominator,contractorWeekly:contractor/Number(data.weeks),employeeWeekly:employee/(type==='annual'?52:Number(data.employeeWeeks)),contractorMonthly:contractor/12,employeeMonthly:employee/12};
}
return {calculate};
});
