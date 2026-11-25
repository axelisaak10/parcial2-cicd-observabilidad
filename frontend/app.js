const { renderProducts, formatCurrency, formatCount } = window.InventoryView;
const list = document.querySelector("#product-list");
const dialog = document.querySelector("#product-dialog");
const form = document.querySelector("#product-form");
const feedback = document.querySelector("#feedback");
const formError = document.querySelector("#form-error");
let allProducts = [];
let feedbackTimer;
const SESSION_KEY = "stockroom.session.v1";
const USER_KEY = "stockroom.user.v1";

function savedSession() {
  return localStorage.getItem(SESSION_KEY) || sessionStorage.getItem(SESSION_KEY) || "";
}

function showInventory(username = localStorage.getItem(USER_KEY) || sessionStorage.getItem(USER_KEY) || "admin") {
  document.querySelector("#login-screen").hidden = true;
  document.querySelector("#sidebar").hidden = false;
  document.querySelector("#inventory").hidden = false;
  document.querySelector("#active-user").textContent = username;
}

function clearSession() {
  localStorage.removeItem(SESSION_KEY);
  localStorage.removeItem(USER_KEY);
  sessionStorage.removeItem(SESSION_KEY);
  sessionStorage.removeItem(USER_KEY);
}

function showLogin(message = "") {
  document.querySelector("#login-screen").hidden = false;
  document.querySelector("#sidebar").hidden = true;
  document.querySelector("#inventory").hidden = true;
  if (message) {
    document.querySelector("#login-error").textContent = message;
    document.querySelector("#login-error").hidden = false;
  }
}

async function request(path, options = {}) {
  const token = savedSession();
  const response = await fetch(path, {
    ...options,
    headers: { ...(options.body ? { "Content-Type": "application/json" } : {}), ...(token ? { Authorization: `Bearer ${token}` } : {}), ...options.headers }
  });
  if (response.status === 204) return null;
  const data = await response.json().catch(() => ({}));
  if (response.status === 401) {
    clearSession();
    showLogin("Tu sesión expiró. Inicia sesión para continuar.");
  }
  if (!response.ok) throw new Error(data.detail || `Error ${response.status}: ${response.statusText}`);
  return data;
}

function announce(message, type = "success") {
  clearTimeout(feedbackTimer);
  feedback.textContent = message;
  feedback.className = `feedback ${type}`;
  feedback.hidden = false;
  feedbackTimer = setTimeout(() => { feedback.hidden = true; }, 5000);
}

function updateStats(summary) {
  document.querySelector("#stat-products").textContent = Number(summary.products).toLocaleString("es-MX");
  document.querySelector("#stat-units").textContent = Number(summary.units).toLocaleString("es-MX");
  document.querySelector("#stat-low").textContent = (Number(summary.low_stock) + Number(summary.out_of_stock)).toLocaleString("es-MX");
  document.querySelector("#stat-value").textContent = formatCurrency(summary.inventory_value);
  document.querySelector("#nav-alert-count").textContent = Number(summary.low_stock + summary.out_of_stock).toLocaleString("es-MX");
}

function updateCategoryOptions(categories) {
  const select = document.querySelector("#category-filter");
  const current = select.value;
  select.innerHTML = '<option value="">Todas las categorías</option>' + categories.map(category =>
    `<option value="${window.InventoryView.escapeHtml(category)}">${window.InventoryView.escapeHtml(category)}</option>`
  ).join("");
  if (categories.includes(current)) select.value = current;
}

function renderList(products) {
  list.innerHTML = renderProducts(products);
  document.querySelector("#result-count").textContent = formatCount(products.length);
  const empty = document.querySelector("#empty-state");
  empty.hidden = products.length > 0;
  if (!products.length) {
    const filtered = Boolean(document.querySelector("#search").value || document.querySelector("#category-filter").value || document.querySelector("#stock-filter").value !== "all");
    document.querySelector("#empty-title").textContent = filtered ? "No encontramos productos" : "Aún no hay productos";
    document.querySelector("#empty-copy").textContent = filtered ? "Prueba con otra búsqueda o cambia los filtros." : "Agrega tu primer producto para comenzar a controlar el inventario.";
    document.querySelector("#empty-add").hidden = filtered;
  }
}

async function loadInventory({ quiet = false } = {}) {
  const params = new URLSearchParams();
  const search = document.querySelector("#search").value.trim();
  const category = document.querySelector("#category-filter").value;
  const stock = document.querySelector("#stock-filter").value;
  if (search) params.set("search", search);
  if (category) params.set("category", category);
  if (stock !== "all") params.set("stock", stock);
  try {
    const [products, summary, categories] = await Promise.all([
      request(`/api/inventory?${params.toString()}`),
      request("/api/inventory/summary"),
      request("/api/inventory/categories")
    ]);
    allProducts = products;
    renderList(products);
    updateStats(summary);
    updateCategoryOptions(categories);
    document.querySelector("#health-label").textContent = "Todos los servicios operativos";
    document.querySelector("#api-state").textContent = "API conectada";
  } catch (problem) {
    document.querySelector("#health-label").textContent = "No se pudo conectar con la API";
    document.querySelector("#api-state").textContent = "API sin conexión";
    if (!quiet) announce(problem.message, "error");
  }
}

function openCreateDialog() {
  form.reset();
  document.querySelector("#product-id").value = "";
  document.querySelector("#quantity").value = "0";
  document.querySelector("#min-stock").value = "5";
  document.querySelector("#unit-price").value = "0";
  document.querySelector("#dialog-title").textContent = "Agregar producto";
  document.querySelector("#save-product").innerHTML = 'Guardar producto <span>↗</span>';
  formError.hidden = true;
  dialog.showModal();
}

function openEditDialog(product) {
  form.reset();
  document.querySelector("#product-id").value = product.id;
  for (const key of ["sku", "name", "category", "location", "quantity", "description"]) {
    document.querySelector(`#${key}`).value = product[key] ?? "";
  }
  document.querySelector("#min-stock").value = product.min_stock;
  document.querySelector("#unit-price").value = product.unit_price;
  document.querySelector("#dialog-title").textContent = "Editar producto";
  document.querySelector("#save-product").innerHTML = 'Guardar cambios <span>↗</span>';
  formError.hidden = true;
  dialog.showModal();
}

document.querySelector("#add-product").addEventListener("click", openCreateDialog);
document.querySelector("#empty-add").addEventListener("click", openCreateDialog);
document.querySelector("#close-dialog").addEventListener("click", () => dialog.close());
document.querySelector("#cancel-dialog").addEventListener("click", () => dialog.close());
document.querySelector("#refresh").addEventListener("click", () => loadInventory());
document.querySelector("#search").addEventListener("input", () => loadInventory({ quiet: true }));
document.querySelector("#category-filter").addEventListener("change", () => loadInventory());
document.querySelector("#stock-filter").addEventListener("change", () => loadInventory());
document.querySelector("#low-stock-link").addEventListener("click", event => {
  event.preventDefault();
  document.querySelector("#stock-filter").value = "low";
  loadInventory();
});

document.querySelector("#login-form").addEventListener("submit", async event => {
  event.preventDefault();
  const loginError = document.querySelector("#login-error");
  const button = document.querySelector("#login-submit");
  const username = document.querySelector("#login-user").value.trim();
  const password = document.querySelector("#login-password").value;
  loginError.hidden = true;
  button.disabled = true;
  button.innerHTML = 'Validando acceso <span>…</span>';
  try {
    const response = await fetch("/api/auth/login", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password })
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(data.detail || "No pudimos iniciar sesión. Verifica tus datos.");
    clearSession();
    const storage = document.querySelector("#remember-me").checked ? localStorage : sessionStorage;
    storage.setItem(SESSION_KEY, data.access_token);
    storage.setItem(USER_KEY, data.username);
    document.querySelector("#login-password").value = "";
    showInventory(data.username);
    await loadInventory();
    announce(`Hola, ${data.username}. Tu inventario está listo.`);
  } catch (problem) {
    loginError.textContent = problem.message;
    loginError.hidden = false;
  } finally {
    button.disabled = false;
    button.innerHTML = 'Iniciar sesión <span>→</span>';
  }
});

document.querySelector("#toggle-password").addEventListener("click", event => {
  const field = document.querySelector("#login-password");
  const visible = field.type === "password";
  field.type = visible ? "text" : "password";
  event.currentTarget.textContent = visible ? "Ocultar" : "Ver";
  event.currentTarget.setAttribute("aria-label", visible ? "Ocultar contraseña" : "Mostrar contraseña");
});

document.querySelector("#logout").addEventListener("click", () => {
  clearSession();
  document.querySelector("#login-password").value = "";
  showLogin();
  document.querySelector("#login-user").focus();
});

form.addEventListener("submit", async event => {
  event.preventDefault();
  formError.hidden = true;
  const item = {
    sku: document.querySelector("#sku").value,
    name: document.querySelector("#name").value,
    category: document.querySelector("#category").value,
    location: document.querySelector("#location").value,
    quantity: Number(document.querySelector("#quantity").value),
    min_stock: Number(document.querySelector("#min-stock").value),
    unit_price: Number(document.querySelector("#unit-price").value),
    description: document.querySelector("#description").value
  };
  const id = document.querySelector("#product-id").value;
  const button = document.querySelector("#save-product");
  button.disabled = true;
  try {
    await request(id ? `/api/inventory/${id}` : "/api/inventory", { method: id ? "PUT" : "POST", body: JSON.stringify(item) });
    dialog.close();
    announce(id ? "Producto actualizado correctamente." : "Producto agregado al inventario.");
    await loadInventory();
  } catch (problem) {
    formError.textContent = problem.message;
    formError.hidden = false;
  } finally {
    button.disabled = false;
  }
});

list.addEventListener("click", async event => {
  const button = event.target.closest("button[data-action]");
  if (!button) return;
  const id = Number(button.dataset.id);
  const product = allProducts.find(item => Number(item.id) === id);
  if (!product) return;
  if (button.dataset.action === "edit") return openEditDialog(product);
  if (button.dataset.action === "delete" && window.confirm(`¿Eliminar “${product.name}” (${product.sku}) del inventario?`)) {
    try {
      await request(`/api/inventory/${id}`, { method: "DELETE" });
      announce("Producto eliminado del inventario.");
      await loadInventory();
    } catch (problem) { announce(problem.message, "error"); }
  }
});

request("/health").then(() => {
  document.querySelector("#health-label").textContent = "Todos los servicios operativos";
  document.querySelector("#api-state").textContent = "API conectada";
}).catch(() => {
  document.querySelector("#health-label").textContent = "No se pudo conectar con la API";
  document.querySelector("#api-state").textContent = "API sin conexión";
});

if (savedSession()) {
  showInventory();
  loadInventory();
} else {
  showLogin();
}
