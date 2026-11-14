export type ArtifactType = 'Dataset' | 'TrainingRun' | 'Model' | 'ContainerImage' | 'Deployment'
export const TYPES: ArtifactType[] = ['Dataset', 'TrainingRun', 'Model', 'ContainerImage', 'Deployment']

export interface Artifact {
  artifact_id: string
  artifact_id_bytes32: string
  artifact_type: ArtifactType
  original_filename: string
  content_hash_bytes32: string
  sha256_hex: string
  file_size_bytes: number
  uploaded_at: string
  mime_type: string | null
  chain_registered: boolean
  chain_tx_hash: string | null
}
export interface Overview {
  total_artifacts: number
  db_marked_registered: number
  by_type: Record<ArtifactType, number>
  recent_artifacts: Artifact[]
}
export interface ArtifactList { items: Artifact[]; total: number; limit: number; offset: number }
export interface ChainStatus { rpc_connected: boolean; contract_deployed: boolean; chain_id: number | null; latest_block: number | null; contract_address?: string | null }
export interface Check { artifact_id: string; artifact_type: ArtifactType; verified: boolean; file_exists?: boolean; file_hash_matches?: boolean; local_hash_matches?: boolean; blockchain_record_matches: boolean }
export interface Relationship { source: string; target: string; relationship: string; verified: boolean; linked_at?: number; linked_by?: string }
export interface ConsumerReport {
  deployment_id: string
  lineage_complete: boolean
  artifacts: Record<string, Check>
  datasets: Check[]
  relationships: Relationship[]
  model_approval: Approval | null
  approval_active_now: boolean
  provenance_integrity_verified: boolean
  trusted_for_current_policy: boolean
  errors: string[]
  notes: string[]
}
export interface ModelReport {
  model_id: string
  model: Check
  training_run: Check | null
  datasets: Check[]
  relationships: Relationship[]
  overall_verified: boolean
  message: string
}
export interface Approval {
  approved: boolean
  approved_by: string
  approved_at: number
  evidence_hash: string
  revoked_by: string
  revoked_at: number
}
export interface ArtifactVerification {
  artifact_id: string
  verification: {
    file_exists: boolean
    local_hash_matches_database: boolean
    blockchain_record_exists: boolean
    blockchain_hash_matches_database: boolean
    overall_verified: boolean
  }
  hashes: { database_hash: string; local_file_hash: string | null; blockchain_hash: string | null }
}
