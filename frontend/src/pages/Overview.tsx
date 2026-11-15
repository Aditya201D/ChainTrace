import { Link } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { ArrowRight, ArrowUpRight, Box, CircleCheck, Database, GitBranch, ShieldCheck, Waypoints } from 'lucide-react'
import { api } from '../api'
import { ArtifactTable, NumberText, Panel, Pill, State } from '../components/Ui'
import { SkeletonStatCard, SkeletonTable } from '../components/Skeleton'
import { TYPES } from '../types'

const stages = [
  { n: '01', label: 'REGISTER', name: 'Dataset' },
  { n: '02', label: 'TRAIN', name: 'Training run' },
  { n: '03', label: 'ATTEST', name: 'Model' },
  { n: '04', label: 'RELEASE', name: 'Deployment' },
]

export default function Overview() {
  const overview = useQuery({ queryKey: ['overview'], queryFn: api.overview })
  const status = useQuery({ queryKey: ['chainStatus'], queryFn: api.status })
  const counts = overview.data?.by_type
  const stats = [
    { name: 'Indexed artifacts', val: overview.data?.total_artifacts, detail: 'Across all asset types', icon: Database },
    { name: 'Models', val: counts?.Model, detail: 'Known to local registry', icon: Box },
    { name: 'Training runs', val: counts?.TrainingRun, detail: 'Tracked training manifests', icon: GitBranch },
    { name: 'Deployments', val: counts?.Deployment, detail: 'Deployment records', icon: ShieldCheck },
  ]
  const online = Boolean(status.data?.rpc_connected && status.data.contract_deployed)

  return <div className="page-container">
    <div className="overview-hero reveal">
      <div className="hero-grid" aria-hidden="true"/>
      <div className="hero-copy"><span className="hero-eyebrow"><span className="hero-eyebrow-line"/> CHAINTRACE / OVERVIEW</span>
        <h1>Trust has a <em>trace.</em></h1>
        <p>Follow every model from source data to deployment. Verify artifacts, inspect lineage, and check the approvals behind each release.</p>
        <div className="hero-actions"><Link className="btn btn-primary" to="/lineage">Explore provenance <ArrowUpRight size={16}/></Link><Link className="btn btn-quiet" to="/verify">Verify deployment <ArrowRight size={16}/></Link></div>
      </div>
      <div className="hero-visual" aria-hidden="true">
        <div className="trace-caption">TRUST CHAIN <span>01 — 04</span></div>
        <div className="trace-spine"/>
        {stages.map((stage, i) => <div className="trace-step" key={stage.n} style={{ animationDelay: `${i * .13}s` }}><span className="trace-no">{stage.n}</span><span className="trace-indicator"><span/></span><div><small>{stage.label}</small><strong>{stage.name}</strong></div><CircleCheck size={15}/></div>)}
        <div className="trace-technical">PROVENANCE GRAPH / VERIFIED RELATIONSHIPS</div>
      </div>
    </div>

    <div className="overview-meta"><span>NETWORK HEALTH <Pill label={status.isLoading ? 'Checking' : online ? 'Operational' : 'Unavailable'} variant={status.isLoading ? 'muted' : online ? 'good' : 'bad'} /></span><span className="overview-meta-right">Data below reflects <b>SQLite index</b>; verify records individually against the chain.</span></div>

    <div className="stat-grid">{overview.isLoading ? Array.from({ length: 4 }).map((_, i) => <SkeletonStatCard key={i} />) : stats.map(({ name, val, detail, icon: Icon }, i) => <div className="stat-card reveal" key={name} style={{ animationDelay: `${i * .06}s` }}><div className="stat-top"><span>{name}</span><Icon size={18}/></div><div className="stat-value"><NumberText value={val}/></div><div className="stat-detail">{detail}</div></div>)}</div>
    <div className="overview-bottom"><Panel className="recent-panel" title="Recent artifacts" sub="Latest activity in the local registry" action={<Link className="text-action" to="/artifacts">View registry <ArrowUpRight size={14}/></Link>}>
      {overview.isLoading ? <SkeletonTable rows={5}/> : overview.isError ? <State type="error" message={(overview.error as Error).message}/> : <ArtifactTable artifacts={overview.data?.recent_artifacts || []}/>}
    </Panel><div className="overview-side"><Panel title="Registry composition" sub="Artifacts by type"><div className="composition-list">{TYPES.map((type, i) => <div className="composition-row" key={type}><div className="composition-label"><span>{type === 'TrainingRun' ? 'Training run' : type === 'ContainerImage' ? 'Container image' : type}</span><b>{counts?.[type] ?? '—'}</b></div><div className="composition-track"><div style={{width: counts && overview.data?.total_artifacts ? `${(counts[type] / overview.data.total_artifacts) * 100}%` : '0%', background: ['#75cce0','#838ef6','#83dbc1','#d4a5dd','#e4bd83'][i]}}/></div></div>)}</div></Panel>
    <div className="info-panel"><div className="info-panel-mark"><Waypoints size={21}/></div><h3>Provenance is more than a hash.</h3><p>Integrity checks establish that the files match recorded hashes. Independent evaluation and authorized attestations remain separate decisions.</p><Link to="/verify">View verification portal <ArrowRight size={15}/></Link></div></div></div>
  </div>
}
