import axios from 'axios'
import type {
  TripFormData, TripPlanResponse, TripPlan, TripListResponse, TripRecord,
  UserPreference, DiscoveredAttraction, DiscoveryStreamEvent, PlanFromSelectionsPayload,
  TripDraftPayload, DayDetailResponse, DayEditRequest,
  AISelectRequest, AISelectResponse, PreviewDayAssignmentRequest, PreviewDayAssignmentResponse,
} from '@/types'

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || ''

const apiClient = axios.create({
  baseURL: API_BASE_URL,
  timeout: 300000,
  headers: {
    'Content-Type': 'application/json'
  }
})

import type { ValidationReport, EditProposal, PlanningConstraints } from '@/types/planning'

export async function validateDraft(id: string): Promise<ValidationReport> {
  return (await apiClient.get(`/api/trip/draft/${id}/validation`)).data
}

export async function getReservationTasks(kind: 'draft' | 'trip', id: string | number): Promise<{ tasks: import('@/types/reservation').ReservationTask[] }> {
  return (await apiClient.get(`/api/reservations/${kind}/${id}`)).data
}

export async function markReservationBooked(kind: 'draft' | 'trip', id: string | number, key: string, booked: boolean): Promise<{ tasks: import('@/types/reservation').ReservationTask[] }> {
  return (await apiClient.patch(`/api/reservations/${kind}/${id}/${key}`, { booked })).data
}

export async function exportReservationCalendar(kind: 'draft' | 'trip', id: string | number): Promise<Blob> {
  return (await apiClient.get(`/api/reservations/${kind}/${id}/calendar.ics`, { responseType: 'blob' })).data
}

export async function savePlanningConstraints(id: string, body: PlanningConstraints) {
  return (await apiClient.put(`/api/trip/draft/${id}/constraints`, body)).data
}

export async function proposeDraftEdit(id: string, body: { message: string; repair: boolean; day_index?: number }, signal?: AbortSignal): Promise<EditProposal> {
  return (await apiClient.post(`/api/trip/draft/${id}/proposals`, body, { signal })).data
}

export async function confirmDraftEdit(id: string, proposalId: string, remember: boolean): Promise<EditProposal> {
  return (await apiClient.post(`/api/trip/draft/${id}/proposals/${proposalId}/confirm`, {
    confirmed: true, remember_preferences: remember,
  })).data
}

export async function cancelDraftEdit(id: string, proposalId: string) {
  return (await apiClient.delete(`/api/trip/draft/${id}/proposals/${proposalId}`)).data
}

/** 统一的 API 错误：调用方只需读 message，不再各写各的 error.response?.data?.detail */
export class ApiError extends Error {
  status?: number
  detail?: string
  constructor(message: string, status?: number, detail?: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.detail = detail
  }
}

function normalizeError(error: any): ApiError {
  if (axios.isCancel(error)) {
    return new ApiError('请求已取消')
  }
  if (!error.response) {
    if (error.code === 'ECONNABORTED' || /timeout/.test(error.message || '')) {
      return new ApiError('请求超时，请稍后重试')
    }
    if (error.name === 'AbortError') {
      return new ApiError('请求已取消')
    }
    return new ApiError('网络异常，请检查网络连接')
  }

  const status: number = error.response.status
  const detail = typeof error.response.data?.detail === 'string'
    ? error.response.data.detail
    : (error.response.data?.message || '')

  if (status === 401) return new ApiError('登录状态已失效，请重新登录', status, detail)
  if (status === 403) return new ApiError('没有权限执行该操作', status, detail)
  if (status === 404) return new ApiError(detail || '请求的资源不存在', status, detail)
  if (status === 409) return new ApiError(detail || '当前状态冲突，请刷新后重试', status, detail)
  if (status >= 500) return new ApiError(detail || '服务器异常，请稍后重试', status, detail)
  return new ApiError(detail || `请求失败 (${status})`, status, detail)
}

const isDev = import.meta.env.DEV

apiClient.interceptors.request.use(
  (config) => {
    if (isDev) console.log('发送请求:', config.method?.toUpperCase(), config.url)
    return config
  },
  (error) => {
    console.error('请求错误:', error)
    return Promise.reject(normalizeError(error))
  }
)

apiClient.interceptors.response.use(
  (response) => {
    if (isDev) console.log('收到响应:', response.status, response.config.url)
    return response
  },
  (error) => {
    console.error('响应错误:', error.response?.status, error.message)
    return Promise.reject(normalizeError(error))
  }
)

export async function generateTripPlan(formData: TripFormData): Promise<TripPlanResponse> {
  try {
    const response = await apiClient.post<TripPlanResponse>('/api/trip/plan', formData)
    return response.data
  } catch (error) {
    throw normalizeError(error)
  }
}

export interface StreamEvent {
  type: 'init' | 'node_start' | 'node_complete' | 'complete' | 'error' | 'progress'
  message?: string
  progress?: number
  node?: string
  current_node?: string
  data?: TripPlan
  /** 骨架图产物：草稿 ID（plan/from-selections/stream 的 complete 事件） */
  draft_id?: string
  /** 定稿流产物（draft/finalize 的 complete 事件） */
  trip_id?: number
}

export interface StreamOptions {
  timeout?: number
  signal?: AbortSignal
  /** 连续多久没收到任何字节（含心跳）就认为连接已断开，默认 60s */
  idleTimeout?: number
  /** 收到心跳行时的回调 */
  onHeartbeat?: () => void
}

async function createSSEStream<T extends { type: string }>(
  url: string,
  body: unknown,
  onEvent: (event: T) => void,
  options?: StreamOptions
): Promise<void> {
  const timeout = options?.timeout || 300000
  const idleTimeout = options?.idleTimeout || 60000
  const controller = new AbortController()

  const signal = options?.signal
    ? AbortSignal.any([options.signal, controller.signal])
    : controller.signal

  // 首字节超时：只覆盖 fetch 阶段
  const timeoutId = setTimeout(() => controller.abort(), timeout)

  let response: Response
  try {
    response = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
      signal,
    })
  } catch (error: any) {
    clearTimeout(timeoutId)
    if (error.name === 'AbortError') {
      throw new Error('请求已取消或超时')
    }
    throw error
  }

  clearTimeout(timeoutId)

  if (!response.ok) {
    throw new Error(`请求失败: ${response.status}`)
  }

  const reader = response.body?.getReader()
  if (!reader) {
    throw new Error('无法获取响应流')
  }

  const decoder = new TextDecoder()
  let buffer = ''

  // 流式阶段看门狗：每收到任意字节就续命，网络静默断开时不再永久挂起
  let idleId: ReturnType<typeof setTimeout> | undefined
  const resetIdle = () => {
    if (idleId) clearTimeout(idleId)
    idleId = setTimeout(async () => {
      idleId = undefined
      try {
        await reader.cancel()
      } catch {
        /* noop */
      }
    }, idleTimeout)
  }
  const clearIdle = () => {
    if (idleId) {
      clearTimeout(idleId)
      idleId = undefined
    }
  }
  resetIdle()

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) throw new Error('行程尚未完成，连接已结束，请重试')
      resetIdle()

      buffer += decoder.decode(value, { stream: true })

      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        const trimmed = line.trim()
        if (!trimmed) continue
        // 后端每 15s 发 `: heartbeat`，单独识别而不是静默丢弃
        if (trimmed.startsWith(':')) {
          options?.onHeartbeat?.()
          continue
        }
        if (trimmed.startsWith('data: ')) {
          try {
            const event = JSON.parse(trimmed.slice(6)) as T
            onEvent(event)
            if (event.type === 'complete' || event.type === 'error') {
              return
            }
          } catch (e) {
            console.warn('解析SSE事件失败:', trimmed, e)
          }
        }
      }
    }
  } catch (error: any) {
    if (error?.name === 'AbortError' || idleId === undefined) {
      throw new Error('连接已断开或长时间无响应，请重试')
    }
    throw error
  } finally {
    clearIdle()
    reader.cancel().catch(() => {})
  }
}

export async function generateTripPlanStream(
  formData: TripFormData,
  onEvent: (event: StreamEvent) => void,
  options?: StreamOptions
): Promise<void> {
  return createSSEStream<StreamEvent>(
    `${API_BASE_URL}/api/trip/plan/stream`,
    formData,
    onEvent,
    { timeout: 180000, signal: options?.signal, idleTimeout: options?.idleTimeout, onHeartbeat: options?.onHeartbeat }
  )
}

export async function healthCheck(): Promise<any> {
  try {
    const response = await apiClient.get('/health')
    return response.data
  } catch (error) {
    throw normalizeError(error)
  }
}

export async function getTripList(params?: { status?: string; page?: number; page_size?: number }): Promise<TripListResponse> {
  const response = await apiClient.get<TripListResponse>('/api/trips', { params })
  return response.data
}

export async function getTripDetail(tripId: number): Promise<{ success: boolean; data: TripRecord }> {
  const response = await apiClient.get(`/api/trips/${tripId}`)
  return response.data
}

export async function updateTripPlan(tripId: number, plan: TripPlan): Promise<void> {
  await apiClient.put(`/api/trips/${tripId}/plan`, plan)
}

export async function saveTripToHistory(plan: TripPlan, request?: TripFormData): Promise<{ success: boolean; data: TripRecord; message: string }> {
  const response = await apiClient.post('/api/trips', { plan, request })
  return response.data
}

export async function deleteTripFromHistory(tripId: number): Promise<{ success: boolean; message: string }> {
  const response = await apiClient.delete(`/api/trips/${tripId}`)
  return response.data
}

export async function updateTripStatus(tripId: number, status: string): Promise<{ success: boolean; data: TripRecord }> {
  const response = await apiClient.patch(`/api/trips/${tripId}/status`, { status })
  return response.data
}

export async function searchTrips(keyword: string, page?: number, pageSize?: number): Promise<TripListResponse> {
  const response = await apiClient.get<TripListResponse>('/api/trips/search', { params: { keyword, page, page_size: pageSize } })
  return response.data
}

export async function getUserPreferences(userId: string = 'default'): Promise<{ success: boolean; data?: UserPreference; message: string }> {
  const response = await apiClient.get(`/api/trip/preferences/${userId}`)
  return response.data
}

export async function updateUserPreferences(userId: string, preferences: UserPreference): Promise<{ success: boolean; data?: UserPreference; message: string }> {
  const response = await apiClient.put(`/api/trip/preferences/${userId}`, preferences)
  return response.data
}

export async function deleteUserPreferences(userId: string = 'default'): Promise<{ success: boolean; message: string }> {
  const response = await apiClient.delete(`/api/trip/preferences/${userId}`)
  return response.data
}


export async function discoverAttractionsStream(
  formData: TripFormData,
  onEvent: (event: DiscoveryStreamEvent) => void,
  options?: StreamOptions
): Promise<void> {
  return createSSEStream<DiscoveryStreamEvent>(
    `${API_BASE_URL}/api/trip/discover/stream`,
    formData,
    onEvent,
    { timeout: 300000, signal: options?.signal, idleTimeout: options?.idleTimeout, onHeartbeat: options?.onHeartbeat }
  )
}


export async function searchAttractionManual(
  keywords: string,
  city: string
): Promise<{ success: boolean; data: DiscoveredAttraction[] }> {
  const response = await apiClient.post('/api/trip/discover/search', { keywords, city })
  return response.data
}


export async function planFromSelectionsStream(
  payload: PlanFromSelectionsPayload,
  onEvent: (event: StreamEvent) => void,
  options?: StreamOptions
): Promise<void> {
  return createSSEStream<StreamEvent>(
    `${API_BASE_URL}/api/trip/plan/from-selections/stream`,
    payload,
    onEvent,
    { timeout: 300000, signal: options?.signal, idleTimeout: options?.idleTimeout, onHeartbeat: options?.onHeartbeat }
  )
}

// ============ AI 选景 / 智能分日 ============

/** AI 从当前景点池挑选必去 / 备选（池内挑选，不再额外搜攻略） */
export async function aiSelectAttractions(req: AISelectRequest): Promise<AISelectResponse> {
  const response = await apiClient.post<AISelectResponse>('/api/discover/ai_select', req)
  return response.data
}

/** 智能日程分配预览（不持久化）：返回每天景点分配与估时 */
export async function previewDayAssignment(
  req: PreviewDayAssignmentRequest
): Promise<PreviewDayAssignmentResponse> {
  const response = await apiClient.post<PreviewDayAssignmentResponse>(
    '/api/trip/plan/preview-day-assignment', req
  )
  return response.data
}

// ============ 骨架草稿 API ============

/** 读取草稿完整内容 */
export async function getDraft(draftId: string): Promise<TripDraftPayload> {
  const response = await apiClient.get<TripDraftPayload>(`/api/trip/draft/${draftId}`)
  return response.data
}

/** 删除草稿 */
export async function deleteDraft(draftId: string): Promise<{ success: boolean }> {
  const response = await apiClient.delete(`/api/trip/draft/${draftId}`)
  return response.data
}

/** 展开某天：规则装配 + 路线 + LLM 叙述 */
export async function assembleDay(
  draftId: string,
  dayIndex: number,
  overrides: DayEditRequest = {},
  force = false
): Promise<DayDetailResponse> {
  const response = await apiClient.post<DayDetailResponse>(
    `/api/trip/draft/${draftId}/day/${dayIndex}/assemble`,
    overrides,
    { params: { force } }
  )
  return response.data
}

/** 重算某天：规则装配 + amap 路线（不调用 LLM） */
export async function recomputeDay(
  draftId: string,
  dayIndex: number,
  edit: DayEditRequest
): Promise<DayDetailResponse> {
  const response = await apiClient.post<DayDetailResponse>(
    `/api/trip/draft/${draftId}/day/${dayIndex}/recompute`,
    edit
  )
  return response.data
}

/** AI 重新安排某天（从餐饮候选池重排） */
export async function aiRearrangeDay(
  draftId: string,
  dayIndex: number,
  hint?: string
): Promise<DayDetailResponse> {
  const response = await apiClient.post<DayDetailResponse>(
    `/api/trip/draft/${draftId}/day/${dayIndex}/ai-rearrange`,
    { hint: hint ?? null }
  )
  return response.data
}

/** 重写当日叙述文案（仅刷新 description） */
export async function rewriteNarrative(
  draftId: string,
  dayIndex: number
): Promise<DayDetailResponse> {
  const response = await apiClient.post<DayDetailResponse>(
    `/api/trip/draft/${draftId}/day/${dayIndex}/narrative`
  )
  return response.data
}

export interface FinalizeStreamEvent {
  type: 'progress' | 'complete' | 'error'
  step?: string
  message?: string
  trip_id?: number
  trip_plan?: TripPlan
}

/** 定稿草稿 → 写入 trip_history（SSE） */
export async function finalizeDraftStream(
  draftId: string,
  onEvent: (event: FinalizeStreamEvent) => void,
  options?: StreamOptions
): Promise<void> {
  return createSSEStream<FinalizeStreamEvent>(
    `${API_BASE_URL}/api/trip/draft/${draftId}/finalize`,
    {},
    onEvent,
    { timeout: 300000, signal: options?.signal, idleTimeout: options?.idleTimeout, onHeartbeat: options?.onHeartbeat }
  )
}

export default apiClient
