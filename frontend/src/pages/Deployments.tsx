import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowRight, Boxes, ShieldCheck, ShieldQuestion, TimerReset } from 'lucide-react'
import { api } from '../api'
import { Heading, Panel, Pill, State } from '../components/Ui'

export default function Deployments() {
  const [selected, setSelected] = useState('')
  const deployments = useQuery({queryKey:['artifacts','Deployment'],queryFn:()=>api.artifacts('Deployment')})
  const rows = deployments.data?.items||[]
  const chosen = rows.some(d=>d.artifact_id===selected)?selected:rows[0]?.artifact_id
  const check = useQuery({queryKey:['deploymentCheck',chosen],queryFn:()=>api.verifyDeployment(chosen!),enabled:!!chosen,retry:false})
  const trusted = check.data?.trusted_for_current_policy
  return <div className="page-container"><Heading eyebrow="OPERATIONS / DEPLOYMENTS" title="Release inventory" desc="Inspect deployment records and evaluate the release lineage behind each one." action={<Link to="/verify" className="btn btn-primary">Verify deployment <ArrowRight size={16}/></Link>}/>
    <div className="deploy-layout"><Panel title="Deployment records" sub="Indexed in the local registry"><div className="deploy-items">{deployments.isPending?<State type="loading" message="Loading deployments…"/>:deployments.isError?<State type="error" message={(deployments.error as Error).message}/>:rows.length===0?<State type="empty" message="No deployments registered yet."/>:rows.map(d=><button className={'deploy-row '+(chosen===d.artifact_id?'selected':'')} key={d.artifact_id} onClick={()=>setSelected(d.artifact_id)}><span className="deploy-icon"><Boxes size={19}/></span><span><strong>{d.original_filename}</strong><small>{d.artifact_id}</small></span><span className="deploy-arrow">→</span></button>)}</div></Panel>
    <div className="deploy-main"><Panel title="Deployment health" sub="Current state according to verification policy">{!chosen?<State type="empty" message="Select a deployment to inspect."/>:check.isPending?<State type="loading" message="Verifying the complete release chain…"/>:check.isError?<State type="error" message={(check.error as Error).message}/>:<><div className={'deploy-verdict '+(trusted?'trusted':'untrusted')}><div className="deploy-emblem">{trusted?<ShieldCheck size={29}/>:<ShieldQuestion size={29}/>}</div><div><span>CONSUMER TRUST POLICY</span><h3>{trusted?'Verification passed':'Requires attention'}</h3><p>{trusted?'Recorded lineage, integrity and current approval meet the policy.':'At least one current trust requirement was not met.'}</p></div></div><div className="deploy-checks"><div><span>Lineage</span><Pill label={check.data?.lineage_complete?'Complete':'Incomplete'} variant={check.data?.lineage_complete?'good':'bad'}/></div><div><span>File integrity</span><Pill label={check.data?.provenance_integrity_verified?'Verified':'Failed'} variant={check.data?.provenance_integrity_verified?'good':'bad'}/></div><div><span>Audit approval</span><Pill label={check.data?.approval_active_now?'Active':'Inactive'} variant={check.data?.approval_active_now?'good':'bad'}/></div></div><Link className="btn btn-secondary btn-full" to={`/verify?id=${encodeURIComponent(chosen)}`}>Full verification report <ArrowRight size={15}/></Link></> }</Panel><div className="info-panel compact"><TimerReset size={20}/><p><b>Live service status is not monitored.</b> This page verifies the recorded deployment artifact and its declared provenance, not whether a model-serving endpoint is currently online.</p></div></div></div>
  </div>
}
