(function (root, factory) {
  const helpers = factory();
  if (typeof module === "object" && module.exports) module.exports = helpers;
  else root.InventoryView = helpers;
})(typeof globalThis === "object" ? globalThis : this, function () {
  const escapeHtml = value => String(value ?? "").replace(/[&<>"']/g, character => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[character]);

  const formatCurrency = amount => new Intl.NumberFormat("es-MX", {
    style: "currency", currency: "MXN", maximumFractionDigits: 2
  }).format(Number(amount) || 0);

  const stockState = item => {
    if (Number(item.quantity) === 0) return { key: "out", label: "Agotado" };
    if (Number(item.quantity) <= Number(item.min_stock)) return { key: "low", label: "Stock bajo" };
    return { key: "ok", label: "Disponible" };
  };

  function renderProducts(products) {
    return products.map(item => {
      const id = Number(item.id);
      const state = stockState(item);
      const quantity = Number(item.quantity);
      const minimum = Math.max(Number(item.min_stock), 1);
      const fill = Math.min(100, Math.round(quantity / (minimum * 3) * 100));
      const initial = escapeHtml((item.name || "?").trim().charAt(0).toUpperCase());
      return `<tr data-product-id="${id}">
        <td><div class="product-cell"><span class="product-avatar">${initial}</span><span class="product-info"><strong>${escapeHtml(item.name)}</strong><small>SKU: ${escapeHtml(item.sku)}</small></span></div></td>
        <td><span class="category-tag">${escapeHtml(item.category)}</span></td>
        <td class="price-cell">${formatCurrency(item.unit_price)}</td>
        <td><div class="stock-cell"><strong>${quantity.toLocaleString("es-MX")}</strong><small>mín. ${Number(item.min_stock).toLocaleString("es-MX")}</small><span class="stock-track"><i class="stock-fill ${state.key}" style="width:${fill}%"></i></span></div></td>
        <td class="location-cell"><span aria-hidden="true">⌖</span> ${escapeHtml(item.location)}</td>
        <td><span class="status-tag ${state.key}"><i></i>${state.label}</span></td>
        <td><div class="row-actions"><button class="icon-button edit-button" type="button" data-action="edit" data-id="${id}" aria-label="Editar ${escapeHtml(item.name)}" title="Editar">✎</button><button class="icon-button delete-button" type="button" data-action="delete" data-id="${id}" aria-label="Eliminar ${escapeHtml(item.name)}" title="Eliminar">⌫</button></div></td>
      </tr>`;
    }).join("");
  }

  function formatCount(count, singular = "producto", plural = "productos") {
    const value = Number(count) || 0;
    return `${value.toLocaleString("es-MX")} ${value === 1 ? singular : plural}`;
  }

  return { escapeHtml, formatCurrency, stockState, renderProducts, formatCount };
});
