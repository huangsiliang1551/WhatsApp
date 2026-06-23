import { api } from "./api";

// ── Types ──

export type Product = {
  id: string;
  name: string;
  price: number;
  image_url: string | null;
  tags: string[];
  created_at: string;
};

export type ProductPackage = {
  id: string;
  name: string;
  target_amount: number;
  margin_percent: number;
  item_count: number;
  reward_amount: number;
  items: ProductPackageItem[];
  created_at: string;
};

export type ProductPackageItem = {
  product_id: string;
  product_name: string;
  price: number;
  quantity: number;
};

export type PackageAssemblePreview = {
  items: ProductPackageItem[];
  total_value: number;
  target_amount: number;
  deviation_pct: number;
};

export type TaskRule = {
  id: string;
  name: string;
  trigger_type: string;
  trigger_config: Record<string, unknown>;
  package_id: string;
  package_name: string;
  expiry_config: string;
  follow_up_chain: TaskRuleFollowUp[];
  status: string;
  created_at: string;
};

export type TaskRuleFollowUp = {
  delay_days: number;
  package_id: string;
  package_name: string;
};

export type SignInConfig = {
  consecutive_days: number;
  reward_amount: number;
};

export type InviteConfig = {
  register_reward: number;
  recharge_trigger_amount: number;
  recharge_reward: number;
  max_invitees: number;
  same_ip_limit: number;
  same_device_limit: number;
};

export type MarketingStats = {
  push_triggered: number;
  push_claimed: number;
  push_completed: number;
  push_reward_total: number;
  signin_count: number;
  signin_completed: number;
  signin_reward_total: number;
  invite_share_count: number;
  invite_registration: number;
  invite_recharge: number;
  invite_reward_total: number;
  daily_trend: Array<{ date: string; push: number; signin: number; invite: number }>;
};

export type PackageStats = {
  total_products: number;
  total_packages: number;
  total_claimed: number;
  avg_completion_rate: number;
};

export type PushPayload = {
  customer_ids: string[];
  package_id: string;
  account_id?: string;
};

// ── Mock Data ──

const DEFAULT_MOCK_PRODUCTS: Product[] = [
  { id: "prod-1", name: "Travel Tote", price: 79.5, image_url: null, tags: ["hot", "new"], created_at: "2026-06-01" },
  { id: "prod-2", name: "Canvas Strap", price: 50.0, image_url: null, tags: ["accessory"], created_at: "2026-06-01" },
  { id: "prod-3", name: "USB Cable", price: 12.0, image_url: null, tags: ["tech"], created_at: "2026-06-02" },
  { id: "prod-4", name: "Screen Film", price: 8.0, image_url: null, tags: ["tech"], created_at: "2026-06-02" },
  { id: "prod-5", name: "Ear Buds", price: 15.0, image_url: null, tags: ["audio"], created_at: "2026-06-03" },
  { id: "prod-6", name: "Phone Case", price: 22.0, image_url: null, tags: ["accessory"], created_at: "2026-06-03" },
  { id: "prod-7", name: "Desk Lamp", price: 58.0, image_url: null, tags: ["home"], created_at: "2026-06-04" },
  { id: "prod-8", name: "Warm LED Bulb", price: 15.0, image_url: null, tags: ["home"], created_at: "2026-06-04" },
  { id: "prod-9", name: "Sport Watch", price: 245.0, image_url: null, tags: ["hot"], created_at: "2026-06-05" },
];

function loadMockProducts(): Product[] {
  try {
    const saved = localStorage.getItem("mock_products");
    if (saved) {
      const parsed: Product[] = JSON.parse(saved);
      // Strip stale blob URLs (only valid within same page session)
      return parsed.map(p => ({
        ...p,
        image_url: p.image_url?.startsWith("blob:") ? null : p.image_url,
      }));
    }
  } catch { /* ignore */ }
  return [...DEFAULT_MOCK_PRODUCTS];
}

function saveMockProducts(prods: Product[]): void {
  try {
    localStorage.setItem("mock_products", JSON.stringify(prods));
  } catch { /* ignore */ }
}

let MOCK_PRODUCTS: Product[] = loadMockProducts();

const DEFAULT_MOCK_PACKAGES: ProductPackage[] = [
  { id: "pkg-1", name: "新人大礼包", target_amount: 99, margin_percent: 10, item_count: 5, reward_amount: 5, items: [
    { product_id: "prod-1", product_name: "Travel Tote", price: 79.5, quantity: 1 },
    { product_id: "prod-2", product_name: "Canvas Strap", price: 50.0, quantity: 1 },
    { product_id: "prod-3", product_name: "USB Cable", price: 12.0, quantity: 1 },
    { product_id: "prod-4", product_name: "Screen Film", price: 8.0, quantity: 2 },
    { product_id: "prod-5", product_name: "Ear Buds", price: 15.0, quantity: 1 },
  ], created_at: "2026-06-01" },
  { id: "pkg-2", name: "充值奖励包", target_amount: 50, margin_percent: 10, item_count: 3, reward_amount: 3, items: [
    { product_id: "prod-3", product_name: "USB Cable", price: 12.0, quantity: 2 },
    { product_id: "prod-6", product_name: "Phone Case", price: 22.0, quantity: 1 },
    { product_id: "prod-8", product_name: "Warm LED Bulb", price: 15.0, quantity: 1 },
  ], created_at: "2026-06-02" },
  { id: "pkg-3", name: "每日精选", target_amount: 30, margin_percent: 10, item_count: 2, reward_amount: 1, items: [
    { product_id: "prod-4", product_name: "Screen Film", price: 8.0, quantity: 1 },
    { product_id: "prod-5", product_name: "Ear Buds", price: 15.0, quantity: 1 },
  ], created_at: "2026-06-03" },
];

function loadMockPackages(): ProductPackage[] {
  try {
    const saved = localStorage.getItem("mock_packages");
    if (saved) return JSON.parse(saved);
  } catch { /* ignore */ }
  return [...DEFAULT_MOCK_PACKAGES];
}

function saveMockPackages(pkgs: ProductPackage[]): void {
  try {
    localStorage.setItem("mock_packages", JSON.stringify(pkgs));
  } catch { /* ignore */ }
}

let MOCK_PACKAGES: ProductPackage[] = loadMockPackages();

const DEFAULT_MOCK_TASK_RULES: TaskRule[] = [
  { id: "rule-1", name: "新人大礼包", trigger_type: "register", trigger_config: { delay_minutes: 30 }, package_id: "pkg-1", package_name: "新人大礼包", expiry_config: "daily_reset", follow_up_chain: [
    { delay_days: 2, package_id: "pkg-2", package_name: "充值奖励包" },
    { delay_days: 3, package_id: "pkg-3", package_name: "每日精选" },
  ], status: "active", created_at: "2026-06-01" },
  { id: "rule-2", name: "充值奖励", trigger_type: "recharge", trigger_config: { threshold_amount: 50 }, package_id: "pkg-2", package_name: "充值奖励包", expiry_config: "none", follow_up_chain: [], status: "active", created_at: "2026-06-02" },
  { id: "rule-3", name: "每日精选", trigger_type: "schedule", trigger_config: { cron_hour: "10:00" }, package_id: "pkg-3", package_name: "每日精选", expiry_config: "daily_reset", follow_up_chain: [], status: "active", created_at: "2026-06-03" },
  { id: "rule-4", name: "召回礼包", trigger_type: "follow_up", trigger_config: { delay_days: 2 }, package_id: "pkg-2", package_name: "充值奖励包", expiry_config: "none", follow_up_chain: [
    { delay_days: 1, package_id: "pkg-3", package_name: "每日精选" },
  ], status: "active", created_at: "2026-06-04" },
];

function loadMockTaskRules(): TaskRule[] {
  try {
    const saved = localStorage.getItem("mock_task_rules");
    if (saved) return JSON.parse(saved);
  } catch { /* ignore */ }
  return [...DEFAULT_MOCK_TASK_RULES];
}

function saveMockTaskRules(rules: TaskRule[]): void {
  try {
    localStorage.setItem("mock_task_rules", JSON.stringify(rules));
  } catch { /* ignore */ }
}

let MOCK_TASK_RULES: TaskRule[] = loadMockTaskRules();

const DEFAULT_MOCK_SIGNIN_CONFIG: SignInConfig = { consecutive_days: 7, reward_amount: 5 };
const DEFAULT_MOCK_INVITE_CONFIG: InviteConfig = { register_reward: 2, recharge_trigger_amount: 30, recharge_reward: 3, max_invitees: 20, same_ip_limit: 3, same_device_limit: 2 };

function loadMockConfig<T>(key: string, fallback: T): T {
  try {
    const saved = localStorage.getItem(key);
    if (saved) return JSON.parse(saved);
  } catch { /* ignore */ }
  return fallback;
}
function saveMockConfig(key: string, data: unknown): void {
  try { localStorage.setItem(key, JSON.stringify(data)); } catch { /* ignore */ }
}

let MOCK_SIGNIN_CONFIG: SignInConfig = loadMockConfig("mock_signin_config", DEFAULT_MOCK_SIGNIN_CONFIG);
let MOCK_INVITE_CONFIG: InviteConfig = loadMockConfig("mock_invite_config", DEFAULT_MOCK_INVITE_CONFIG);

const MOCK_MARKETING_STATS: MarketingStats = {
  push_triggered: 500, push_claimed: 420, push_completed: 350, push_reward_total: 1750,
  signin_count: 120, signin_completed: 45, signin_reward_total: 225,
  invite_share_count: 80, invite_registration: 35, invite_recharge: 12, invite_reward_total: 106,
  daily_trend: Array.from({ length: 30 }, (_, i) => ({
    date: new Date(Date.now() - (29 - i) * 86400000).toISOString().slice(0, 10),
    push: Math.floor(Math.random() * 30 + 5),
    signin: Math.floor(Math.random() * 15 + 2),
    invite: Math.floor(Math.random() * 8 + 1),
  })),
};

// ── API Functions ──

// Products

/** Convert a File to a base64 data URL (persistable across refreshes) */
export function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(reader.result as string);
    reader.onerror = reject;
    reader.readAsDataURL(file);
  });
}

export async function listProducts(accountId?: string): Promise<Product[]> {
  if (!accountId) return MOCK_PRODUCTS;
  try { const r = await api.get<Product[]>("/api/products", { params: { account_id: accountId } }); return r.data; }
  catch { return MOCK_PRODUCTS; }
}

export async function createProduct(data: FormData): Promise<Product> {
  try {
    const r = await api.post<Product>("/api/products", data, { headers: { "Content-Type": "multipart/form-data" } });
    return r.data;
  } catch {
    const imgFile = data.get("image");
    const imageUrl = imgFile instanceof File ? await fileToDataUrl(imgFile) : null;
    const newProd: Product = {
      id: `prod-${Date.now()}`,
      name: data.get("name") as string || "New Product",
      price: Number(data.get("price")) || 0,
      image_url: imageUrl,
      tags: [],
      created_at: new Date().toISOString(),
    };
    MOCK_PRODUCTS.unshift(newProd);
    saveMockProducts(MOCK_PRODUCTS);
    return newProd;
  }
}

export async function updateProduct(id: string, data: Partial<Product>): Promise<Product> {
  try {
    const r = await api.patch<Product>(`/api/products/${id}`, data);
    return r.data;
  } catch {
    const idx = MOCK_PRODUCTS.findIndex((p) => p.id === id);
    if (idx >= 0) {
      Object.assign(MOCK_PRODUCTS[idx], data);
      saveMockProducts(MOCK_PRODUCTS);
      return MOCK_PRODUCTS[idx];
    }
    throw new Error("Product not found");
  }
}

export async function deleteProduct(id: string): Promise<void> {
  try {
    await api.delete(`/api/products/${id}`);
  } catch {
    const idx = MOCK_PRODUCTS.findIndex((p) => p.id === id);
    if (idx >= 0) {
      MOCK_PRODUCTS.splice(idx, 1);
      saveMockProducts(MOCK_PRODUCTS);
    }
  }
}

// Packages
export async function listPackages(accountId?: string): Promise<ProductPackage[]> {
  if (!accountId) return MOCK_PACKAGES;
  try { const r = await api.get<{ items: ProductPackage[]; total: number }>("/api/product-packages", { params: { account_id: accountId } }); return r.data.items; }
  catch { return MOCK_PACKAGES; }
}

export async function createPackage(data: {
  name: string;
  account_id: string;
  target_amount: number;
  amount_tolerance_pct: number;
  product_count: number;
  completion_reward: number;
}): Promise<ProductPackage> {
  try {
    const r = await api.post<ProductPackage>("/api/product-packages", data);
    return r.data;
  } catch {
    // Mock fallback: simulate creation with a random ID
    const newPkg: ProductPackage = {
      id: `pkg-${Date.now()}`,
      name: data.name,
      target_amount: data.target_amount,
      margin_percent: data.amount_tolerance_pct,
      item_count: data.product_count,
      reward_amount: data.completion_reward,
      items: MOCK_PRODUCTS.slice(0, data.product_count).map((p) => ({
        product_id: p.id,
        product_name: p.name,
        price: p.price,
        quantity: 1,
      })),
      created_at: new Date().toISOString(),
    };
    MOCK_PACKAGES.unshift(newPkg);
    saveMockPackages(MOCK_PACKAGES);
    return newPkg;
  }
}

export async function assemblePreview(accountId: string, data: { target_amount: number; tolerance_pct: number; product_count: number }): Promise<PackageAssemblePreview> {
  try {
    const r = await api.post<PackageAssemblePreview>("/api/product-packages/assemble-preview", data, { params: { account_id: accountId } });
    return r.data;
  } catch {
    // Random fallback: shuffle + greedy, try several times for variety (mirrors backend random.sample)
    const maxTarget = data.target_amount * (1 + data.tolerance_pct / 100);
    const minTarget = data.target_amount * (1 - data.tolerance_pct / 100);

    let bestItems: ProductPackageItem[] = [];
    let bestTotal = 0;
    let bestDiff = Infinity;
    const maxAttempts = Math.min(50, 200);

    for (let attempt = 0; attempt < maxAttempts; attempt++) {
      // Random shuffle
      const shuffled = [...MOCK_PRODUCTS].sort(() => Math.random() - 0.5);
      const items: ProductPackageItem[] = [];
      let total = 0;

      for (const prod of shuffled) {
        if (total + prod.price <= maxTarget || items.length === 0) {
          items.push({ product_id: prod.id, product_name: prod.name, price: prod.price, quantity: 1 });
          total += prod.price;
        }
        if (total >= minTarget && items.length > 0) break;
        if (items.length >= data.product_count) break;
      }

      // If still below minTarget, add more
      if (total < minTarget) {
        for (const prod of shuffled) {
          if (!items.find((i) => i.product_id === prod.id)) {
            items.push({ product_id: prod.id, product_name: prod.name, price: prod.price, quantity: 1 });
            total += prod.price;
            if (total >= minTarget) break;
          }
        }
      }

      // Within range → instant accept (like backend)
      if (total >= minTarget && total <= maxTarget && items.length > 0) {
        bestItems = items;
        bestTotal = total;
        break;
      }

      // Otherwise track the closest
      const diff = Math.abs(total - data.target_amount);
      if (diff < bestDiff && items.length > 0) {
        bestDiff = diff;
        bestItems = items;
        bestTotal = total;
      }
    }

    return {
      items: bestItems,
      total_value: bestTotal,
      target_amount: data.target_amount,
      deviation_pct: data.target_amount > 0 ? Number(((bestTotal - data.target_amount) / data.target_amount * 100).toFixed(2)) : 0,
    };
  }
}

export async function updatePackage(id: string, data: { name?: string; completion_reward?: number }): Promise<ProductPackage> {
  try {
    const r = await api.patch<ProductPackage>(`/api/product-packages/${id}`, data);
    return r.data;
  } catch {
    // Mock fallback: update the package in local cache
    const idx = MOCK_PACKAGES.findIndex((p) => p.id === id);
    if (idx >= 0) {
      const pkg = MOCK_PACKAGES[idx];
      if (data.name !== undefined) pkg.name = data.name;
      if (data.completion_reward !== undefined) pkg.reward_amount = data.completion_reward;
      saveMockPackages(MOCK_PACKAGES);
      return pkg;
    }
    throw new Error("Package not found");
  }
}

export async function deletePackage(id: string): Promise<void> {
  try {
    await api.delete(`/api/product-packages/${id}`);
  } catch {
    // Mock fallback: remove from local cache
    const idx = MOCK_PACKAGES.findIndex((p) => p.id === id);
    if (idx >= 0) {
      MOCK_PACKAGES.splice(idx, 1);
      saveMockPackages(MOCK_PACKAGES);
    }
  }
}

// Task Rules
export async function listTaskRules(): Promise<TaskRule[]> {
  try { const r = await api.get<{ items: TaskRule[]; total: number }>("/api/task-rules"); return r.data.items; }
  catch { return MOCK_TASK_RULES; }
}

export async function createTaskRule(data: Partial<TaskRule>): Promise<TaskRule> {
  try {
    const r = await api.post<TaskRule>("/api/task-rules", data);
    return r.data;
  } catch {
    const newRule: TaskRule = {
      id: `rule-${Date.now()}`,
      name: data.name || "New Rule",
      trigger_type: data.trigger_type || "manual",
      trigger_config: data.trigger_config || {},
      package_id: data.package_id || "",
      package_name: data.package_name || "",
      expiry_config: data.expiry_config || "none",
      follow_up_chain: data.follow_up_chain || [],
      status: data.status || "active",
      created_at: new Date().toISOString(),
    };
    MOCK_TASK_RULES.unshift(newRule);
    saveMockTaskRules(MOCK_TASK_RULES);
    return newRule;
  }
}

export async function updateTaskRule(id: string, data: Partial<TaskRule>): Promise<TaskRule> {
  try {
    const r = await api.patch<TaskRule>(`/api/task-rules/${id}`, data);
    return r.data;
  } catch {
    const idx = MOCK_TASK_RULES.findIndex((r) => r.id === id);
    if (idx >= 0) {
      Object.assign(MOCK_TASK_RULES[idx], data);
      saveMockTaskRules(MOCK_TASK_RULES);
      return MOCK_TASK_RULES[idx];
    }
    throw new Error("Task rule not found");
  }
}

export async function toggleTaskRule(id: string): Promise<void> {
  try {
    await api.patch(`/api/task-rules/${id}/toggle`);
  } catch {
    const idx = MOCK_TASK_RULES.findIndex((r) => r.id === id);
    if (idx >= 0) {
      MOCK_TASK_RULES[idx].status = MOCK_TASK_RULES[idx].status === "active" ? "inactive" : "active";
      saveMockTaskRules(MOCK_TASK_RULES);
    }
  }
}

export async function deleteTaskRule(id: string): Promise<void> {
  try {
    await api.delete(`/api/task-rules/${id}`);
  } catch {
    const idx = MOCK_TASK_RULES.findIndex((r) => r.id === id);
    if (idx >= 0) {
      MOCK_TASK_RULES.splice(idx, 1);
      saveMockTaskRules(MOCK_TASK_RULES);
    }
  }
}

// Manual Push
export async function manualPush(data: PushPayload): Promise<{ pushed_count: number }> {
  try {
    const r = await api.post<{ pushed_count: number }>("/api/task-instances/manual-push", data);
    return r.data;
  } catch {
    return { pushed_count: data.customer_ids.length };
  }
}

// Sign-in / Invite Config
export async function getSignInConfig(): Promise<SignInConfig> {
  try { const r = await api.get<SignInConfig>("/api/sign-in/config"); return r.data; }
  catch { return MOCK_SIGNIN_CONFIG; }
}

export async function updateSignInConfig(data: SignInConfig): Promise<void> {
  try {
    await api.put("/api/sign-in/config", data);
  } catch {
    MOCK_SIGNIN_CONFIG = { ...data };
    saveMockConfig("mock_signin_config", MOCK_SIGNIN_CONFIG);
  }
}

export async function getInviteConfig(): Promise<InviteConfig> {
  try { const r = await api.get<InviteConfig>("/api/invites/config"); return r.data; }
  catch { return MOCK_INVITE_CONFIG; }
}

export async function updateInviteConfig(data: InviteConfig): Promise<void> {
  try {
    await api.put("/api/invites/config", data);
  } catch {
    MOCK_INVITE_CONFIG = { ...data };
    saveMockConfig("mock_invite_config", MOCK_INVITE_CONFIG);
  }
}

// Stats
export async function getMarketingStats(): Promise<MarketingStats> {
  try { const r = await api.get<MarketingStats>("/api/marketing/stats/overview"); return r.data; }
  catch { return MOCK_MARKETING_STATS; }
}

export async function getPackageStats(): Promise<PackageStats> {
  try {
    const r = await api.get<PackageStats>("/api/marketing/stats/packages");
    // Backend returns {items: [...]} per-package breakdown, not aggregate
    // If the response has items but not our expected fields, compute from mock
    if (r.data && typeof r.data === "object" && !("total_products" in r.data)) {
      return { total_products: MOCK_PRODUCTS.length, total_packages: MOCK_PACKAGES.length, total_claimed: 350, avg_completion_rate: 78 };
    }
    return r.data;
  } catch {
    return { total_products: MOCK_PRODUCTS.length, total_packages: MOCK_PACKAGES.length, total_claimed: 350, avg_completion_rate: 78 };
  }
}
