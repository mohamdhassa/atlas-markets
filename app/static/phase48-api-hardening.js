(()=>{
function formatDetail(value){
 if(value==null)return '';
 if(typeof value==='string')return value;
 if(Array.isArray(value))return value.map(formatDetail).filter(Boolean).join(' · ');
 if(typeof value==='object'){
  if(value.msg){const loc=Array.isArray(value.loc)?value.loc.join('.'):'',msg=String(value.msg);return loc?`${loc}: ${msg}`:msg}
  if(value.detail)return formatDetail(value.detail);
  if(value.error)return formatDetail(value.error);
  try{return JSON.stringify(value)}catch{return String(value)}
 }
 return String(value)
}
window.api=async function(path,options={}){
 const headers={...(options.headers||{})};if(options.body&&!headers['Content-Type'])headers['Content-Type']='application/json';const token=localStorage.getItem('atlas_token');if(token)headers.Authorization=`Bearer ${token}`;
 const res=await fetch(path,{...options,headers});if(res.status===204)return null;let data=null;try{data=await res.json()}catch{}
 if(!res.ok){const detail=formatDetail(data?.detail||data?.error||data)||`Request failed (${res.status})`;throw new Error(detail)}
 return data
};
window.AtlasPhase48={formatDetail};
})();