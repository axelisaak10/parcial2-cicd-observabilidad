const { escapeHtml, formatCurrency, formatCount, stockState, renderProducts } = require("../inventory-view");

const sample = { id: 1, sku: "TOOL-1", name: "Taladro", category: "Herramientas", quantity: 4, min_stock: 5, unit_price: 1200, location: "Estante A-1" };

describe("inventory frontend helpers", () => {
  test("escapes product data before rendering HTML", () => {
    expect(escapeHtml(`<script>alert("x")</script>`)).toBe("&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;");
    expect(escapeHtml("A&B's")).toBe("A&amp;B&#39;s");
    expect(escapeHtml(null)).toBe("");
    expect(renderProducts([{ ...sample, name: "<img src=x onerror=alert(1)>" }])).not.toContain("<img src=x");
  });

  test("formats inventory value and product counts in Spanish", () => {
    expect(formatCurrency(1200)).toContain("1,200");
    expect(formatCount(1)).toBe("1 producto");
    expect(formatCount(0)).toBe("0 productos");
  });

  test("identifies healthy, low and empty stock", () => {
    expect(stockState({ quantity: 7, min_stock: 5 }).key).toBe("ok");
    expect(stockState({ quantity: 4, min_stock: 5 }).key).toBe("low");
    expect(stockState({ quantity: 0, min_stock: 5 }).key).toBe("out");
  });

  test("renders an inventory row with edit and delete actions", () => {
    const html = renderProducts([sample]);
    expect(html).toContain("Taladro");
    expect(html).toContain("SKU: TOOL-1");
    expect(html).toContain('data-action="edit" data-id="1"');
    expect(html).toContain('data-action="delete" data-id="1"');
    expect(html).toContain("Stock bajo");
  });
});
