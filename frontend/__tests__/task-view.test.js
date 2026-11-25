const { escapeHtml, formatTaskCount, renderTasks } = require("../task-view");

describe("frontend task rendering", () => {
  test("escapes untrusted task titles", () => {
    expect(escapeHtml(`<script>alert("x")</script>`)).toBe(
      "&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;"
    );
  });

  test("uses singular and plural task counts", () => {
    expect(formatTaskCount(1)).toBe("1 ELEMENTO");
    expect(formatTaskCount(0)).toBe("0 ELEMENTOS");
    expect(formatTaskCount(3)).toBe("3 ELEMENTOS");
  });

  test("renders an incomplete task with its completion control", () => {
    expect(renderTasks([{ id: 7, title: "Revisar API", done: false }])).toContain(
      'data-id="7" aria-label="Completar Revisar API"'
    );
  });

  test("renders a completed task as a checked item without a button", () => {
    const html = renderTasks([{ id: 7, title: "Revisar API", done: true }]);
    expect(html).toContain("class=\"done\"");
    expect(html).toContain("aria-label='Completada'");
    expect(html).not.toContain("<button");
  });
});
