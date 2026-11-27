const inferredApiUrl = typeof window === "undefined" ? "http://localhost:8001" : `${window.location.protocol}//${window.location.hostname}:8001`;
const API_URL = (import.meta.env.VITE_API_URL || inferredApiUrl).replace(/\/$/, "");

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) { super(message); this.status = status; }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_URL}${path}`, {
    ...init,
    credentials: "include",
    headers: { "Content-Type": "application/json", ...init?.headers },
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const detail = typeof data.detail === "string" ? data.detail : data.detail?.[0]?.msg;
    throw new ApiError(response.status, detail || `Request failed (${response.status})`);
  }
  return data as T;
}

export type Session = { id: string; email: string; created_at?: string; workspaces: { id: string; name: string; role: string }[] };
export type AppRecord = { id: string; name: string; base_url: string; build_id: string; workspace_id?: string; workspace_name?: string; can_delete?: boolean; flagsmith_api_url?: string; environments: { id: string; name: string; type: string }[]; capability_count: number; workflow_count: number };
export type SystemStatus = { api: string; flagsmith: { connected?: boolean; status_code?: number; error?: string }; redis: { connected: boolean }; counts: Record<string, number> };
export type AppDetail = AppRecord & { capabilities: { semantic_key: string; flag_key: string; mapping: Record<string, unknown>; policy: Record<string, unknown> }[]; workflows: { id: string; name: string; version: string; definition: Record<string, unknown> }[] };
export type Exploration = { id: string; environment_id: string; workflow_id: string; strategy: string; status: string; budget: number; seed: number; metrics: Record<string, number>; started_at?: string; completed_at?: string };
export type Branch = { id: string; environment_id: string; application_id: string; name: string; head_commit_hash: string; revision: number; assignments: Record<string, unknown>; head_message: string; created_at?: string };
export type PassportScope = { application_id: string; application_name: string; build_id: string; workflow_id?: string; workflow_name?: string; workflow_version?: string };
export type PassportRecord = { id: string; version: number; key_id: string; payload: Record<string, unknown> & { scope?: PassportScope }; signature?: string; expires_at: string; revoked_at?: string | null };
export type AssistantStatus = { configured: boolean; provider: string; model: string };
export type ProjectContext = { application: { id: string; name: string; base_url: string; build_id: string }; status: Record<string, number | boolean>; environments: { name: string; type: string }[]; capabilities: { semantic_key: string; flag_key: string }[]; workflows: { name: string; version: string }[]; recent_explorations: { status: string; strategy: string; budget: number; metrics: Record<string, unknown> }[]; branches: { name: string; revision: number }[] };
export type ChatTurn = { role: "user" | "assistant"; content: string };
export type AssistantStreamEvent = { type: "step" | "delta" | "done" | "error"; text?: string; message?: string };

export async function streamAssistant(body: { application_id: string; message: string; history: ChatTurn[]; model: "thinkingmachines/Inkling:peft:262144" }, onEvent: (event: AssistantStreamEvent) => void, signal?: AbortSignal) {
  const response = await fetch(`${API_URL}/api/v1/assistant/chat/stream`, { method: "POST", credentials: "include", headers: { "Content-Type": "application/json", Accept: "text/event-stream" }, body: JSON.stringify(body), signal });
  if (!response.ok) { const data = await response.json().catch(() => ({})); throw new ApiError(response.status, typeof data.detail === "string" ? data.detail : "Unable to start Inkling stream"); }
  if (!response.body) throw new ApiError(502, "Streaming response body is unavailable");
  const reader=response.body.getReader();const decoder=new TextDecoder();let buffer="";
  while(true){const {done,value}=await reader.read();buffer+=decoder.decode(value??new Uint8Array(),{stream:!done});const frames=buffer.split(/\r?\n\r?\n/);buffer=frames.pop()??"";for(const frame of frames){let eventType="";let data="";for(const line of frame.split(/\r?\n/)){if(line.startsWith("event:"))eventType=line.slice(6).trim();if(line.startsWith("data:"))data+=line.slice(5).trim()}if(eventType&&data){const payload=JSON.parse(data) as Record<string,string>;onEvent({type:eventType as AssistantStreamEvent["type"],text:payload.text,message:payload.message})}}if(done)break}
}

export const api = {
  signup: (body: { email: string; password: string; workspace_name: string }) => request<{ access_token: string }>("/api/v1/auth/signup", { method: "POST", body: JSON.stringify(body) }),
  login: (body: { email: string; password: string }) => request<{ access_token: string }>("/api/v1/auth/login", { method: "POST", body: JSON.stringify(body) }),
  logout: () => request<{ ok: boolean }>("/api/v1/auth/logout", { method: "POST" }),
  me: () => request<Session>("/api/v1/auth/me"),
  apps: () => request<{ items: AppRecord[] }>("/api/v1/apps"),
  deleteApp: (id: string) => request<{ id: string; deleted: boolean }>(`/api/v1/apps/${id}`, { method: "DELETE" }),
  status: () => request<SystemStatus>("/api/v1/system/status"),
  createApp: (body: { name: string; base_url: string; build_id: string }) => request<AppRecord>("/api/v1/apps", { method: "POST", body: JSON.stringify(body) }),
  app: (id: string) => request<AppDetail>(`/api/v1/apps/${id}`),
  connectApp: (id: string, body: { flagsmith_api_url: string; environment_key: string; environment_name: string; environment_type: string; management_token?: string }) => request<{ connected: boolean; environment_id: string }>(`/api/v1/apps/${id}/connect`, { method: "POST", body: JSON.stringify(body) }),
  syncApp: (id: string) => request<{ synced: boolean; snapshot_id: string; document_hash: string }>(`/api/v1/apps/${id}/sync`, { method: "POST" }),
  updateCapabilities: (id: string, manifest: Record<string, unknown>) => request<{ updated: boolean; capability_count: number }>(`/api/v1/apps/${id}/capabilities`, { method: "PUT", body: JSON.stringify(manifest) }),
  registerWorkflow: (id: string, body: { name: string; version: string; definition: Record<string, unknown> }) => request<{ id: string; name: string; version: string }>(`/api/v1/apps/${id}/workflows`, { method: "POST", body: JSON.stringify(body) }),
  explorations: () => request<{ items: Exploration[] }>("/api/v1/explorations"),
  startExploration: (body: { application_id: string; environment_id?: string; workflow_id: string; strategy: string; budget: number; seed: number; domains: Record<string, unknown[]> }) => request<Exploration>("/api/v1/explorations", { method: "POST", body: JSON.stringify(body) }),
  cancelExploration: (id: string) => request<{ id: string; status: string }>(`/api/v1/explorations/${id}/cancel`, { method: "POST" }),
  branches: () => request<{ items: Branch[] }>("/api/v1/branches"),
  createBranch: (body: { application_id: string; environment_id?: string; name: string; assignments: Record<string, unknown>; message: string }) => request<Branch>("/api/v1/branches", { method: "POST", body: JSON.stringify(body) }),
  passports: () => request<{ items: PassportRecord[] }>("/api/v1/passports"),
  createPassport: (body: { preferences: Record<string, unknown>; audience?: string[]; ttl_days: number; application_id?: string; workflow_id?: string }) => request<PassportRecord & { token: string }>("/api/v1/passports", { method: "POST", body: JSON.stringify(body) }),
  revokePassport: (id: string) => request<{ id: string; revoked: boolean }>(`/api/v1/passports/${id}/revoke`, { method: "POST" }),
  resolveRuntime: (body: { application_id: string; passport_token?: string; preview_token?: string; user_context: Record<string, unknown>; entitlements: string[] }) => request<Record<string, unknown>>("/api/v1/runtime/resolve", { method: "POST", body: JSON.stringify(body) }),
  assistantStatus: () => request<AssistantStatus>("/api/v1/assistant/status"),
  projectContext: (id: string) => request<ProjectContext>(`/api/v1/assistant/projects/${id}/context`),
  assistantChat: (body: { application_id: string; message: string; history: ChatTurn[]; model: "thinkingmachines/Inkling:peft:262144" }) => request<{ answer: string; application_id: string; provider: string; model: string }>("/api/v1/assistant/chat", { method: "POST", body: JSON.stringify(body) }),
};
