const API = window.API_BASE || "";
const { renderTasks, formatTaskCount } = window.TaskView;
const list = document.querySelector("#task-list");
const empty = document.querySelector("#empty-state");
const count = document.querySelector("#task-count");
const error = document.querySelector("#error");

async function request(path, options) {
  const response = await fetch(`${API}${path}`, { headers: { "Content-Type": "application/json" }, ...options });
  if (!response.ok) throw new Error(`Error ${response.status}: ${response.statusText}`);
  return response.json();
}

async function loadTasks() {
  const tasks = await request("/api/tasks");
  list.innerHTML = renderTasks(tasks);
  empty.hidden = tasks.length > 0;
  count.textContent = formatTaskCount(tasks.length);
}

document.querySelector("#task-form").addEventListener("submit", async event => {
  event.preventDefault(); error.hidden = true;
  const input = document.querySelector("#task-title");
  try { await request("/api/tasks", { method: "POST", body: JSON.stringify({ title: input.value.trim() }) }); input.value = ""; await loadTasks(); }
  catch (problem) { error.textContent = problem.message; error.hidden = false; }
});

list.addEventListener("click", async event => {
  const button = event.target.closest("button[data-id]"); if (!button) return;
  try { await request(`/api/tasks/${button.dataset.id}`, { method: "PATCH" }); await loadTasks(); }
  catch (problem) { error.textContent = problem.message; error.hidden = false; }
});

request("/health").then(() => { document.querySelector("#health-label").textContent = "Frontend y API conectados"; }).catch(() => { document.querySelector("#health-label").textContent = "API no disponible"; });
loadTasks().catch(problem => { error.textContent = problem.message; error.hidden = false; });
