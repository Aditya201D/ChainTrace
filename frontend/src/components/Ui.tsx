import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { ArrowUpRight, Check, CheckCircle2, CircleDashed, Clipboard, File, FileArchive, FileCode2, Layers, Server, Shield, XCircle } from 'lucide-react'
import type { Artifact, ArtifactType } from '../types'

export const iconForType: Record<ArtifactType, typeof File> = {
  Dataset: File,
  TrainingRun: FileCode2,
  Model: Layers,
  ContainerImage: FileArchive,
  Deployment: Server,
}
export const displayType: Record<ArtifactType, string> = {
  Dataset: 'Dataset', TrainingRun: 'Training run', Model: 'Model', ContainerImage: 'Container image', Deployment: 'Deployment'
}

export function Short({ value, start = 10, end = 6 }: { value: string; start?: number; end?: number }) {
  return <span className="mono" title={value}>{value.length > start + end + 2 ? value.slice(0, start) + '…' + value.slice(-end) : value}</span>
}
export function Copy({ value, children }: { value: string; children?: ReactNode }) {
  const handle = async () => { try { await navigator.clipboard.writeText(value) } catch { /* clipboard permission denied */ } }
  return <button type="button" className="copy-btn" title="Copy to clipboard" onClick={handle}>{children || <Clipboard size={14} />}</button>
}
export function Pill({ label, variant = 'muted', dot = true }: { label: string; variant?: 'good' | 'bad' | 'warn' | 'muted' | 'cyan'; dot?: boolean }) {
  return <span className={'pill pill-' + variant}>{dot && <span className="pill-dot" />}{label}</span>
}
export function Heading({ eyebrow, title, desc, action }: { eyebrow: string; title: string; desc?: string; action?: ReactNode }) {
  return <header className="page-heading reveal"><div><div className="eyebrow">{eyebrow}</div><h1>{title}</h1>{desc && <p>{desc}</p>}</div>{action && <div className="page-action">{action}</div>}</header>
}
export function Panel({ title, sub, action, children, className = '' }: { title?: string; sub?: string; action?: ReactNode; children: ReactNode; className?: string }) {
  return <section className={'panel ' + className}>{title && <div className="panel-head"><div><h2>{title}</h2>{sub && <p>{sub}</p>}</div>{action}</div>}{children}</section>
}
export function State({ type, message }: { type: 'loading' | 'error' | 'empty'; message: string }) {
  const Icon = type === 'error' ? XCircle : type === 'loading' ? CircleDashed : Shield
  return <div className={'state-view state-' + type}><Icon size={23} className={type === 'loading' ? 'spin' : ''}/><p>{message}</p></div>
}
export function ArtifactTable({ artifacts, showAll = false }: { artifacts: Artifact[]; showAll?: boolean }) {
  if (!artifacts.length) return <State type="empty" message="No artifacts in this view yet." />
  return <div className="table-scroll"><table className="artifact-table"><thead><tr><th>Artifact</th><th>Identifier</th><th>Added</th><th>Record</th><th></th></tr></thead><tbody>{artifacts.map(artifact => {
    const Icon = iconForType[artifact.artifact_type]
    return <tr key={artifact.artifact_id}>
      <td><div className="artifact-cell"><span className="file-symbol"><Icon size={17}/></span><div><strong>{displayType[artifact.artifact_type]}</strong><small title={artifact.original_filename}>{artifact.original_filename}</small></div></div></td>
      <td><Short value={artifact.artifact_id} start={showAll ? 17 : 13} end={5} /></td>
      <td className="quiet">{new Date(artifact.uploaded_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' })}</td>
      <td><Pill label={artifact.chain_registered ? 'DB confirmed' : 'Local only'} variant={artifact.chain_registered ? 'good' : 'muted'} /></td>
      <td><Link to={`/artifacts?inspect=${encodeURIComponent(artifact.artifact_id)}`} className="table-action" title="Inspect artifact"><ArrowUpRight size={16}/></Link></td>
    </tr>
  })}</tbody></table></div>
}
export function Flag({ good, label }: { good: boolean; label: string }) {
  return <div className={'flag ' + (good ? 'flag-good' : 'flag-bad')}>{good ? <CheckCircle2 size={16}/> : <XCircle size={16}/>}<span>{label}</span></div>
}
export function NumberText({ value }: { value: number | undefined }) { return <>{value === undefined ? '—' : value.toLocaleString()}</> }
export function formatBytes(bytes: number) { return bytes > 1024 ** 2 ? `${(bytes / 1024 ** 2).toFixed(1)} MB` : bytes > 1024 ? `${(bytes / 1024).toFixed(1)} KB` : `${bytes} B` }
export function EmptyMark() { return <Check size={16} /> }
