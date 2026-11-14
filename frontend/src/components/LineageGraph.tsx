import { useMemo, useState } from 'react'
import { ReactFlow, Background, Controls, Handle, Position, type Edge, type Node, type NodeProps } from '@xyflow/react'
import { Check, CircleAlert, Database, FileCode2, Layers, Package, RadioTower } from 'lucide-react'
import { Copy, Short } from './Ui'
import type { Check as ArtifactCheck, ConsumerReport, ModelReport, Relationship } from '../types'

const order: Record<string, number> = { Dataset: 0, TrainingRun: 1, Model: 2, ContainerImage: 3, Deployment: 4 }
const icons: Record<string, typeof Database> = { Dataset: Database, TrainingRun: FileCode2, Model: Layers, ContainerImage: Package, Deployment: RadioTower }
type StageData = { label: string; artifactId: string; verified: boolean; stage: number; [key: string]: unknown }
type StageNode = Node<StageData, 'stage'>

function Stage({ data, selected }: NodeProps<StageNode>) {
  const Icon = icons[data.label] || Layers
  return <div className={'flow-node '+(selected?'selected ':'')+(data.verified?'flow-node-ok':'flow-node-fail')}>
    <Handle type="target" position={Position.Left} isConnectable={false} />
    <div className="flow-node-top"><span className="flow-node-step">0{data.stage+1}</span><span className="flow-node-status">{data.verified?<Check size={13}/>:<CircleAlert size={13}/>}</span></div>
    <div className="flow-node-icon"><Icon size={22}/></div>
    <strong>{data.label === 'TrainingRun' ? 'Training run' : data.label === 'ContainerImage' ? 'Container image' : data.label}</strong>
    <div className="flow-node-id mono">{data.artifactId.slice(0,18)}…</div>
    <Handle type="source" position={Position.Right} isConnectable={false}/>
  </div>
}
const nodeTypes = { stage: Stage }

function unpack(report: ConsumerReport | ModelReport): { checks: ArtifactCheck[]; relationships: Relationship[] } {
  if ('deployment_id' in report) return { checks: [...Object.values(report.artifacts), ...report.datasets], relationships: report.relationships }
  return { checks: [report.model, ...(report.training_run?[report.training_run]:[]), ...report.datasets], relationships: report.relationships }
}

export default function LineageGraph({ report }: { report: ConsumerReport | ModelReport }) {
  const [selected, setSelected] = useState<string | null>(null)
  const { nodes, edges, checks } = useMemo(() => {
    const unpacked = unpack(report)
    const datasets = unpacked.checks.filter(x=>x.artifact_type==='Dataset')
    const nodes: StageNode[] = unpacked.checks.map(check => {
      const col = order[check.artifact_type] ?? 0
      const datasetIndex = datasets.findIndex(x=>x.artifact_id===check.artifact_id)
      const y = check.artifact_type === 'Dataset' ? 140 + (datasetIndex-(datasets.length-1)/2)*170 : 140
      return { id:check.artifact_id, type:'stage', position:{x:col*236+34,y}, data:{label:check.artifact_type,artifactId:check.artifact_id,verified:check.verified,stage:col}, selected: selected===check.artifact_id }
    })
    const known = new Set(nodes.map(node=>node.id))
    const edges: Edge[] = unpacked.relationships.filter(x=>known.has(x.source)&&known.has(x.target)).map((rel,i)=>({id:`rel-${i}`,source:rel.source,target:rel.target,type:'smoothstep',animated:rel.verified,style:{stroke:rel.verified?'#56c6b2':'#b96565',strokeWidth:2,opacity:.85},label:rel.relationship,labelStyle:{fill:'#9ca9b9',fontSize:10,fontFamily:'ui-monospace, monospace',fontWeight:600},labelBgStyle:{fill:'#101722',fillOpacity:1},labelBgPadding:[7,5],labelBgBorderRadius:5}))
    return {...unpacked,nodes,edges}
  }, [report,selected])
  const highlighted = checks.find(item=>item.artifact_id===selected)

  return <div className="graph-wrap"><div className="graph-toolbar"><span>PROVENANCE / <b>ON-CHAIN RELATIONSHIPS</b></span><span>{checks.length} ARTIFACTS · {edges.length} LINKS</span></div><div className="graph-canvas"><ReactFlow nodes={nodes} edges={edges} nodeTypes={nodeTypes} fitView fitViewOptions={{padding:.17,maxZoom:1}} minZoom={.4} maxZoom={1.5} nodesConnectable={false} nodesDraggable={false} proOptions={{hideAttribution:true}} onNodeClick={(_,node)=>setSelected(node.id)} onPaneClick={()=>setSelected(null)}><Background color="#253444" gap={24} size={1}/><Controls showInteractive={false}/></ReactFlow></div><div className="graph-info">{highlighted ? <><div><span className="detail-label">SELECTED ARTIFACT</span><strong><Short value={highlighted.artifact_id} start={38} end={9}/></strong></div><div className="graph-info-right"><span className={highlighted.verified?'good-text':'bad-text'}>{highlighted.verified?'Integrity verified':'Integrity failed'}</span><Copy value={highlighted.artifact_id}/></div></> : <><span>Click any artifact to inspect its recorded identifier.</span><span>Scroll to zoom · Drag to pan</span></>}</div></div>
}
