(function (root, factory) {
  const helpers = factory();
  if (typeof module === "object" && module.exports) module.exports = helpers;
  else root.TaskView = helpers;
})(typeof globalThis === "object" ? globalThis : this, function () {
  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, character => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    })[character]);
  }

  function formatTaskCount(count) {
    return `${count} ${count === 1 ? "ELEMENTO" : "ELEMENTOS"}`;
  }

  function renderTasks(tasks) {
    return tasks.map(task => {
      const title = escapeHtml(task.title);
      const state = task.done ? "done" : "";
      const action = task.done
        ? "<span aria-label='Completada'>✓</span>"
        : `<button class="task-action" data-id="${Number(task.id)}" aria-label="Completar ${title}">Completar ↗</button>`;
      return `<li class="${state}"><span class="task-title">${title}</span>${action}</li>`;
    }).join("");
  }

  return { escapeHtml, formatTaskCount, renderTasks };
});
