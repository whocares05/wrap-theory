export type ModifierOption = { id: string; name: string; priceDelta: number };
export type ModifierGroup = { id: string; name: string; minSelections: number; maxSelections: number; options: ModifierOption[] };
export type Product = {
  id: string; categoryId: string | null; name: string; slug: string; description: string; price: number;
  compareAtPrice: number | null; tag: string | null; tone: string | null; imageUrl: string | null;
  isFeatured: boolean; modifierGroups: ModifierGroup[];
};
export type Menu = { categories: Array<{ id: string; name: string; slug: string; products: Product[] }> };
export type Store = {
  name: string; phone: string; email: string | null; address: string; city: string; currency: string;
  taxRateBps: number; defaultDeliveryFee: number; minimumOrder: number; freeDeliveryThreshold: number;
  acceptsDelivery: boolean; acceptsPickup: boolean; ordersPaused: boolean;
  openingHours: Record<string, { open: string; close: string; closed?: boolean }>;
};
export type DeliveryZone = {
  id: string; name: string; areas: string[]; deliveryFee: number; minimumOrder: number | null;
  freeDeliveryThreshold: number | null; estimatedMinutes: number;
};
export type OrderSummary = { id: string; orderNumber: string; publicToken: string; status: string; paymentStatus: string; total: number };

const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:4000").replace(/\/$/, "");

export class APIError extends Error {
  constructor(public status: number, message: string, public code = "API_ERROR") { super(message); }
}

async function request<T>(path: string, options: RequestInit = {}, token?: string): Promise<T> {
  const response = await fetch(`${API_URL}/v1${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers, ...(token ? { Authorization: `Bearer ${token}` } : {}) },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => null);
    throw new APIError(response.status, body?.error?.message ?? "The request failed", body?.error?.code);
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

export const publicApi = {
  bootstrap: async () => {
    const [store, menu, zones] = await Promise.all([
      request<Store>("/public/store"), request<Menu>("/public/menu"), request<DeliveryZone[]>("/public/delivery-zones"),
    ]);
    return { store, menu, zones };
  },
  createOrder: (body: unknown, idempotencyKey: string) => request<OrderSummary>("/public/orders", {
    method: "POST", headers: { "Idempotency-Key": idempotencyKey }, body: JSON.stringify(body),
  }),
};

export const staffApi = {
  me: (token: string) => request<{ userId: string; email: string; displayName: string; role: "admin" | "manager" }>("/admin/staff/me", {}, token),
  dashboard: (token: string) => request<Record<string, unknown>>("/admin/dashboard", {}, token),
  orders: (token: string, search = "") => request<{ data: Array<Record<string, unknown>> }>(`/admin/orders?search=${encodeURIComponent(search)}`, {}, token),
  updateOrderStatus: (token: string, id: string, status: string) => request(`/admin/orders/${id}/status`, { method: "PATCH", body: JSON.stringify({ status }) }, token),
  customers: (token: string) => request<{ data: Array<Record<string, unknown>> }>("/admin/customers", {}, token),
  products: (token: string) => request<Array<Record<string, unknown>>>("/admin/catalog/products", {}, token),
  inventory: (token: string) => request<Array<Record<string, unknown>>>("/admin/catalog/inventory", {}, token),
  campaigns: (token: string) => request<Array<Record<string, unknown>>>("/admin/campaigns", {}, token),
  tasks: (token: string) => request<Array<Record<string, unknown>>>("/admin/tasks", {}, token),
};

export function formatMoney(paisa: number): string { return `Rs. ${Math.round(paisa / 100).toLocaleString("en-PK")}`; }
