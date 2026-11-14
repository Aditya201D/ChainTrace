import type { Approval, Artifact, ArtifactList, ArtifactType, ArtifactVerification, ChainStatus, ConsumerReport, ModelReport, Overview } from './types'

const ROOT = (import.meta.env.VITE_API_BASE_URL || '').replace(/\/$/, '')
export const apiPath = (path: string) => ROOT + path
export const idPath = (id: string) => encodeURIComponent(id)

export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message) }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try { response = await fetch(apiPath(path), { ...init, headers: { Accept: 'application/json', ...init?.headers } }) }
  catch { throw new ApiError('Cannot reach FastAPI. Check that it is running on port 8000.', 0) }
  if (!response.ok) {
    let detail = `Request failed (${response.status})`
    try {
      const data = await response.json()
      detail = typeof data.detail === 'string' ? data.detail : detail
    } catch { /* non-JSON response */ }
    throw new ApiError(detail, response.status)
  }
  return response.json() as Promise<T>
}

export const api = {
  overview: () => request<Overview>('/api/v1/ui/overview'),
  status: () => request<ChainStatus>('/api/v1/blockchain/status'),
  artifacts: (type?: ArtifactType | 'All', search?: string, limit = 200) => {
    const params = new URLSearchParams({ limit: String(limit) })
    if (type && type !== 'All') params.set('artifact_type', type)
    if (search) params.set('search', search)
    return request<ArtifactList>(`/api/v1/ui/artifacts?${params}`)
  },
  artifact: (id: string) => request<Artifact>(`/api/v1/artifacts/${idPath(id)}`),
  verifyArtifact: (id: string) => request<ArtifactVerification>(`/api/v1/artifacts/${idPath(id)}/verify`),
  modelProvenance: (id: string) => request<ModelReport>(`/api/v1/artifacts/${idPath(id)}/provenance`),
  verifyDeployment: (id: string) => request<ConsumerReport>(`/api/v1/consumer/deployments/${idPath(id)}/verify`),
  audit: (id: string) => request<{ model_id: string; approval: Approval }>(`/api/v1/blockchain/audit/models/${idPath(id)}/status`),
  upload: async (file: File, type: ArtifactType) => {
    const form = new FormData()
    form.append('file', file)
    form.append('artifact_type', type)
    return request<Artifact>('/api/v1/artifacts/upload', { method: 'POST', body: form })
  }
}
