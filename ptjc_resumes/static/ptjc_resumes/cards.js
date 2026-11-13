(()=>{'use strict';const c=JSON.parse(document.getElementById('card-bootstrap').textContent),$=id=>document.getElementById(id),csrf=document.querySelector('#csrf-form [name=csrfmiddlewaretoken]').value;let data=c.data,revision=c.revision,dirty=false,saving=null,timer,blocked=false;
const labels={name:'Full name',role:'Professional title',organization:'Organization',phone:'Phone',email:'Email',website:'Website',address:'Street address',city:'City, region and postal code',booking:'Booking link',background:'Clinical background or interests',status:'Actual Canadian registration status',education_country:'Country of physiotherapy education',profile:'Professional profile link',initials:'Initials for the monogram'};const limits={name:70,role:100,organization:100,phone:60,email:140,website:160,address:120,city:100,booking:160,background:140,status:140,education_country:80,profile:160,initials:5};
function error(message){$('card-error').hidden=!message;$('card-error').textContent=message||''}function mark(){dirty=true;$('card-state').textContent='Unsaved changes';clearTimeout(timer);if(!blocked)timer=setTimeout(()=>save().catch(()=>{}),800)}
async function save(){clearTimeout(timer);if(blocked)throw Error('Reload before editing this card.');if(saving){await saving;if(dirty)return save();return}if(!dirty)return;if(c.demo){dirty=false;await proof();if(!dirty)$('card-state').textContent='Preview updated';return}const payload={data:structuredClone(data),revision};dirty=false;$('card-state').textContent='Saving…';saving=(async()=>{try{const r=await fetch(c.save_url,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':csrf},body:JSON.stringify(payload)});const x=await r.json();if(!r.ok){if(r.status===409)blocked=true;throw Error(x.error||'Save failed.')}revision=x.revision;if(!dirty){$('card-state').textContent='Draft saved to your account · '+new Date().toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'});error('');proof().catch(()=>{})}}catch(e){dirty=true;$('card-state').textContent='Not saved';error(e.message);throw e}finally{saving=null}})();await saving;if(dirty&&!blocked)return save()}
let proofVersion=0;
async function proof(){
 const version=++proofVersion,sides=['front','back'];
 try{
  if(!c.demo){for(const side of sides)$('card-'+side).src=c.preview_url+'?side='+side+'&v='+revision;return}
  const body=JSON.stringify({data});
  const blobs=await Promise.all(sides.map(async side=>{
   const r=await fetch(c.preview_url+'?side='+side,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':csrf},body});
   if(!r.ok)throw Error('Preview could not be generated. Try again.');
   return r.blob();
  }));
  if(version!==proofVersion)return;
  error('');
  sides.forEach((side,i)=>{
   const img=$('card-'+side),old=img.dataset.blob,url=URL.createObjectURL(blobs[i]);
   img.src=url;img.dataset.blob=url;if(old)URL.revokeObjectURL(old);
  });
 }catch(e){if(version===proofVersion){error(e.message);throw e}}
}
for(const [key,label] of Object.entries(labels)){const box=document.createElement('div');box.dataset.field=key;const l=document.createElement('label'),input=document.createElement('input');input.id='card-'+key;l.htmlFor=input.id;l.textContent=label;input.value=data[key]||'';input.maxLength=limits[key];input.oninput=()=>{data[key]=input.value;mark()};box.append(l,input);$('card-fields').append(box)}$('card-design').value=data.design;$('card-design').onchange=()=>{data.design=$('card-design').value;showFields();mark();save().catch(()=>{})};function change(key,value){data[key]=value;mark()}
for(const key of ['extra','typeface']){
 const input=$('card-'+key);if(data[key])input.value=data[key];
 input.oninput=()=>change(key,input.value);
}
const colourDefaults={paper:'#ffffff',ink:'#243039',accent:'#326173'};
const palettes={
 ink:['#ffffff','#18232b','#a9bbc8'], sage:['#f8f5ea','#263f33','#a8b6a0'],
 navy:['#eff6ff','#172e52','#91b5d8'], berry:['#fff2f5','#542435','#cc849e'],
 clay:['#fbf3e9','#512d20','#c28260'], forest:['#eaf5ed','#193f31','#76ae91'],
 cobalt:['#f1f4ff','#243269','#7b91df'], plum:['#f7effb','#3e264f','#af93c2'],
 mono:['#fcfaf3','#222222','#a5a096'],
};
const colourKeys=Object.keys(colourDefaults);
function syncColours(){
 for(const key of colourKeys){
  $('card-'+key).value=data[key]||colourDefaults[key];
  const hex=$('card-'+key+'-hex');
  hex.value=data[key]||'';
  hex.setCustomValidity('');
 }
}
syncColours();
$('card-palette').onchange=()=>{
 const colours=palettes[$('card-palette').value];
 if(!colours)return;
 colourKeys.forEach((key,i)=>data[key]=colours[i]);syncColours();mark();
};
for(const key of colourKeys){
 const picker=$('card-'+key),hex=$('card-'+key+'-hex');
 picker.oninput=()=>{
  hex.value=picker.value;hex.setCustomValidity('');$('card-palette').value='';change(key,picker.value);
 };
 hex.oninput=()=>{
  const raw=hex.value.trim(), value=raw && (raw.startsWith('#')?raw:'#'+raw);
  if(value&&!/^#[0-9a-f]{6}$/i.test(value)){hex.setCustomValidity('Enter six hexadecimal digits, for example #16344a.');return;}
  hex.setCustomValidity('');picker.value=value||colourDefaults[key];$('card-palette').value='';change(key,value);
 };
 hex.onchange=()=>{if(!hex.checkValidity())hex.reportValidity()};
}
$('card-reset-style').onclick=()=>{
 colourKeys.forEach(key=>data[key]='');data.typeface='original';$('card-typeface').value='original';
 $('card-palette').value='';syncColours();mark();
};
const fieldOptions=$('card-field-options');
for(const [key,label] of Object.entries(labels)){
 const row=document.createElement('label'),toggle=document.createElement('input');toggle.type='checkbox';toggle.checked=!(data.hidden||[]).includes(key);
 toggle.onchange=()=>{const hidden=new Set(data.hidden||[]);if(toggle.checked)hidden.delete(key);else hidden.add(key);change('hidden',[...hidden]);showFields()};
 row.append(toggle,document.createTextNode(label));fieldOptions.append(row);
}
if($('card-keep'))$('card-keep').onclick=async()=>{
 try{const r=await fetch(c.keep_url,{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json','X-CSRFToken':csrf},body:JSON.stringify({data})});
 const response=await r.json();if(!r.ok)throw Error(response.error||'Card could not be saved.');
 if(response.url){dirty=false;location.assign(response.url);return;}
 const options=$('card-account-options');options.hidden=false;options.querySelector('a').focus();
 }catch(e){error(e.message)}
};
if($('card-save-now'))$('card-save-now').onclick=async()=>{try{await save();$('card-state').textContent='Draft saved'}catch(e){error(e.message)}};
for(const side of ['front','back']){
 const input=$('art-'+side), key=side+'_art', placement=$('placement-'+side);
 placement.value=data[side+'_placement']||'right';
 for(const layer of ['art','text'])for(const axis of ['x','y']){
  const control=$(side+'-'+layer+'-'+axis),field=side+'_'+layer+'_'+axis;
  control.value=data[field]||0;control.oninput=()=>change(field,Number(control.value));
 }
 const scale=$('scale-'+side), remove=$('remove-'+side), size=$('size-'+side);
 scale.value=data[side+'_scale']||100;
 let uploadVersion=0;
 function syncArtwork(){
  const hasArt=Boolean(data[key]);
  remove.disabled=scale.disabled=placement.disabled=!hasArt;
  $(side+'-art-x').disabled=$(side+'-art-y').disabled=!hasArt;
  $(side+'-text-x').disabled=$(side+'-text-y').disabled=hasArt&&placement.value==='full';
  size.textContent=scale.value+'%';
 }
 syncArtwork();
 scale.oninput=()=>{change(side+'_scale',Number(scale.value));syncArtwork()};
 scale.onchange=()=>save().catch(e=>error(e.message));
 placement.onchange=()=>{
  data[side+'_placement']=placement.value;
  if(placement.value==='full'){data[side+'_scale']=100;scale.value=100;}
  syncArtwork();mark();save().catch(e=>error(e.message))
 };
 input.onchange=async()=>{const file=input.files[0];if(!file)return;const version=++uploadVersion;let image;try{
 if(!['image/png','image/jpeg'].includes(file.type)||file.size>12000000)throw Error('Choose a PNG or JPEG smaller than 12 MB.');
 image=await createImageBitmap(file);const canvas=document.createElement('canvas'),scale=Math.min(1,1050/Math.max(image.width,image.height));
 canvas.width=Math.max(1,Math.round(image.width*scale));canvas.height=Math.max(1,Math.round(image.height*scale));
 canvas.getContext('2d').drawImage(image,0,0,canvas.width,canvas.height);
 let art=canvas.toDataURL(file.type,.88);
 if(art.length>270000&&file.type==='image/jpeg')art=canvas.toDataURL(file.type,.73);
 if(art.length>270000){const reduced=document.createElement('canvas');reduced.width=Math.max(1,Math.round(canvas.width*.65));reduced.height=Math.max(1,Math.round(canvas.height*.65));reduced.getContext('2d').drawImage(canvas,0,0,reduced.width,reduced.height);art=reduced.toDataURL(file.type,.78);}
 if(art.length>270000)throw Error('Choose a smaller image.');if(version!==uploadVersion)return;data[key]=art;syncArtwork();mark();await save();
 }catch(e){if(version===uploadVersion)error(e.message)}finally{image?.close();if(version===uploadVersion)input.value=''}};
 remove.onclick=()=>{uploadVersion++;data[key]='';input.value='';syncArtwork();mark();save().catch(e=>error(e.message))};
}if($('card-purchase'))$('card-purchase').onsubmit=async e=>{e.preventDefault();try{await save();HTMLFormElement.prototype.submit.call($('card-purchase'))}catch{}};if($('card-download'))$('card-download').onclick=async()=>{try{await save();location.assign(c.download_url)}catch{}};window.addEventListener('beforeunload',e=>{if(dirty||saving){e.preventDefault();e.returnValue=''}});function showFields(){
 const supported={clinical:['name','role','organization','phone','email','website','address','city','booking','initials'],community:['name','role','organization','phone','email','website','address','city','booking'],editorial:['name','role','organization','phone','email','website','address','city','booking'],networking:['name','role','organization','phone','email','education_country','background','status','profile']}[data.design]||[];
 for(const box of document.querySelectorAll('[data-field]'))box.hidden=!supported.includes(box.dataset.field)||(data.hidden||[]).includes(box.dataset.field);
 [...fieldOptions.children].forEach((node,i)=>node.hidden=!supported.includes(Object.keys(labels)[i]));
}for(const b of document.querySelectorAll('[data-card-view]'))b.onclick=async()=>{try{await save();$('card-workspace').dataset.view=b.dataset.cardView}catch{}};showFields();proof().catch(()=>{});})();
