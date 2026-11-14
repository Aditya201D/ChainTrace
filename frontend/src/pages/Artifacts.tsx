import { useMemo, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useSearchParams } from 'react-router-dom'
import { ArrowUpRight, CheckCircle2, CloudUpload, FileCheck2, FileUp, Search, X } from 'lucide-react'
import { api } from '../api'
import { ArtifactTable, Copy, Flag, formatBytes, Heading, Panel, Pill, State } from '../components/Ui'
import { TYPES, type Artifact, type ArtifactType } from '../types'

export default function Artifacts() {
  const [filter, setFilter] = useState<ArtifactType | 'All'>('All')
  const [search, setSearch] = useState('')
  const [isUploadOpen, setUploadOpen] = useState(false)
  const [params, setParams] = useSearchParams()
  const [file, setFile] = useState<File | null>(null)
  const [type, setType] = useState<ArtifactType>('Dataset')
  const [uploadResult, setUploadResult] = useState<Artifact | null>(null)
  const inputRef = useRef<HTMLInputElement>(null)
  const queryClient = useQueryClient()
  const artifacts = useQuery({ queryKey: ['artifacts', filter], queryFn: () => api.artifacts(filter) })
  const inspect = params.get('inspect')
  const inspection = useQuery({ queryKey: ['artifactInspect', inspect], queryFn: () => api.verifyArtifact(inspect!), enabled: !!inspect, retry: false })
  const upload = useMutation({ mutationFn: () => api.upload(file!, type), onSuccess: async (artifact) => { setUploadResult(artifact); setFile(null); await queryClient.invalidateQueries({queryKey:['artifacts']}); await queryClient.invalidateQueries({queryKey:['overview']}) } })
  const rows = useMemo(() => (artifacts.data?.items || []).filter(a => (a.artifact_id + a.original_filename).toLowerCase().includes(search.trim().toLowerCase())), [artifacts.data, search])

  const closeInspect = () => { setParams(prev => { prev.delete('inspect'); return prev }) }
  return <div className="page-container">
    <Heading eyebrow="REGISTRY / ASSETS" title="Artifact registry" desc="Find and inspect the immutable references behind every model release." action={<button className="btn btn-primary" onClick={() => {setUploadResult(null); setUploadOpen(true)}}><FileUp size={16}/> Upload artifact</button>}/>
    <div className="summary-strip"><span><FileCheck2 size={16}/> SHA-256 fingerprints stored off-chain and anchored by on-chain hashes.</span><span className="mono">INDEXED: {artifacts.data?.total ?? '—'}</span></div>
    <Panel className="registry-panel">
      <div className="registry-controls"><div className="filter-tabs">{(['All',...TYPES] as const).map(item => <button type="button" key={item} onClick={()=>setFilter(item)} className={'filter-tab '+(filter===item?'selected':'')}>{item === 'TrainingRun' ? 'Training runs' : item === 'ContainerImage' ? 'Containers' : item === 'All' ? 'All artifacts' : item+'s'}</button>)}</div><label className="search-field"><Search size={16}/><input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Search ID or filename" aria-label="Search artifacts"/></label></div>
      {artifacts.isLoading ? <State type="loading" message="Querying local registry…"/> : artifacts.isError ? <State type="error" message={(artifacts.error as Error).message}/> : <ArtifactTable artifacts={rows} showAll/>}
      <div className="table-footer">Showing {rows.length} of {artifacts.data?.total ?? 0} indexed artifacts (up to 200 per view). <span>Chain status is verified on inspection.</span></div>
    </Panel>
    {inspect && <div className="drawer-scrim" onMouseDown={closeInspect}><aside className="detail-drawer" onMouseDown={e=>e.stopPropagation()}><div className="drawer-head"><div><span className="eyebrow">ARTIFACT / VERIFICATION</span><h2>Integrity report</h2></div><button className="icon-button" onClick={closeInspect}><X size={18}/></button></div><div className="drawer-body"><div className="mono id-chip">{inspect}<Copy value={inspect}/></div>
      {inspection.isPending ? <State type="loading" message="Checking stored file and blockchain…"/> : inspection.isError ? <State type="error" message={(inspection.error as Error).message}/> : <><div className="drawer-status"><Pill variant={inspection.data.verification.overall_verified?'good':'bad'} label={inspection.data.verification.overall_verified?'Integrity verified':'Verification failed'}/></div><div className="check-list"><Flag good={inspection.data.verification.file_exists} label="Stored file exists"/><Flag good={inspection.data.verification.local_hash_matches_database} label="File matches database fingerprint"/><Flag good={inspection.data.verification.blockchain_record_exists} label="Artifact exists on-chain"/><Flag good={inspection.data.verification.blockchain_hash_matches_database} label="On-chain hash matches database"/></div><div className="detail-section"><span className="detail-label">RECORDED SHA-256</span><div className="hash-box mono">{inspection.data.hashes.database_hash}<Copy value={inspection.data.hashes.database_hash}/></div></div><div className="detail-section"><span className="detail-label">BLOCKCHAIN HASH</span><div className="hash-box mono">{inspection.data.hashes.blockchain_hash || 'Not available'}</div></div></>}
      </div></aside></div>}

    {isUploadOpen && <div className="modal-shade" onMouseDown={()=>setUploadOpen(false)}><div className="modal" onMouseDown={e=>e.stopPropagation()}><div className="modal-header"><div><span className="eyebrow">NEW ARTIFACT</span><h2>Upload to registry</h2></div><button className="icon-button" onClick={()=>setUploadOpen(false)}><X size={18}/></button></div>{uploadResult ? <div className="upload-done"><CheckCircle2 size={32}/><h3>File stored successfully</h3><p>Artifact uploaded and hashed. On-chain registration remains a separate, wallet-authorized step.</p><div className="id-chip mono">{uploadResult.artifact_id}<Copy value={uploadResult.artifact_id}/></div><button className="btn btn-primary" onClick={()=>setUploadOpen(false)}>Done <ArrowUpRight size={15}/></button></div> : <div className="upload-form"><label className="field-label" htmlFor="artifact-kind">Artifact type</label><select className="select" id="artifact-kind" value={type} onChange={e=>setType(e.target.value as ArtifactType)}>{TYPES.map(t=><option key={t} value={t}>{t}</option>)}</select><input ref={inputRef} type="file" hidden onChange={e=>setFile(e.target.files?.[0]||null)}/><button className={'drop-target '+(file?'has-file':'')} onClick={()=>inputRef.current?.click()} onDragOver={e=>e.preventDefault()} onDrop={e=>{e.preventDefault();setFile(e.dataTransfer.files?.[0]||null)}}><CloudUpload size={29}/><strong>{file?file.name:'Choose a file or drag it here'}</strong><span>{file?formatBytes(file.size):'Stored locally; SHA-256 is calculated on upload'}</span></button><div className="modal-note">This uploads the file to FastAPI and SQLite. Blockchain signing is introduced in the MetaMask phase.</div>{upload.isError && <p className="form-error">{(upload.error as Error).message}</p>}<button disabled={!file || upload.isPending} className="btn btn-primary btn-full" onClick={()=>upload.mutate()}>{upload.isPending?'Uploading…':'Upload artifact'} <ArrowUpRight size={16}/></button></div>}</div></div>}
  </div>
}
