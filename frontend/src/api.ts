import type { Alert, Filters, Machine, MachineDay, Summary, Trend } from './types'
const base = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1'
async function get<T>(path:string):Promise<T>{
  const response=await fetch(`${base}${path}`)
  if(!response.ok){const body=await response.json().catch(()=>({}));throw new Error(body.detail||`Request failed (${response.status})`)}
  return response.json()
}
export const api={
  filters:()=>get<Filters>('/filters'),
  summary:(q:string)=>get<Summary>(`/summary${q}`),
  trends:(q:string)=>get<{items:Trend[]}>(`/trends${q}`),
  machines:(q:string)=>get<{items:Machine[]}>(`/machines${q}`),
  machineDetail:(id:number,q:string)=>get<{machine:Machine;daily:MachineDay[]}>(`/machines/${id}${q}`),
  alerts:(plant:string,status:string,severity:string)=>{const q=new URLSearchParams();if(plant)q.set('plant_id',plant);if(status!=='all')q.set('status',status);if(severity!=='all')q.set('severity',severity);return get<{items:Alert[];count:number}>(`/alerts${q.size?`?${q}`:''}`)},
}
