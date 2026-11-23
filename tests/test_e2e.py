import os

from playwright.sync_api import Page, expect


def test_task_flow(page: Page):
    base_url = os.getenv("APP_URL", "http://127.0.0.1:8000")
    page.goto(base_url)
    expect(page.get_by_role("heading", name="Lista de tareas")).to_be_visible()
    expect(page.get_by_text("Frontend y API conectados")).to_be_visible()
    page.get_by_label("Nueva tarea").fill("Verificar extremo a extremo")
    page.get_by_role("button", name="Agregar").click()
    expect(page.get_by_text("Verificar extremo a extremo")).to_be_visible()
    page.get_by_role("button", name="Completar Verificar extremo a extremo").click()
    expect(page.get_by_label("Completada")).to_be_visible()


def test_empty_submission_is_blocked_by_browser(page: Page):
    page.goto(os.getenv("APP_URL", "http://127.0.0.1:8000"))
    expect(page.get_by_role("button", name="Agregar")).to_be_visible()
    assert page.locator("#task-title").get_attribute("required") is not None
