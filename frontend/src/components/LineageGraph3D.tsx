import { useMemo, useState, useRef, useCallback } from 'react'
import { Canvas, useFrame } from '@react-three/fiber'
import { OrbitControls, Html, Float } from '@react-three/drei'
import { Check, CircleAlert, Database, FileCode2, Layers, Package, RadioTower } from 'lucide-react'
import { Copy, Short } from './Ui'
import type { Check as ArtifactCheck, ConsumerReport, ModelReport, Relationship } from '../types'
import * as THREE from 'three'

/* ── Three.js 3D Provenance Graph ──────────────────────────────────
   Renders the same provenance data as LineageGraph (2D) but in an
   interactive 3D scene using @react-three/fiber + drei.
   ────────────────────────────────────────────────────────────────── */

const order: Record<string, number> = { Dataset: 0, TrainingRun: 1, Model: 2, ContainerImage: 3, Deployment: 4 }
const icons: Record<string, typeof Database> = { Dataset: Database, TrainingRun: FileCode2, Model: Layers, ContainerImage: Package, Deployment: RadioTower }
const typeLabels: Record<string, string> = { TrainingRun: 'Training run', ContainerImage: 'Container image' }

interface NodeData { id: string; label: string; verified: boolean; stage: number; x: number; y: number; z: number }
interface EdgeData { source: NodeData; target: NodeData; verified: boolean; label: string }

function unpack(report: ConsumerReport | ModelReport): { checks: ArtifactCheck[]; relationships: Relationship[] } {
  if ('deployment_id' in report) return { checks: [...Object.values(report.artifacts), ...report.datasets], relationships: report.relationships }
  return { checks: [report.model, ...(report.training_run ? [report.training_run] : []), ...report.datasets], relationships: report.relationships }
}

/* ── Animated edge pulse ─────────────────────────────────────────── */
function PulsingEdge({ edge }: { edge: EdgeData }) {
  const ref = useRef<THREE.Mesh>(null)
  const points = useMemo(() => [
    new THREE.Vector3(edge.source.x + 1.1, edge.source.y, edge.source.z),
    new THREE.Vector3(
      (edge.source.x + edge.target.x) / 2,
      (edge.source.y + edge.target.y) / 2,
      (edge.source.z + edge.target.z) / 2 + 0.3
    ),
    new THREE.Vector3(edge.target.x - 1.1, edge.target.y, edge.target.z),
  ], [edge])

  const curve = useMemo(() => new THREE.QuadraticBezierCurve3(...points as [THREE.Vector3, THREE.Vector3, THREE.Vector3]), [points])

  useFrame(({ clock }) => {
    if (!ref.current) return
    const t = (clock.getElapsedTime() * 0.4) % 1
    const pos = curve.getPoint(t)
    ref.current.position.copy(pos)
  })

  return (
    <>
      <mesh>
        <tubeGeometry args={[curve, 32, 0.03, 8, false]} />
        <meshStandardMaterial
          color={edge.verified ? '#56c6b2' : '#b96565'}
          emissive={edge.verified ? '#56c6b2' : '#b96565'}
          emissiveIntensity={0.6}
          roughness={0.3}
          transparent
          opacity={0.8}
        />
      </mesh>
      {/* Traveling pulse dot */}
      <mesh ref={ref}>
        <sphereGeometry args={[0.07, 12, 12]} />
        <meshStandardMaterial
          color={edge.verified ? '#83dcb8' : '#ef9f9e'}
          emissive={edge.verified ? '#83dcb8' : '#ef9f9e'}
          emissiveIntensity={2}
        />
      </mesh>
      {/* Edge label at midpoint */}
      <Html position={[points[1].x, points[1].y, points[1].z]} center style={{ pointerEvents: 'none' }}>
        <span className="edge-3d-label mono">{edge.label}</span>
      </Html>
    </>
  )
}

/* ── 3D Node card ────────────────────────────────────────────────── */
function Node3D({ node, isSelected, onSelect }: { node: NodeData; isSelected: boolean; onSelect: (id: string) => void }) {
  const Icon = icons[node.label] || Layers
  const meshRef = useRef<THREE.Mesh>(null)

  // Subtle hover glow
  const [hovered, setHovered] = useState(false)

  return (
    <Float
      speed={1.2}
      rotationIntensity={0}
      floatIntensity={0.3}
      floatingRange={[-0.04, 0.04]}
    >
      <group position={[node.x, node.y, node.z]}>
        {/* Glow backplane */}
        <mesh
          ref={meshRef}
          onPointerOver={() => setHovered(true)}
          onPointerOut={() => setHovered(false)}
          onClick={() => onSelect(node.id)}
        >
          <planeGeometry args={[2.1, 1.7]} />
          <meshStandardMaterial
            color={isSelected ? '#1e3d4a' : hovered ? '#1a3340' : '#15242e'}
            emissive={isSelected ? '#84dce5' : node.verified ? '#56c6b2' : '#b96565'}
            emissiveIntensity={isSelected ? 0.3 : hovered ? 0.15 : 0.07}
            transparent
            opacity={0.85}
          />
        </mesh>

        {/* Border ring */}
        <mesh position={[0, 0, -0.01]}>
          <planeGeometry args={[2.18, 1.78]} />
          <meshStandardMaterial
            color={isSelected ? '#84dce5' : node.verified ? '#395866' : '#754951'}
            transparent
            opacity={0.6}
          />
        </mesh>

        {/* DOM card inside the 3D scene */}
        <Html
          center
          distanceFactor={5}
          style={{ pointerEvents: 'auto', cursor: 'pointer' }}
          onClick={() => onSelect(node.id)}
        >
          <div
            className={'node-3d ' + (isSelected ? 'node-3d-selected ' : '') + (node.verified ? 'node-3d-ok' : 'node-3d-fail')}
            onClick={() => onSelect(node.id)}
          >
            <div className="node-3d-top">
              <span className="node-3d-step mono">0{node.stage + 1}</span>
              <span className="node-3d-status">
                {node.verified ? <Check size={12} /> : <CircleAlert size={12} />}
              </span>
            </div>
            <div className="node-3d-icon"><Icon size={18} /></div>
            <strong>{typeLabels[node.label] || node.label}</strong>
            <div className="node-3d-id mono">{node.id.slice(0, 16)}…</div>
          </div>
        </Html>
      </group>
    </Float>
  )
}

/* ── Grid floor ──────────────────────────────────────────────────── */
function GridFloor() {
  return (
    <mesh rotation={[-Math.PI / 2, 0, 0]} position={[0, -2, 0]}>
      <planeGeometry args={[30, 20]} />
      <meshStandardMaterial color="#0c141e" transparent opacity={0.5} />
    </mesh>
  )
}

/* ── Main 3D scene ───────────────────────────────────────────────── */
export default function LineageGraph3D({ report }: { report: ConsumerReport | ModelReport }) {
  const [selected, setSelected] = useState<string | null>(null)

  const { nodes3d, edges3d, checks } = useMemo(() => {
    const unpacked = unpack(report)
    const datasets = unpacked.checks.filter(c => c.artifact_type === 'Dataset')
    const nodeMap = new Map<string, NodeData>()

    const nodes3d: NodeData[] = unpacked.checks.map(check => {
      const col = order[check.artifact_type] ?? 0
      const datasetIndex = datasets.findIndex(d => d.artifact_id === check.artifact_id)
      const yOffset = check.artifact_type === 'Dataset'
        ? (datasetIndex - (datasets.length - 1) / 2) * 2.2
        : 0

      const node: NodeData = {
        id: check.artifact_id,
        label: check.artifact_type,
        verified: check.verified,
        stage: col,
        x: col * 3 - 6,
        y: yOffset,
        z: check.artifact_type === 'Dataset' ? datasetIndex * 0.15 : 0,
      }
      nodeMap.set(check.artifact_id, node)
      return node
    })

    const known = new Set(nodes3d.map(n => n.id))
    const edges3d: EdgeData[] = unpacked.relationships
      .filter(r => known.has(r.source) && known.has(r.target))
      .map(rel => ({
        source: nodeMap.get(rel.source)!,
        target: nodeMap.get(rel.target)!,
        verified: rel.verified,
        label: rel.relationship,
      }))

    return { nodes3d, edges3d, checks: unpacked.checks }
  }, [report])

  const highlighted = checks.find(c => c.artifact_id === selected)

  const handleSelect = useCallback((id: string) => {
    setSelected(prev => prev === id ? null : id)
  }, [])

  return (
    <div className="graph-wrap">
      <div className="graph-toolbar">
        <span>PROVENANCE / <b>3D VISUALIZATION</b></span>
        <span>{checks.length} ARTIFACTS · {edges3d.length} LINKS</span>
      </div>
      <div className="graph-3d-canvas">
        <Canvas
          camera={{ position: [0, 2, 12], fov: 50 }}
          style={{ background: '#0c141e' }}
          onPointerMissed={() => setSelected(null)}
        >
          <ambientLight intensity={0.4} />
          <pointLight position={[5, 5, 5]} intensity={0.6} color="#84dce5" />
          <pointLight position={[-5, -3, 3]} intensity={0.3} color="#74d5b4" />

          <GridFloor />

          {/* Fog for depth */}
          <fog attach="fog" args={['#0c141e', 12, 25]} />

          {nodes3d.map(node => (
            <Node3D key={node.id} node={node} isSelected={selected === node.id} onSelect={handleSelect} />
          ))}

          {edges3d.map((edge, i) => (
            <PulsingEdge key={i} edge={edge} />
          ))}

          <OrbitControls
            enableDamping
            dampingFactor={0.08}
            autoRotate
            autoRotateSpeed={0.3}
            maxPolarAngle={Math.PI * 0.7}
            minPolarAngle={Math.PI * 0.2}
            minDistance={5}
            maxDistance={20}
          />
        </Canvas>
      </div>
      <div className="graph-info">
        {highlighted ? (
          <>
            <div>
              <span className="detail-label">SELECTED ARTIFACT</span>
              <strong><Short value={highlighted.artifact_id} start={38} end={9} /></strong>
            </div>
            <div className="graph-info-right">
              <span className={highlighted.verified ? 'good-text' : 'bad-text'}>
                {highlighted.verified ? 'Integrity verified' : 'Integrity failed'}
              </span>
              <Copy value={highlighted.artifact_id} />
            </div>
          </>
        ) : (
          <>
            <span>Click any artifact to inspect · Drag to orbit · Scroll to zoom</span>
            <span className="mono" style={{ fontSize: 9, color: '#6e8090' }}>THREE.JS RENDER</span>
          </>
        )}
      </div>
    </div>
  )
}
