// 类型定义

export interface Location {
  longitude: number
  latitude: number
}

export interface CityStay {
  city: string
  days: number
}

export interface Attraction {
  name: string
  address: string
  location?: Location
  visit_duration: number
  description: string
  category?: string
  rating?: number
  image_url?: string
  poi_id?: string
  ticket_price?: number
  reservation_required?: boolean
  reservation_tips?: string
  open_hours?: string
  tel?: string
}

// 餐饮类别（与后端 DiningCategory 枚举对齐）
export type DiningCategoryValue = 'main' | 'snack' | 'dessert' | 'cafe' | 'late_night'

export interface DiningCandidate {
  name: string
  address?: string
  location?: Location
  category: DiningCategoryValue
  cuisine?: string
  rating?: number
  avg_cost?: number
  distance?: string
  open_hours?: string
  tel?: string
  poi_id?: string
  source?: string
}

/** 每日多类别餐饮候选池 */
export interface DiningPoolDay {
  main: DiningCandidate[]
  snack: DiningCandidate[]
  dessert: DiningCandidate[]
  cafe: DiningCandidate[]
  late_night: DiningCandidate[]
}

export interface Meal {
  type: 'breakfast' | 'lunch' | 'dinner' | 'snack'
  category?: DiningCategoryValue
  name: string
  address?: string
  location?: Location
  description?: string
  cuisine?: string
  rating?: number
  avg_cost?: number
  distance?: string
  poi_id?: string
  source?: 'nearby' | 'popular'
  estimated_cost?: number
  open_hours?: string
  tel?: string
}

export interface Hotel {
  name: string
  address: string
  location?: Location
  price_range: string
  rating: string
  distance: string
  type: string
  estimated_cost?: number
  star_rating?: number
  price?: number
  original_price?: number
  currency?: string
  hotel_amenities?: string[]
  room_amenities?: string[]
  description?: string
  image_url?: string
  detail_url?: string
  distance_in_meters?: number
  hotel_id?: number | string
}

export interface CompanionInfo {
  count: number
  type: string
}

export interface Budget {
  total_attractions: number
  total_hotels: number
  total_meals: number
  total_transportation: number
  total_inter_city_transport?: number
  total: number
  budget_limit?: number
  is_within_budget?: boolean
}

export interface RouteSegment {
  from_name: string
  to_name: string
  distance: string
  duration: string
  mode: string
  detail: string
}

export interface DayPlan {
  date: string
  day_index: number
  city?: string
  is_transfer_day?: boolean
  transfer_info?: string
  description: string
  transportation: string
  accommodation: string
  hotel?: Hotel
  attractions: Attraction[]
  meals: Meal[]
  route_segments: RouteSegment[]
  timeline_order?: Array<Record<string, any>>
  day_start_time?: string
}

// ============ 骨架草稿类型（与后端 schemas.py 对齐） ============

/** 骨架阶段每日上下文 */
export interface DraftDayContext {
  day_index: number
  date: string
  attraction_names: string[]
  attractions: Attraction[]
  hotel?: Hotel | null
  dining_pool: DiningPoolDay
  weather?: WeatherInfo | null
  day_start_time?: string | null
}

/** 详细阶段产物（每日装配后的完整时间轴） */
export interface DayDetail {
  day_index: number
  date: string
  description: string
  attractions: Attraction[]
  hotel?: Hotel | null
  meals: Meal[]
  route_segments: RouteSegment[]
  day_start_time?: string | null
  timeline_order: Array<Record<string, any>>
  day_budget?: Budget | null
  is_assembled: boolean
}

export interface DayDetailResponse {
  draft_id: string
  day_index: number
  day_detail: DayDetail
}

/** 草稿完整载荷（GET /draft/{id}） */
export interface TripDraftPayload {
  draft_id: string
  status: 'skeleton' | 'assembling' | 'finalized' | 'expired'
  request: TripFormData
  city: string
  macro_plan: MacroPlan
  days: DraftDayContext[]
  days_detail: Array<DayDetail | null>
  weather_info: WeatherInfo[]
  created_at: string
  updated_at: string
}

export interface MacroPlan {
  city: string
  total_days: number
  days: Array<{ day_index: number; date: string; attraction_names: string[]; hotel_name: string }>
  transportation: string
  accommodation: string
}

/** 用户编辑端点共享请求体 */
export interface DayEditRequest {
  attractions_order?: string[]
  meals?: Array<Record<string, any>>
  day_start_time?: string
}

// ============ AI 选景 / 智能分日预览 ============

export interface AISelectRequest {
  destination: string
  days: number
  attractions: Array<Record<string, any>>
  preferences?: Record<string, any> | null
}

export interface AISelectResponse {
  must_ids: string[]
  optional_ids: string[]
  reasons: Record<string, string>
  tags: Record<string, string[]>
  summary?: string | null
}

export interface DayDurationInfo {
  day_index: number
  total_minutes: number
  warning?: string | null
}

export interface PreviewDayAssignmentRequest {
  selected_attractions: DiscoveredAttraction[]
  travel_days: number
}

export interface PreviewDayAssignmentResponse {
  day_assignments: DiscoveredAttraction[][]
  day_durations: DayDurationInfo[]
}

export interface WeatherInfo {
  date: string
  city?: string
  day_weather: string
  night_weather: string
  day_temp: number
  night_temp: number
  wind_direction: string
  wind_power: string
}

export interface TripPlan {
  city: string
  cities?: string[]
  start_date: string
  end_date: string
  days: DayPlan[]
  weather_info: WeatherInfo[]
  overall_suggestions: string
  budget?: Budget
  companions?: CompanionInfo
  trip_tagline?: string
  weather_summary?: string
}

export interface TripFormData {
  city: string
  cities?: CityStay[]
  start_date: string
  end_date: string
  travel_days: number
  transportation: string
  accommodation: string
  preferences: string[]
  food_preference: string
  free_text_input: string
  budget?: number
  companions?: CompanionInfo
  language?: string
  default_day_start_time?: string
}

/**
 * 表单内部状态：cities / companions 在表单初始化时就已构造，
 * 模板与逻辑里无需再判空（避免 TS18048）。提交时可直接作为 TripFormData 使用。
 */
export interface TripFormState extends Omit<TripFormData, 'cities' | 'companions'> {
  cities: CityStay[]
  companions: CompanionInfo
}

export interface TripPlanResponse {
  success: boolean
  message: string
  data?: TripPlan
  graph_data?: KnowledgeGraphData
  plan_id?: string
}

export interface TripRecord {
  id: number
  title: string
  city: string
  start_date: string
  end_date: string
  travel_days: number
  status: 'completed' | 'favorite' | 'archived'
  budget_limit?: number
  total_cost: number
  companion_type?: string
  companion_count: number
  tags: string[]
  cover_image?: string
  created_at?: string
  updated_at?: string
  plan?: TripPlan
  request?: TripFormData
}

export interface TripListResponse {
  success: boolean
  data: TripRecord[]
  total: number
  page: number
  page_size: number
}

export interface UserPreference {
  user_id: string
  preferred_hotel_types: string[]
  preferred_cuisines: string[]
  preferred_transportation: string[]
  budget_range?: number[]
  preferred_attraction_categories: string[]
  preferred_visit_duration: number
  preferred_attractions_per_day: number
  preferred_meal_price_range: number[]
  preferred_hotel_price_range: number[]
  total_trips: number
  cities_visited: string[]
  last_updated: string
}

export interface DiscoveredAttraction {
  name: string
  description: string
  address: string
  category: string
  rating?: number
  ticket_price?: string
  image_url?: string
  location?: Location
  poi_id?: string
  visit_minutes?: number
  open_hours?: string
  tel?: string
  selected?: boolean
  manuallyAdded?: boolean
  /** AI 池内选景结果：必去 / 备选（仅前端展示用） */
  aiPick?: 'must' | 'optional'
}

export interface DiscoveryStreamEvent {
  type: 'init' | 'attraction' | 'weather' | 'progress' | 'complete' | 'error'
  message?: string
  data?: any
  node?: string
  progress?: number
}

export interface PlanFromSelectionsPayload {
  request: TripFormData
  selected_attractions: DiscoveredAttraction[]
  day_assignments?: DiscoveredAttraction[][]
  weather_info: string
  user_id?: string
}

// ============ 知识图谱类型 ============

export interface GraphNode {
  id: string
  name: string
  category: number
  symbolSize: number
  itemStyle?: { color: string }
  value?: string
}

export interface GraphEdge {
  source: string
  target: string
  label?: string
}

export interface GraphCategory {
  name: string
}

export interface KnowledgeGraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
  categories: GraphCategory[]
}

// ============ AI 行程问答类型 ============

export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface TripChatRequest {
  message: string
  trip_plan: object
  history: ChatMessage[]
}

export interface TripChatResponse {
  success: boolean
  reply: string
}
