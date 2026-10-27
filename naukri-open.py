"""Open the Naukri profile in Edge and alternate its displayed name hourly."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

try:
    from selenium import webdriver
    from selenium.common.exceptions import (
        InvalidSessionIdException,
        TimeoutException,
        WebDriverException,
    )
    from selenium.webdriver.common.by import By
    from selenium.webdriver.edge.options import Options
    from selenium.webdriver.remote.webelement import WebElement
    from selenium.webdriver.remote.webdriver import WebDriver
    from selenium.webdriver.support.ui import WebDriverWait
except ImportError as error:
    raise SystemExit(
        "Selenium is required. Run with: "
        "uv run --no-project --with selenium python naukri-open.py"
    ) from error


PROFILE_URL = "https://www.naukri.com/mnjuser/profile"
NAME_VARIANTS = ("Chayan Sehgal", "Chayan S")
INTERVAL_SECONDS = 30 * 60
DEBUGGING_PORT = 9222


def find_edge_executable() -> Path:
    configured_path = os.environ.get("EDGE_EXECUTABLE")
    candidates = [Path(configured_path)] if configured_path else []

    for variable in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
        base = os.environ.get(variable)
        if base:
            candidates.append(Path(base) / "Microsoft" / "Edge" / "Application" / "msedge.exe")

    for candidate in candidates:
        if candidate.is_file():
            return candidate

    located_executable = shutil.which("msedge")
    if located_executable:
        return Path(located_executable)
    if configured_path:
        raise FileNotFoundError(f"Edge executable does not exist: {configured_path}")
    raise FileNotFoundError(
        "Could not find msedge.exe. Set EDGE_EXECUTABLE to its full path."
    )


def find_edge_user_data_dir() -> Path:
    configured_path = os.environ.get("NAUKRI_EDGE_USER_DATA_DIR")
    if configured_path:
        user_data_dir = Path(configured_path)
    else:
        local_app_data = os.environ.get("LOCALAPPDATA")
        if not local_app_data:
            raise RuntimeError(
                "LOCALAPPDATA is missing; set NAUKRI_EDGE_USER_DATA_DIR."
            )
        user_data_dir = Path(local_app_data) / "Jobhunt" / "NaukriEdgeProfile"

    user_data_dir.mkdir(parents=True, exist_ok=True)
    return user_data_dir


def page_lines(driver: WebDriver) -> set[str]:
    lines = {
        re.sub(r"\s+", " ", line).strip()
        for line in driver.find_element(By.TAG_NAME, "body").text.splitlines()
    }
    return lines


def visible_profile_name(driver: WebDriver) -> str:
    lines = page_lines(driver)
    matches = [name for name in NAME_VARIANTS if name in lines]
    if len(matches) != 1:
        raise RuntimeError(
            "Could not identify exactly one expected profile name on the page. "
            "Confirm you are signed in and that the profile page has finished loading."
        )
    return matches[0]


def wait_for_profile_name(driver: WebDriver, expected_name: str) -> None:
    WebDriverWait(driver, 30).until(
        lambda browser: expected_name in page_lines(browser)
    )


def wait_for_profile_page(driver: WebDriver, timeout: int = 30) -> None:
    WebDriverWait(driver, timeout).until(
        lambda browser: any(name in page_lines(browser) for name in NAME_VARIANTS)
    )


def click_profile_edit(driver: WebDriver, current_name: str) -> None:
    control = driver.execute_script(
        """const currentName = arguments[0];
            const controls = [...document.querySelectorAll(
                'button, a, [role="button"], input[type="button"], input[type="submit"]'
            )].filter((element) => {
                const text = [
                    element.innerText,
                    element.getAttribute('aria-label'),
                    element.getAttribute('title'),
                    element.value
                ].filter(Boolean).join(' ');
                return /edit/i.test(text) && element.getClientRects().length > 0;
            });
            const candidates = controls.map((control) => {
                let container = control;
                while (container && !container.innerText?.includes(currentName)) {
                    container = container.parentElement;
                }
                return container ? { control, container } : null;
            }).filter(Boolean);
            candidates.sort((left, right) =>
                left.container.innerText.length - right.container.innerText.length
            );
            return candidates.length ? candidates[0].control : null;
        """,
        current_name,
    )
    if control is None:
        raise RuntimeError(
            "Could not find an Edit control near the profile name. "
            "Naukri may have changed its profile page."
        )
    control.click()


def editable_fields(
    driver: WebDriver,
) -> list[tuple[WebElement, dict[str, object]]]:
    elements = driver.find_elements(
        By.CSS_SELECTOR, "input:not([type=hidden]), textarea"
    )
    metadata = driver.execute_script(
        """return arguments[0].map((element) => {
            const labels = element.labels
                ? [...element.labels].map((label) => label.innerText).join(' ')
                : '';
            const style = window.getComputedStyle(element);
            return {
                visible: element.getClientRects().length > 0 &&
                    style.visibility !== 'hidden' && style.display !== 'none',
                enabled: !element.disabled,
                value: element.value || '',
                description: [
                    labels,
                    element.getAttribute('aria-label'),
                    element.getAttribute('name'),
                    element.id,
                    element.getAttribute('placeholder')
                ].filter(Boolean).join(' ').toLowerCase()
            };
        });""",
        elements,
    )
    return list(zip(elements, metadata))


def find_name_fields(
    driver: WebDriver, current_name: str
) -> tuple[WebElement, WebElement | None]:
    fields = [
        (element, field)
        for element, field in editable_fields(driver)
        if field["visible"] and field["enabled"]
    ]

    first_name = [
        (element, field)
        for element, field in fields
        if re.search(r"\b(first|given)[ _-]*name\b", str(field["description"]))
    ]
    last_name = [
        (element, field)
        for element, field in fields
        if re.search(r"\b(last|sur|family)[ _-]*name\b", str(field["description"]))
    ]
    if len(first_name) == 1 and len(last_name) == 1:
        return first_name[0][0], last_name[0][0]

    full_name = [
        (element, field)
        for element, field in fields
        if re.search(r"\b(full[ _-]*name|name)\b", str(field["description"]))
        and not re.search(
            r"\b(first|given|last|sur|family)[ _-]*name\b",
            str(field["description"]),
        )
    ]
    current_name_fields = [
        (element, field)
        for element, field in fields
        if str(field["value"]).strip() == current_name
    ]
    candidates = full_name or current_name_fields
    if len(candidates) == 1:
        return candidates[0][0], None

    raise RuntimeError(
        "Could not identify a unique name field (or first/last name pair) "
        "in the profile editor; no changes were submitted."
    )


def save_profile(driver: WebDriver) -> None:
    buttons = driver.find_elements(
        By.CSS_SELECTOR,
        "button, input[type=button], input[type=submit], [role=button]",
    )
    visible_buttons = [
        button
        for button in buttons
        if button.is_displayed()
        and button.is_enabled()
        and any(
            re.fullmatch(
                r"(save|update)( changes)?",
                value.strip(),
                re.IGNORECASE,
            )
            for value in (
                button.text,
                button.get_attribute("aria-label"),
                button.get_attribute("title"),
                button.get_attribute("value"),
            )
            if value
        )
    ]
    if not visible_buttons:
        raise RuntimeError(
            "Could not find a visible Save or Update button; no changes were submitted."
        )
    if len(visible_buttons) > 1:
        raise RuntimeError(
            "Found multiple visible Save or Update buttons; no changes were submitted."
        )
    visible_buttons[0].click()


def set_profile_name(
    driver: WebDriver, current_name: str, target_name: str
) -> None:
    click_profile_edit(driver, current_name)
    first_field, last_field = find_name_fields(driver, current_name)
    first_field.clear()
    first_field.send_keys("Chayan")
    if last_field is not None:
        last_field.clear()
        last_field.send_keys("S" if target_name == "Chayan S" else "Sehgal")
    else:
        first_field.clear()
        first_field.send_keys(target_name)

    save_profile(driver)
    wait_for_profile_name(driver, target_name)
    if visible_profile_name(driver) != target_name:
        raise RuntimeError(
            f"Naukri did not show the expected name {target_name!r} after saving."
        )


def start_edge_session(
    executable: Path, user_data_dir: Path
) -> tuple[WebDriver, subprocess.Popen[bytes]]:
    edge_process = subprocess.Popen(
        [
            str(executable),
            f"--user-data-dir={user_data_dir}",
            "--profile-directory=Default",
            "--no-first-run",
            f"--remote-debugging-port={DEBUGGING_PORT}",
            PROFILE_URL,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if edge_process.poll() is not None:
            raise RuntimeError(
                f"Edge exited during startup with status {edge_process.returncode}."
            )
        try:
            with urlopen(
                f"http://127.0.0.1:{DEBUGGING_PORT}/json/version", timeout=1
            ):
                break
        except (OSError, URLError):
            time.sleep(0.25)
    else:
        raise RuntimeError(
            "Edge did not enable its debugging endpoint. Close other windows "
            "using this dedicated profile and try again."
        )

    options = Options()
    options.debugger_address = f"127.0.0.1:{DEBUGGING_PORT}"
    return webdriver.Edge(options=options), edge_process


def main() -> None:
    if sys.platform != "win32":
        raise SystemExit("This script is configured to use Edge on Windows.")

    edge_executable = find_edge_executable()
    user_data_dir = find_edge_user_data_dir()
    print(f"Using dedicated Edge profile: {user_data_dir}")
    print("Sign into Naukri in the Edge window if prompted.")
    try:
        driver, edge_process = start_edge_session(edge_executable, user_data_dir)
    except WebDriverException as error:
        raise RuntimeError(
            f"Could not attach to Edge: {error.msg}"
        ) from error
    except OSError as error:
        raise RuntimeError(f"Could not start Edge: {error}") from error

    try:
        driver.get(PROFILE_URL)
        print("If prompted, sign into Naukri in the Edge window; waiting up to 5 minutes.")
        try:
            wait_for_profile_page(driver, timeout=300)
        except TimeoutException as error:
            raise RuntimeError(
                "The Naukri profile name did not appear. Sign into Naukri in the "
                "dedicated Edge profile, then restart the script."
            ) from error
        print(f"Opened {PROFILE_URL}")

        while True:
            try:
                current_name = visible_profile_name(driver)
            except InvalidSessionIdException:
                print("Edge was closed. Reopening the automation browser...")
                driver, edge_process = start_edge_session(
                    edge_executable, user_data_dir
                )
                driver.get(PROFILE_URL)
                wait_for_profile_page(driver, timeout=300)
                current_name = visible_profile_name(driver)

            target_name = (
                NAME_VARIANTS[1]
                if current_name == NAME_VARIANTS[0]
                else NAME_VARIANTS[0]
            )
            set_profile_name(driver, current_name, target_name)
            print(f"Profile name updated to {target_name}.")
            print("Next change in 30 minutes. Press Ctrl+C to stop.")
            time.sleep(INTERVAL_SECONDS)
    finally:
        driver.quit()


if __name__ == "__main__":
    main()