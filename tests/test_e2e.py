import os
import time

from playwright.sync_api import Page, expect


def sign_in(page: Page):
    page.goto(os.getenv("APP_URL", "http://127.0.0.1:8000"))
    expect(page.get_by_role("heading", name="Bienvenido de vuelta")).to_be_visible()
    page.locator("#login-user").fill(os.getenv("INVENTORY_ADMIN_USER", "test-admin"))
    page.locator("#login-password").fill(os.getenv("INVENTORY_ADMIN_PASSWORD", "test-password"))
    page.locator("#login-submit").click()
    expect(page.get_by_role("heading", name="Inventario")).to_be_visible()


def test_inventory_crud_and_low_stock_filter(page: Page):
    sign_in(page)
    expect(page.get_by_role("heading", name="Inventario")).to_be_visible()
    expect(page.get_by_text("API conectada")).to_be_visible()
    initial_count = int(page.locator("#stat-products").inner_text())
    initial_low_count = int(page.locator("#stat-low").inner_text())
    sku = f"AUDIO-{time.time_ns()}"
    name = "Audífonos E2E " + sku[-6:]

    page.locator("#add-product").click()
    page.locator("#sku").fill(sku)
    page.locator("#name").fill(name)
    page.locator("#category").fill("Electrónica")
    page.locator("#location").fill("Estante B-04")
    page.locator("#quantity").fill("12")
    page.locator("#min-stock").fill("5")
    page.locator("#unit-price").fill("899.90")
    page.locator("#save-product").click()
    expect(page.get_by_text(name)).to_be_visible()
    item_row = page.locator("#product-list tr").filter(has_text=sku)
    expect(item_row.locator(".stock-cell strong")).to_have_text("12")
    expect(page.locator("#stat-products")).to_have_text(str(initial_count + 1))

    page.get_by_role("button", name=f"Editar {name}").click()
    page.locator("#quantity").fill("3")
    page.locator("#save-product").click()
    expect(item_row.locator(".status-tag.low")).to_be_visible()
    expect(page.locator("#stat-low")).to_have_text(str(initial_low_count + 1))

    page.locator("#search").fill(sku)
    page.locator("#stock-filter").select_option("low")
    expect(page.get_by_text(name)).to_be_visible()
    page.once("dialog", lambda dialog: dialog.accept())
    page.get_by_role("button", name=f"Eliminar {name}").click()
    expect(page.get_by_text("No encontramos productos")).to_be_visible()
    expect(page.locator("#stat-products")).to_have_text(str(initial_count))


def test_search_shows_empty_state_and_reset(page: Page):
    sign_in(page)
    page.locator("#search").fill("producto inexistente")
    expect(page.get_by_text("No encontramos productos")).to_be_visible()
    expect(page.locator("#empty-add")).to_be_hidden()


def test_remember_me_restores_session_and_logout_ends_it(page: Page):
    sign_in(page)
    expect(page.locator("#remember-me")).to_be_checked()
    page.reload()
    expect(page.get_by_role("heading", name="Inventario")).to_be_visible()
    page.locator("#logout").click()
    expect(page.get_by_role("heading", name="Bienvenido de vuelta")).to_be_visible()
