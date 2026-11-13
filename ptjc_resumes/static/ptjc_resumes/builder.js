(()=>{'use strict';
const cfg=JSON.parse(document.getElementById('resume-bootstrap').textContent),$=id=>document.getElementById(id);let data=cfg.data,revision=cfg.revision,step=Number.isInteger(cfg.step)?cfg.step:0,dirty=false,blocked=false,timer=null,saving=null,sampleMode=null,samplePage=1;
const csrf=document.querySelector('#csrf-form [name=csrfmiddlewaretoken]').value;
const orderNames={summary:'Professional background',status:'Canadian assessment and registration',experience:'Clinical experience outside Canada',canadian_experience:'Canadian experience',education:'Education',placements:'Supervised clinical education',home_registration:'Professional registration outside Canada',development:'Professional development',languages:'Languages',availability:'Availability'};
const internationalSteps=[['Your details','Contact information and a professional background that describes your original education and experience.'],['Registration in Canada','Start with your current registration status. Assessment and exam details stay optional and only appear on the resume when you choose to include them.'],['Clinical experience','Add your physiotherapy roles outside Canada. Start with the most recent.'],['Canadian experience','Add relevant Canadian employment or volunteering if you have it. Keep your actual title and supervision. A support role or placement does not imply Canadian PT registration.'],['Education','Use the exact original qualification and institution. Do not relabel an overseas degree as a Canadian degree.'],['Supervised placements','Add relevant clinical education separately from employment. Include hours only if documented and useful to this application.'],['Courses and certifications','Add relevant courses, certifications and completed continuing education. Skip this section if it does not apply.'],['Languages','Add a language and your proficiency. Test details are optional.'],['Availability','These details are optional on the resume. Work authorization is separate from professional registration.'],['Review and arrange','Choose the section order, review the page layout and check your details before downloading.']];
const groups={education:[['degree','Exact qualification',180],['institution','Institution',180],['country','Education country / jurisdiction',100],['completed','Completion month / year',80]],experience:[['role','Job title',160],['employer','Employer or organization',180],['location','City and state / province / region',180],['country','Country',100],['dates','Dates, including month and year',100],['setting','Setting and patient groups',180],['bullets','Responsibilities and achievements — one per line',2500,'textarea']],canadian_experience:[['role','Actual job or volunteer title',160],['employer','Organization',180],['location','City and province',100],['dates','Dates, including month and year',100],['setting','Setting and responsibilities',180],['bullets','Contributions — one bullet per line',2500,'textarea']],placements:[['institution','Institution or placement organization',180],['location','City and state / province / region',180],['country','Country',100],['dates','Placement dates',100],['setting','Supervised setting and broad patient groups',180],['hours','Documented supervised hours (optional)',20],['contribution','Your supervised contributions',1500,'textarea']],development:[['course','Completed course or qualification',180],['provider','Provider',180],['completed','Completion date',80]],languages:[['language','Language',80],['proficiency','Your actual proficiency',180],['evidence','Relevant test or evidence, date (optional)',200]]};

const canadianSteps = [
  ['Your details', 'Add your contact information and choose the practice area you are applying to.'],
  ['Registration and skills', 'Enter the registration you actually hold and the skills relevant to this role.'],
  ['Clinical experience', 'Start with your most recent role. Use specific examples of your work.'],
  ['Education', 'List your physiotherapy qualification and institution.'],
  ['Courses and certifications', 'List completed training relevant to the role.'],
  ['Review and arrange', 'Check your details, arrange sections and open the PDF proof.']
];
const steps = cfg.canadian ? canadianSteps : internationalSteps;
const lastStep = steps.length-1;
const layouts = cfg.canadian ? [['classic','Classic'],['clinical','Clinical'],['editorial','Editorial'],['sidebar','Sidebar']] : [['classic','Professional'],['clinical','Experience'],['editorial','Qualifications'],['sidebar','International profile']];
if(cfg.canadian) Object.assign(orderNames,{summary:'Professional summary',canadian_experience:'Clinical experience',home_registration:'Professional registration'});
function editAppearance(){sampleMode=false;mark()}
function addSettingsToggle(panel, title, id) {
  const button=el('button',title,'resume-settings-toggle');
  const content=el('div',undefined,'resume-settings-content');
  content.id=id;
  content.hidden=true;
  button.type='button';
  button.setAttribute('aria-controls',id);
  button.setAttribute('aria-expanded','false');
  button.addEventListener('click',()=>{
    content.hidden=!content.hidden;
    button.setAttribute('aria-expanded',String(!content.hidden));
  });
  panel.append(button,content);
  return content;
}
function designPicker(){
  const box=$('design-controls');
  const toolbar=el('div',undefined,'resume-design-actions');
  box.append(toolbar);
  const layoutField=el('div',undefined,'resume-layout-field');
  const layoutLabel=el('label','Résumé design');
  const layoutSelect=el('select');
  layoutSelect.id='resume-layout-select';layoutLabel.htmlFor=layoutSelect.id;
  for(const [key,label] of layouts){
    const option=el('option',label);option.value=key;layoutSelect.append(option);
  }
  layoutSelect.value=data.layout||'classic';
  layoutSelect.onchange=()=>{samplePage=1;data.layout=layoutSelect.value;mark(true)};
  layoutField.append(layoutLabel,layoutSelect);toolbar.append(layoutField);
  const label=el('label','PDF colour','resume-palette'), select=el('select');
  select.id='resume-palette';label.htmlFor=select.id;
  for(const [value,name] of [['original','Design default'],['slate','Slate'],['navy','Navy'],['plum','Plum'],['grayscale','Grayscale'],['forest','Forest'],['teal','Deep teal'],['berry','Berry'],['clay','Terracotta'],['cobalt','Cobalt']]){
    const option=el('option',name);option.value=value;select.append(option);
  }
  select.value=data.palette||'original';
  select.addEventListener('change',()=>{data.palette=select.value;editAppearance()});
  const appearance=el('section',undefined,'resume-settings');
  const appearanceBody=addSettingsToggle(appearance,'Appearance','resume-appearance-options');
  const settings=el('div',undefined,'resume-appearance-fields');
  const group=(label,control)=>{const field=el('div');field.append(label,control);return field};
  settings.append(group(label,select));
  const font=el('select');font.id='resume-typeface';font.setAttribute('aria-label','Résumé font');
  for(const [value,name] of [['original','Design font'],['sans','DejaVu Sans'],['serif','Book serif'],['helvetica','Helvetica'],['times','Times Roman'],['mono','Courier'],['italic','Times Italic']]){
    const option=el('option',name);option.value=value;font.append(option);
  }
  font.value=data.typeface||'original';font.onchange=()=>{data.typeface=font.value;editAppearance()};
  const colour=el('input');colour.type='color';colour.value=data.accent_colour||'#253449';colour.setAttribute('aria-label','Custom heading colour');
  colour.oninput=()=>{data.accent_colour=colour.value;editAppearance()};
  const reset=el('button','Reset');reset.type='button';reset.onclick=()=>{data.accent_colour='';colour.value='#253449';editAppearance()};
  const fontLabel=el('label','Font');fontLabel.htmlFor=font.id;
  const colourLabel=el('label','Custom heading colour');colour.id='resume-accent';colourLabel.htmlFor=colour.id;
  const colourActions=(input,button)=>{const row=el('div',undefined,'resume-colour-actions');row.append(input,button);return row};
  reset.setAttribute('aria-label','Reset heading colour');
  const accent=group(colourLabel,colourActions(colour,reset));
  settings.append(group(fontLabel,font),accent);
  const header=el('input');header.type='color';header.id='resume-header-colour';header.value=data.header_colour||'#fae5d7';
  const headerLabel=el('label','Top band colour');headerLabel.htmlFor=header.id;
  header.oninput=()=>{data.header_colour=header.value;editAppearance()};
  const resetHeader=el('button','Reset');resetHeader.type='button';
  resetHeader.onclick=()=>{data.header_colour='';header.value='#fae5d7';editAppearance()};
  resetHeader.setAttribute('aria-label','Reset top band colour');
  const headerGroup=group(headerLabel,colourActions(header,resetHeader));headerGroup.id='clinical-header-setting';
  settings.append(headerGroup);
  appearanceBody.append(settings);toolbar.append(appearance.firstChild);box.append(appearanceBody);
  const extrasPanel=el('section',undefined,'resume-settings');
  const extras=addSettingsToggle(extrasPanel,'Sections and optional photo','resume-section-options');
  for(const [key,name] of Object.entries(orderNames)){
    const label=el('label'),check=el('input');check.type='checkbox';check.checked=!(data.hidden_sections||[]).includes(key);
    check.onchange=()=>{const hidden=new Set(data.hidden_sections||[]);if(check.checked)hidden.delete(key);else hidden.add(key);data.hidden_sections=[...hidden];mark()};
    label.append(check,document.createTextNode(name));extras.append(label);
  }
  const photo=el('input');photo.type='file';photo.accept='image/png,image/jpeg';photo.setAttribute('aria-label','Optional résumé photo');
  photo.onchange=async()=>{try{const file=photo.files[0];if(!file)return;if(file.size>12000000||!['image/png','image/jpeg'].includes(file.type))throw Error('Choose a PNG or JPEG under 12 MB.');
    const bitmap=await createImageBitmap(file), canvas=document.createElement('canvas'), scale=Math.min(1,180/Math.max(bitmap.width,bitmap.height));
    canvas.width=Math.max(1,Math.round(bitmap.width*scale));canvas.height=Math.max(1,Math.round(bitmap.height*scale));canvas.getContext('2d').drawImage(bitmap,0,0,canvas.width,canvas.height);bitmap.close();
    data.portrait=canvas.toDataURL('image/jpeg',.78);if(data.portrait.length>40000){data.portrait='';throw Error('Choose a smaller image.')}mark();
  }catch(e){alertError(e.message)}finally{photo.value=''}};
  const remove=el('button','Remove photo');remove.type='button';remove.onclick=()=>{data.portrait='';mark()};
  const size=el('input');size.type='range';size.min=40;size.max=90;size.value=data.portrait_size||64;size.setAttribute('aria-label','Résumé photo size');size.oninput=()=>{data.portrait_size=Number(size.value);mark()};
  extras.append(el('p','Photo optional. Leave blank for a text-only résumé.'),photo,size,remove);toolbar.append(extrasPanel.firstChild);box.append(extras);
}
function samplePreview(){
  const key=data.layout||'classic', show=sampleMode;
  $('clinical-header-setting').hidden=key!=='clinical';
  const params=new URLSearchParams();
  if(cfg.canadian){params.set('audience','canadian');if(data.practice_track)params.set('focus',data.practice_track)}
  const url=$('design-controls').dataset[key];
  const image=$('resume-sample-image'), assets=$('fields').dataset.layoutPreviews;
  const base=assets+(cfg.canadian?'canadian-':'')+key;
  const focused=cfg.canadian&&({pelvic:'clinical',sports:'classic',paediatric:'editorial'}[data.practice_track]===key);
  const samplePath=(focused?assets+'focus-'+data.practice_track:base+(!cfg.canadian&&samplePage===2?'-p2':''))+'.png?v=66';
  if(image.dataset.samplePath!==samplePath){
    image.dataset.samplePath=samplePath;
    image.onerror=()=>{
      image.onerror=null;
      if(samplePath!==base+'.png?v=66'){
        image.onerror=()=>{$('resume-sample-link').textContent='Open the design example as a PDF';};
        image.src=base+'.png?v=66';
      }else $('resume-sample-link').textContent='Open the design example as a PDF';
    };
    image.src=samplePath;
  }
  image.alt='Completed résumé example · '+key+' · page '+samplePage;
  $('sample-page').hidden=!!cfg.canadian;
  $('sample-page').textContent=samplePage===1?'Show page 2':'Show page 1';
  
  if($('download')&&cfg.paid_layouts)$('download').hidden=!cfg.paid_layouts.includes(key);
  if(url){const link=url+(params.size?'?'+params:'');$('resume-sample-link').href=link;$('resume-sample-pdf').href=link}
  document.querySelector('.preview-panel').dataset.example=String(show);$('resume-sample').hidden=!show;$('resume').hidden=show;
  $('preview-heading').textContent=show?'Design example':'Live draft';
  $('sample-toggle').textContent=show?'Back to live draft':'Show design example';
  $('sample-toggle').setAttribute('aria-pressed',String(show));
  $('resume-layout-select').value=key;
}
function canadianFields(p){
  if(step===0){
    field(p,'name','Full name',120);field(p,'location','City and province',180);field(p,'email','Email',180,'email');field(p,'phone','Phone',80);field(p,'profile_url','Professional profile link (optional)',300,'url');
    const select=el('select'), label=el('label','Practice focus');select.id='practice-focus';label.htmlFor=select.id;
    for(const [key,[name]] of Object.entries(cfg.tracks)){const o=el('option',name);o.value=key;select.append(o)}
    select.value=data.practice_track||'general';select.onchange=()=>{data.practice_track=select.value;mark();renderFields()};
    p.append(label,select,el('p',cfg.tracks[select.value]?.[1]||cfg.tracks.general[1],'help'));
    field(p,'target_role','Target role (optional)',110);field(p,'extra_heading','Custom section heading (optional)',80);field(p,'extra_text','Custom section content (optional)',1200,'textarea');field(p,'summary','Professional summary',1800,'textarea');
  }
  if(step===1){field(p,'home_registration','Canadian regulator, class and registration number (if held)',500,'textarea');specialtyPicker(p)}
  if(step===2)repeat(p,'canadian_experience','Clinical role');
  if(step===3)repeat(p,'education','Qualification');
  if(step===4)repeat(p,'development','Course or certification');
}
function specialtyPicker(parent){let box=el('fieldset',undefined,'specialty-picker');box.append(el('legend','Clinical interests and experience'));box.append(el('p','Select only areas you can describe from your own experience. These are interests, not specialist credentials.','help'));const options=el('div',undefined,'specialty-options');box.append(options);for(const name of ['Musculoskeletal','Sports rehabilitation','Pelvic health','Paediatrics','Neurological rehabilitation','Vestibular rehabilitation','Concussion rehabilitation','Older adults','Cardiorespiratory','Intensive care','Oncology rehabilitation','Lymphoedema care','Hand therapy','Persistent pain','Post-operative rehabilitation','Amputee rehabilitation','Occupational rehabilitation','Community care','Home care','Adaptive equipment and seating']){let label=el('label'),check=el('input');check.type='checkbox';check.checked=(data.specialties||'').split(', ').includes(name);check.onchange=()=>{let items=(data.specialties||'').split(', ').filter(Boolean).filter(x=>x!==name);if(check.checked)items.push(name);data.specialties=items.join(', ');const custom=box.querySelector('input[type=text]');if(custom)custom.value=data.specialties;mark()};label.append(check,document.createTextNode(name));options.append(label)}field(box,'specialties','Add or edit your clinical interests',600);parent.append(box)}
function bulletExamples(parent,row){let d=el('details',undefined,'example');d.append(el('summary','Add an example, then make it your own'));for(const text of ['Assessed mobility and functional goals, documented findings and reviewed progress with the care team.','Taught and adapted home exercises to suit patient goals, understanding and available equipment.','Contributed to discharge planning and coordinated follow-up with the multidisciplinary team.','Explained treatment plans and self-management strategies to patients and caregivers.']){let b=el('button',text,'bullet-example');b.type='button';b.onclick=()=>{const next=[row.bullets||'',text].filter(Boolean).join('\n');if(next.length>2500){alertError('This entry has reached its text limit. Edit an existing point first.');return}row.bullets=next;mark();renderFields()};d.append(b)}d.append(el('p','Use an example only if it reflects work you actually did. Replace it with your own wording and details.','help'));parent.append(d)}

async function navigateStep(next){if(next===step)return;try{await save();step=next;if(cfg.step_urls)history.replaceState(null,'',cfg.step_urls[next]);renderFields()}catch{}}
function el(tag,text,cls){let n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n}
function alertError(text){$('errors').hidden=!text;$('errors').textContent=text||''}
function mark(keepSample=false){sampleMode=keepSample===true;if(pdfProofUrl)$('pdf-proof-status').textContent='Draft changed. Reload the PDF proof to check the latest page breaks.';dirty=true;state('Unsaved changes',true);preview();clearTimeout(timer);if(!blocked)timer=setTimeout(()=>save().catch(()=>{}),900)}
function state(text,unsaved=false){$('save-state').textContent=text;$('save-state').classList.toggle('unsaved',unsaved)}
function field(parent,key,label,max=180,type='text',target=data,help=''){let box=el('div'),id='field-'+key+'-'+Math.random().toString(36).slice(2,8),l=el('label',label);l.htmlFor=id;let input=el(type==='textarea'?'textarea':'input');input.id=id;if(type!=='textarea')input.type=type;input.maxLength=max;const examples={setting:'Example: Outpatient MSK · adults and older adults',bullets:'Example: Assessed mobility and functional goals, documented findings and progressed home exercises under the role’s local scope.',language:'Example: English',proficiency:'Example: Professional working proficiency',evidence:'Example: IELTS Academic · test date · scores (if relevant)',course:'Example: Vestibular rehabilitation course',provider:'Course provider or institution',completed:'Month and year'};if(examples[key])input.placeholder=examples[key];input.value=target[key]||'';if(key==='email')input.autocomplete='email';if(key==='name')input.autocomplete='name';input.addEventListener('input',()=>{target[key]=input.value;mark()});box.append(l,input);if(help)box.append(el('p',help,'help'));parent.append(box);return input}
function choice(parent,key,label,help=''){let box=el('div'),l=el('label',label),s=el('select');s.id='choice-'+key;l.htmlFor=s.id;let initial=el('option','Choose your current status');initial.value='';s.append(initial);for(let v of cfg.choices[key]){let o=el('option',v);o.value=v;s.append(o)}s.value=data[key]||'';s.onchange=()=>{data[key]=s.value;mark();renderFields()};box.append(l,s);if(help)box.append(el('p',help,'help'));parent.append(box)}
function example(parent,title,text){let d=el('details',undefined,'example');d.append(el('summary',title),el('p',text));parent.append(d)}
function repeat(parent,key,label){let rows=data[key]||[];data[key]=rows;rows.forEach((r,i)=>{let section=el('section',undefined,'repeat');section.append(el('h3',label+' '+(i+1)));for(let [k,l,max,t] of groups[key]){field(section,k,l,max,t||'text',r);if(k==='bullets')bulletExamples(section,r);} let tools=el('div',undefined,'repeat-tools');for(let [text,delta] of [['Move up',-1],['Move down',1]]){let b=el('button',text);b.type='button';b.disabled=i+delta<0||i+delta>=rows.length;b.onclick=()=>{[rows[i],rows[i+delta]]=[rows[i+delta],rows[i]];mark();renderFields()};tools.append(b)}let remove=el('button','Remove');remove.type='button';remove.onclick=()=>{if(Object.values(r).some(Boolean)&&!confirm('Remove this entry from the draft?'))return;rows.splice(i,1);mark();renderFields()};tools.append(remove);section.append(tools);parent.append(section)});let add=el('button','+ Add '+label.toLowerCase(),'add');add.type='button';add.disabled=rows.length>=20;add.onclick=()=>{rows.push(Object.fromEntries(groups[key].map(([k])=>[k,''])));mark();renderFields()};parent.append(add)}
let completionErrors=cfg.completion_errors||[];
function showCompletion(){
  const panel=$('completion');
  if(!panel)return;
  panel.hidden=step!==lastStep||!completionErrors.length;
  if(!panel.hidden){
    const list=el('ul');list.append(...completionErrors.map(message=>el('li',message)));
    panel.replaceChildren(el('h3','Before downloading'),list);
  }
}
function renderFields(){$('draft-name-field').hidden=step!==lastStep;let p=$('fields');p.replaceChildren(el('h2',steps[step][0]),el('p',steps[step][1],'step-intro'));
if(cfg.canadian)canadianFields(p);else {
if(step===0){field(p,'name','Full name',120);field(p,'location','Current city and country',180);field(p,'email','Email',180,'email');field(p,'phone','Phone with country code',80);field(p,'profile_url','Professional profile link (optional)',300,'url');field(p,'education_country','Country / jurisdiction of physiotherapy education',100);field(p,'summary','Professional background',1800,'textarea',data,'Describe your qualification, relevant settings and clinical contributions, then state your current Canadian position accurately.');example(p,'How to write your introduction','Use two or three sentences: your qualification and experience, the patients and settings you have worked with, and the position you are seeking. Example: Physiotherapy graduate from the Philippines with outpatient and hospital experience. Clinical work includes mobility assessment, exercise instruction and discharge preparation. Seeking a rehabilitation role in British Columbia while completing Canadian registration requirements. Edit every statement to match your own background.');}
if(step===1){choice(p,'destination','Province or territory you are planning for');choice(p,'canadian_registration','Are you registered to practise physiotherapy in Canada?','Choose your actual current status. A submitted assessment or exam booking is a different step.');if(data.canadian_registration==='Registration held — enter exact class and conditions'){field(p,'regulator','Name of Canadian regulator',160);field(p,'registration_class','Registration class shown on your licence',160);field(p,'registration_number','Public registration number (optional)',80);field(p,'registration_conditions','Conditions or restrictions, if any',500,'textarea');}let toggle=el('label'),check=el('input');check.type='checkbox';check.checked=!!data.show_assessment_details;check.onchange=()=>{data.show_assessment_details=check.checked;mark();renderFields()};toggle.append(check,document.createTextNode('Include my assessment and exam progress on the resume'));p.append(toggle);if(data.show_assessment_details){choice(p,'pathway','Assessment route confirmed in your correspondence');choice(p,'assessment','Assessment progress');field(p,'assessment_detail','Decision or outstanding step (optional)',500,'textarea');if(data.pathway==='Comparability'){choice(p,'pet','Physiotherapy Evaluation Tool (PET) progress');field(p,'pet_detail','PET outcome or next step (optional)',500,'textarea');}choice(p,'exam','Examination progress');if(['Exam booked','Completed — awaiting result','Passed','Unsuccessful attempt — planning next step'].includes(data.exam))field(p,'exam_date','Exam date',10,'date');field(p,'exam_detail','Exam result or next step (optional)',500,'textarea');}field(p,'home_registration','Registration outside Canada',500,'textarea',data,'For example: authority name, country and whether your registration is current.');specialtyPicker(p);}
if(step===2){example(p,'See an example responsibility','Name the assessment, education, adaptation or team contribution you actually made. Explain the context and information that informed your action. Keep supervision accurate; do not invent patient outcomes or percentages.');repeat(p,'experience','Clinical role');}
if(step===3){repeat(p,'canadian_experience','Canadian role');p.append(el('p','For supervised Canadian training, use Placements. Add completed bridging or orientation courses under Professional development.','help'));}
if(step===4)repeat(p,'education','Qualification');
if(step===5){example(p,'Keep employment and supervised training separate','A placement can describe its setting, broad population, dates and supervised contributions. Record hours once and only from your documents; an entered total is not a credentialling assessment outcome.');repeat(p,'placements','Placement');}
if(step===6)repeat(p,'development','Course or certification');if(step===7)repeat(p,'languages','Language');
if(step===8){let l=el('label'),c=el('input');c.type='checkbox';c.checked=!!data.show_availability;c.onchange=()=>{data.show_availability=c.checked;mark()};l.append(c,document.createTextNode('Include availability on my resume'));p.append(l);field(p,'work_authorization','Current work authorization wording (optional)',300,'textarea');field(p,'relocation','Relocation availability or location preferences (optional)',300,'textarea');p.append(el('p','Only enter status you can accurately describe. Leave sensitive immigration identifiers out of the resume.','help'));}
}
if(step===lastStep){field(p,'extra_heading','Custom section heading (optional)',80);field(p,'extra_text','Custom section content (optional)',1200,'textarea');for(let [i,key] of data.section_order.entries()){let hasContent=key==='summary'?!!data.summary:key==='status'?lines().length>0:key==='home_registration'?!!data.home_registration:key==='availability'?!!data.show_availability:Array.isArray(data[key])&&data[key].some(r=>Object.values(r).some(Boolean));if(!hasContent)continue;let row=el('div',undefined,'order-row');row.append(el('span',orderNames[key]));let tools=el('div');for(let delta of [-1,1]){let b=el('button',delta<0?'↑':'↓');b.type='button';b.setAttribute('aria-label',(delta<0?'Move up ':'Move down ')+orderNames[key]);b.disabled=i+delta<0||i+delta>=data.section_order.length;b.onclick=()=>{[data.section_order[i],data.section_order[i+delta]]=[data.section_order[i+delta],data.section_order[i]];mark();renderFields()};tools.append(b)}row.append(tools);p.append(row)}p.append(el('p','Check dates, qualifications and registration details. Empty sections are left out. Open the PDF proof to check page breaks.','help'));}
showCompletion();document.querySelector('.purchase').hidden=false;$('mobile-section').value=String(step);$('previous').disabled=step===0;$('next').textContent=step===lastStep?'Save draft':'Next section';[...$('steps').children].forEach((b,i)=>{b.classList.toggle('active',i===step);if(i===step)b.setAttribute('aria-current','step');else b.removeAttribute('aria-current')});}
function lines(){let rows=[];if(cfg.canadian)return rows;if(data.destination)rows.push('Intended destination: '+data.destination);if(data.show_assessment_details&&data.pathway&&data.pathway!=='Not selected')rows.push('Assessment route: '+data.pathway);if(data.show_assessment_details&&data.assessment)rows.push('Credential assessment: '+data.assessment+(data.assessment_detail?' — '+data.assessment_detail:''));if(data.show_assessment_details&&data.pathway==='Comparability'&&data.pet&&data.pet!=='Not applicable / not confirmed')rows.push('PET: '+data.pet+(data.pet_detail?' — '+data.pet_detail:''));if(data.show_assessment_details&&data.exam&&data.exam!=='Not applicable / not confirmed')rows.push('Examination: '+data.exam+(data.exam_date?' · '+data.exam_date:'')+(data.exam_detail?' — '+data.exam_detail:''));if(data.canadian_registration)rows.push('Canadian registration: '+(data.canadian_registration==='Registration held — enter exact class and conditions'?[data.regulator,data.registration_class,data.registration_number?'Registration '+data.registration_number:'',data.registration_conditions].filter(Boolean).join(' | '):data.canadian_registration));return rows}
function preview(){samplePreview();let root=$('resume');root.dataset.audience=cfg.canadian?'canadian':'international';root.dataset.layout=data.layout||'classic';root.dataset.palette=data.palette||'original';root.dataset.typeface=data.typeface||'original';root.style.setProperty('--custom-resume-accent',data.accent_colour||'');const headerColour=data.header_colour||'';root.style.setProperty('--custom-resume-header',headerColour);let headerInk=data.accent_colour||'';if(!headerInk&&/^#[0-9a-f]{6}$/i.test(headerColour)){const [r,g,b]=headerColour.slice(1).match(/../g).map(x=>parseInt(x,16));if(.2126*r+.7152*g+.0722*b<127.5)headerInk='#ffffff'}root.style.setProperty('--custom-resume-header-ink',headerInk);root.replaceChildren(el('h2',data.name||'Your name'));let contact=[data.location,data.email,data.phone,data.profile_url].filter(Boolean).join(' | ');if(contact)root.append(el('p',contact,'meta'));const role=cfg.canadian?data.target_role:data.experience.find(row=>row.role)?.role;if(role)root.append(el('p',role,'resume-role'));if(data.education_country)root.append(el('p','Physiotherapy education: '+data.education_country,'meta'));if(data.specialties)root.append(el('p','Clinical interests: '+data.specialties,'meta'));let nonempty=false,currentKey;const sec=(title,nodes)=>{if(!nodes.length)return;nonempty=true;const section=el('section',undefined,'resume-section');section.dataset.section=currentKey;section.append(el('h3',title),...nodes);root.append(section)};for(let k of data.section_order){if((data.hidden_sections||[]).includes(k))continue;currentKey=k;if(k==='summary'&&data.summary)sec(orderNames[k],[el('p',data.summary)]);if(k==='status')sec(data.show_assessment_details?orderNames[k]:'Canadian registration',lines().map(x=>el('p',x)));if(k==='experience'||k==='canadian_experience'){let nodes=[];for(let r of data[k]){if(!Object.values(r).some(Boolean))continue;nodes.push(el('h4',[r.role,r.employer].filter(Boolean).join(' | ')),el('p',[k==='canadian_experience'?r.location:[r.location,r.country].filter(Boolean).join(', '),r.dates,r.setting].filter(Boolean).join(' · '),'meta'));let ul=el('ul');(r.bullets||'').split('\n').filter(x=>x.trim()).forEach(t=>ul.append(el('li',t.trim().replace(/^[•-]\s*/,''))));nodes.push(ul)}sec(orderNames[k],nodes)}if(k==='education')sec(orderNames[k],data.education.filter(r=>Object.values(r).some(Boolean)).map(r=>el('p',[r.degree,r.institution,r.country,r.completed].filter(Boolean).join(' | '))));if(k==='placements'){let nodes=[];for(let r of data.placements){if(!Object.values(r).some(Boolean))continue;nodes.push(el('h4',[r.institution,r.location,r.country,r.dates].filter(Boolean).join(' | ')));if(r.setting||r.hours)nodes.push(el('p',[r.setting,r.hours?r.hours+' documented supervised hours':''].filter(Boolean).join(' | '),'meta'));if(r.contribution)nodes.push(el('p',r.contribution))}sec(orderNames[k],nodes)}if(k==='home_registration'&&data.home_registration)sec(orderNames[k],[el('p',data.home_registration)]);if(k==='development')sec(orderNames[k],data.development.filter(r=>Object.values(r).some(Boolean)).map(r=>el('p',[r.course,r.provider,r.completed].filter(Boolean).join(' | '))));if(k==='languages')sec(orderNames[k],data.languages.filter(r=>Object.values(r).some(Boolean)).map(r=>el('p',[r.language,r.proficiency,r.evidence].filter(Boolean).join(' | '))));if(k==='availability'&&data.show_availability)sec(orderNames[k],[data.work_authorization?el('p','Work authorization: '+data.work_authorization):null,data.relocation?el('p','Relocation / availability: '+data.relocation):null].filter(Boolean));}if(data.extra_text){currentKey='custom';sec(data.extra_heading||'Additional information',[el('p',data.extra_text)]);}if(!nonempty)root.append(el('p','Add your details to see the resume take shape.','empty'));if(data.portrait){const photo=el('img',undefined,'resume-portrait');photo.src=data.portrait;photo.alt='';photo.style.maxWidth=(data.portrait_size||64)+'px';root.children[0].before(photo);}if(['clinical','editorial','sidebar'].includes(data.layout)){
  const side=el('div',undefined,'resume-sidebar'), content=el('div',undefined,'resume-main'), identity=el('div',undefined,'resume-identity');
  const nameNode=root.querySelector("h2");
  for(const node of [...root.children]){
    if(node===nameNode||node.classList.contains("resume-portrait")){identity.append(node);continue}
    const key=node.dataset.section;
    if(contact&&node.textContent===contact){
      if(data.layout==='editorial'){node.className='meta resume-contact-strip';identity.append(node);}
      else side.append(el('h3','Contact'),el('p',[data.location,data.email,data.phone,data.profile_url].filter(Boolean).join('\n')));
    }else if(node.textContent==='Clinical interests: '+data.specialties){
      const list=el('ul',undefined,'resume-interests');
      for(const interest of data.specialties.split(',').map(s=>s.trim()).filter(Boolean))list.append(el('li',interest));
      const interests=el('section',undefined,'resume-section');interests.append(el('h3','Clinical interests'),list);side.append(interests);
    }else if(['education','home_registration','development','languages'].includes(key))side.append(node);
    else if(node.classList.contains('resume-role'))identity.append(node);
    else content.append(node);
  }
  const columns=el('div',undefined,'resume-columns');
  if(!side.children.length)side.setAttribute('aria-hidden','true');
  if(cfg.canadian&&data.layout==='sidebar')columns.append(content,side);else columns.append(side,content);
  root.replaceChildren(identity,columns);
}}
async function save(){clearTimeout(timer);if(blocked)throw Error('Resolve the other-tab conflict before saving.');if(saving){await saving;if(dirty)return save();return}if(!dirty)return;const payload={title:$('draft-title').value,data:structuredClone(data),revision};dirty=false;state('Saving…');saving=(async()=>{try{let r=await fetch(cfg.save_url,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':csrf},body:JSON.stringify(payload)});let x;try{x=await r.json()}catch{throw Error('Could not save. Your session may have expired. Keep this page open and sign in in another tab.')}if(!r.ok){if(r.status===409)blocked=true;throw Error(x.error||'Could not save your draft.')}revision=x.revision;if(!dirty){if(Array.isArray(x.completion_errors)){completionErrors=x.completion_errors;showCompletion()}state((cfg.demo?'Preview updated at ':cfg.public?'Draft kept in this browser session at ':'Draft saved to your account at ')+new Date(x.saved_at).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'}));alertError('')}}catch(e){dirty=true;state('Not saved',true);alertError(e.message);throw e}finally{saving=null}})();await saving;if(dirty&&!blocked)return save();}
let pdfProofUrl='';
async function navigatePDF(url,download=false){
 const button=download?$('download'):$('proof');
 const status=$('pdf-proof-status');
 button.disabled=true;
 if(!download)status.textContent='Preparing your PDF proof…';
 try {
  await save();
  const options=cfg.public?{method:'POST',credentials:'same-origin',headers:{'X-CSRFToken':csrf}}:
    cfg.demo?{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':csrf},body:JSON.stringify({data,revision})}:{credentials:'same-origin'};
  const r=await fetch(url,options);
  const type=r.headers.get('Content-Type')||'';
  if(!r.ok){
    if(type.includes('json')){const x=await r.json();throw Error([x.error,...(x.fields||[])].join('\n'))}
    throw Error('Could not prepare the PDF. Check your session and try again.');
  }
  if(!type.includes('application/pdf'))throw Error('The PDF is unavailable. Check your session and try again.');
  const u=URL.createObjectURL(await r.blob());
  if(download){
    const a=el('a');a.href=u;a.download=(r.headers.get('Content-Disposition')||'').match(/filename="([^"]+)"/)?.[1]||'resume.pdf';
    a.click();setTimeout(()=>URL.revokeObjectURL(u),60000);
  }else{
    if(pdfProofUrl)URL.revokeObjectURL(pdfProofUrl);
    pdfProofUrl=u;const frame=$('pdf-proof-frame');frame.src=u;frame.hidden=false;
    status.textContent='PDF proof loaded below.';button.textContent='Reload PDF proof';
  }
 }catch(e){if(download)alertError(e.message);else status.textContent=e.message}
 finally{button.disabled=false}
}
for(let [i,s] of steps.entries()){let option=el('option',(i+1)+' of '+steps.length+' · '+s[0]);option.value=String(i);$('mobile-section').append(option);let b=el('button',(i+1)+'. '+s[0]);b.type='button';b.onclick=()=>navigateStep(i);$('steps').append(b)}for(let s of cfg.sources){let a=el('a',s.label);a.href=s.url;a.target='_blank';a.rel='noopener';let li=el('li');li.append(a);$('sources').append(li)}$('mobile-section').onchange=()=>navigateStep(Number($('mobile-section').value));$('draft-title').oninput=mark;$('previous').onclick=()=>{if(step>0)navigateStep(step-1)};$('next').onclick=()=>{if(step<lastStep)navigateStep(step+1);else save().catch(()=>{})};$('proof').onclick=()=>navigatePDF(cfg.preview_url);if($('download'))$('download').onclick=()=>navigatePDF(cfg.download_url,true);if(cfg.public&&cfg.claim_url){for(const link of document.querySelectorAll('a[href]')){const url=new URL(link.href,location.href);if(url.origin===location.origin&&(url.pathname===cfg.claim_url||url.searchParams.get('next')===cfg.claim_url)){link.addEventListener('click',async e=>{if(e.button!==0||e.ctrlKey||e.metaKey||e.shiftKey||e.altKey)return;e.preventDefault();try{await save();location.assign(url.href)}catch{}})}}}let purchase=$('purchase-form');if(purchase)purchase.addEventListener('submit',async e=>{e.preventDefault();try{await save();HTMLFormElement.prototype.submit.call(purchase)}catch{}});let manual=el('button',cfg.demo?'Update preview':'Save draft now','save-button');manual.type='button';manual.onclick=()=>{dirty=true;save().catch(()=>{})};$('steps').after(manual);window.addEventListener('beforeunload',e=>{if(dirty||saving){e.preventDefault();e.returnValue=''}});window.addEventListener('online',()=>{if(dirty&&!blocked)save().catch(()=>{})});sampleMode=!!cfg.public&&!data.portrait&&
 !['name','email','phone','location','summary','specialties','target_role','extra_text','home_registration','canadian_registration','education_country'].some(k=>String(data[k]||'').trim())&&
 !['education','experience','canadian_experience','placements','development','languages'].some(k=>data[k]?.some(row=>Object.values(row).some(Boolean)));
designPicker();$('sample-page').onclick=()=>{samplePage=samplePage===1?2:1;preview()};$('sample-toggle').onclick=()=>{sampleMode=!sampleMode;preview()};renderFields();preview();
})();
