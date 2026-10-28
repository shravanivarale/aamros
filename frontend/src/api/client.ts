const API_BASE = '/api/v1'

class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

// ── 401 interceptor state ─────────────────────────────────────────────────────
// We allow exactly one in-flight refresh attempt at a time to avoid a refresh
// storm when multiple concurrent requests all get 401.
let isRefreshing = false
let pendingQueue: Array<{ resolve: (token: string) => void; reject: (err: unknown) => void }> = []

function processQueue(token: string | null, error: unknown = null) {
  pendingQueue.forEach(({ resolve, reject }) => {
    if (token) resolve(token)
    else reject(error)
  })
  pendingQueue = []
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {},
  _isRetry = false,
): Promise<T> {
  const token = localStorage.getItem('access_token')

  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  }

  if (token) {
    headers['Authorization'] = `Bearer ${token}`
  }

  const response = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  })

  // ── 401 interceptor ───────────────────────────────────────────────────────
  if (response.status === 401 && !_isRetry) {
    const refreshToken = localStorage.getItem('refresh_token')

    if (!refreshToken) {
      // No refresh token — log out immediately
      const { useAuthStore } = await import('../stores/authStore')
      useAuthStore.getState().logout()
      throw new ApiError(401, 'Session expired')
    }

    if (isRefreshing) {
      // Another refresh is in progress — queue this request
      return new Promise<T>((resolve, reject) => {
        pendingQueue.push({
          resolve: (newToken) => {
            headers['Authorization'] = `Bearer ${newToken}`
            resolve(request<T>(endpoint, { ...options, headers }, true))
          },
          reject,
        })
      })
    }

    isRefreshing = true

    try {
      const refreshResp = await fetch(`${API_BASE}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      })

      if (!refreshResp.ok) throw new Error('Refresh failed')

      const tokens = (await refreshResp.json()) as { access_token: string; refresh_token: string }
      localStorage.setItem('access_token', tokens.access_token)
      localStorage.setItem('refresh_token', tokens.refresh_token)

      // Update the store without triggering another fetch
      const { useAuthStore } = await import('../stores/authStore')
      useAuthStore.setState({
        accessToken: tokens.access_token,
        refreshToken: tokens.refresh_token,
      })

      processQueue(tokens.access_token)
      isRefreshing = false

      // Retry the original request with the new token
      headers['Authorization'] = `Bearer ${tokens.access_token}`
      return request<T>(endpoint, { ...options, headers }, true)
    } catch (err) {
      processQueue(null, err)
      isRefreshing = false
      const { useAuthStore } = await import('../stores/authStore')
      useAuthStore.getState().logout()
      throw new ApiError(401, 'Session expired — please log in again')
    }
  }
  // ── end 401 interceptor ───────────────────────────────────────────────────

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }))
    throw new ApiError(response.status, error.detail || 'Request failed')
  }

  if (response.status === 204) return {} as T
  return response.json()
}

export const api = {
  auth: {
    login: (email: string, password: string) =>
      request<{ access_token: string; refresh_token: string }>('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      }),
    register: (data: { email: string; password: string; full_name: string }) =>
      request('/auth/register', { method: 'POST', body: JSON.stringify(data) }),
    me: () => request<import('../types').User>('/auth/me'),
    refresh: (refresh_token: string) =>
      request<{ access_token: string; refresh_token: string }>('/auth/refresh', {
        method: 'POST',
        body: JSON.stringify({ refresh_token }),
      }),
    firebaseLogin: (id_token: string) =>
      request<{ access_token: string; refresh_token: string }>('/auth/firebase-login', {
        method: 'POST',
        body: JSON.stringify({ id_token }),
      }),
  },
  products: {
    list: () => request<import('../types').Product[]>('/products'),
    create: (data: Partial<import('../types').Product>) =>
      request<import('../types').Product>('/products', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
  },
  orders: {
    list: () => request<import('../types').Order[]>('/orders'),
    create: (items: { product_id: string; quantity: number }[], notes?: string) =>
      request<import('../types').Order>('/orders', {
        method: 'POST',
        body: JSON.stringify({ items, notes }),
      }),
  },
  shipments: {
    list: () => request<import('../types').Shipment[]>('/shipments'),
    create: (data: {
      items: { product_id?: string; expected_quantity: number; aruco_marker_id?: number; crate_label?: string }[]
      notes?: string
    }) =>
      request<import('../types').Shipment>('/shipments', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    get: (id: string) => request<import('../types').Shipment>(`/shipments/${id}`),
  },
  robots: {
    list: () => request<import('../types').Robot[]>('/robots'),
    get: (id: string) => request<import('../types').Robot>(`/robots/${id}`),
    create: (data: { name: string; model?: string; serial_number: string; ip_address?: string }) =>
      request<import('../types').Robot>('/robots', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    update: (id: string, data: { name?: string; model?: string; serial_number?: string; ip_address?: string; is_enabled?: boolean }) =>
      request<import('../types').Robot>(`/robots/${id}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
    delete: (id: string) => request<{ status: string; message: string }>(`/robots/${id}`, { method: 'DELETE' }),
    health: (id: string) => request<import('../types').RobotHealth>(`/robots/${id}/health`),
    sendCommand: (id: string, command: string, payload: Record<string, unknown>) =>
      request(`/robots/${id}/command`, {
        method: 'POST',
        body: JSON.stringify({ command, payload }),
      }),
  },
  map: {
    getCurrent: () => request<import('../types').WarehouseMap>('/map/current'),
    upload: (data: { label: string; pgm_data: string; resolution: number; origin_x: number; origin_y: number; width_px: number; height_px: number }) =>
      request<import('../types').WarehouseMap>('/map/upload', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    syncWarehouse: (id: string) =>
      request(`/map/${id}/sync-warehouse`, { method: 'POST' }),
  },
  inventory: {
    list: () => request<import('../types').InventoryItem[]>('/shipments/inventory'), // Note: this is under /shipments prefix in warehouse.py
  },
  slotting: {
    analyze: () => request<{ status: string; demand_analysis: Record<string, unknown> }>('/slotting/analyze', { method: 'POST' }),
    optimize: () => request<{ status: string; recommendations_generated: number }>('/slotting/optimize', { method: 'POST' }),
    recommendations: () => request<{ id: string; product_id: string; slot_id: string; priority_score: number; slot_score: number; reason: string }[]>('/slotting/recommendations'),
    reslot: () => request<{ status: string; tasks_generated: number }>('/slotting/reslot', { method: 'POST' }),
    history: () => request<{ id: string; created_at: string; status: string; algorithm: string; recommendations_count: number; travel_reduction_pct: number; relocation_tasks: number; runtime_ms: number }[]>('/slotting/history'),
  },
  categories: {
    list: () => request<{ id: string; name: string; description?: string }[]>('/categories'),
  },
  stockMovements: {
    list: () => request<{ id: string; sku: string; product_name: string; movement_type: string; quantity: number; source_location: string; destination_location: string; robot_name: string; timestamp: string; status: string }[]>('/stock-movements'),
  },
  users: {
    list: () => request<import('../types').User[]>('/admin/users'),
    update: (id: string, data: Partial<import('../types').User>) =>
      request<import('../types').User>(`/admin/users/${id}`, {
        method: 'PUT',
        body: JSON.stringify(data),
      }),
    delete: (id: string) =>
      request<{ status: string; message: string }>(`/admin/users/${id}`, { method: 'DELETE' }),
  },
  admin: {
    stats: () => request<{ total_users: number; total_products: number; total_orders: number; total_shipments: number; total_robots: number; active_robots: number }>('/admin/stats'),
    settings: () => request<{ app_name: string; app_version: string; environment: string; database_provider: string; supabase_configured: boolean; firebase_auth_enabled: boolean }>('/admin/settings'),
  },
  robotCommunication: {
    submitTask: (data: { task_type?: string; source_location_id: string; destination_location_id: string; priority?: number; robot_id?: string }) =>
      request<{ status: string; task_id: string; message_id: string }>('/robot-communication/tasks', {
        method: 'POST',
        body: JSON.stringify(data),
      }),
    getTask: (taskId: string) => request<{ task_id: string; status: string; ros_bridge_state?: Record<string, unknown> }>(`/robot-communication/tasks/${taskId}`),
    cancelTask: (taskId: string) => request(`/robot-communication/tasks/${taskId}/cancel`, { method: 'POST' }),
    pauseTask: (taskId: string) => request(`/robot-communication/tasks/${taskId}/pause`, { method: 'POST' }),
    resumeTask: (taskId: string) => request(`/robot-communication/tasks/${taskId}/resume`, { method: 'POST' }),
    listRobots: () => request<{ robot_id: string; status: string; battery: number; position: { x: number; y: number; yaw: number }; current_task_id?: string; last_seen?: string }[]>('/robot-communication/robots'),
    listEvents: () => request<{ message_id: string; message_type: string; timestamp: string; task_id?: string; payload?: Record<string, unknown> }[]>('/robot-communication/events'),
    health: () => request<{ status: string; ros_initialized: boolean; active_robots: number; pending_tasks: number; node_name: string }>('/robot-communication/health'),
  },
}

export { ApiError }
