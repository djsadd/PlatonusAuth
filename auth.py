import os
from typing import Any, Dict

from playwright.sync_api import Error, TimeoutError, sync_playwright


LOGIN_URL = os.getenv("PLATONUS_LOGIN_URL", "https://platonus.tau-edu.kz/mail?type=1")
BASE_URL = os.getenv("PLATONUS_BASE_URL", "https://platonus.tau-edu.kz")
DEFAULT_TIMEOUT_MS = int(os.getenv("PLAYWRIGHT_TIMEOUT_MS", "60000"))
STUDENT_ROLE = "\u0441\u0442\u0443\u0434\u0435\u043d\u0442"
TEACHER_ROLE = "\u043f\u0440\u0435\u043f\u043e\u0434\u0430\u0432\u0430\u0442\u0435\u043b\u044c"
LIBRARY_ROLE = "\u0431\u0438\u0431\u043b\u0438\u043e\u0442\u0435\u043a\u0430"
DEANERY_ROLE = "\u0434\u0435\u043a\u0430\u043d\u0430\u0442"


def _fill_first_available(page, selectors, value, field_name):
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            locator.wait_for(state="visible", timeout=5000)
            locator.fill(value)
            return selector
        except TimeoutError:
            continue
    raise RuntimeError(f"Login page field not found: {field_name}")


def _click_first_available(page, selectors, element_name):
    for selector in selectors:
        locator = page.locator(selector).first
        try:
            locator.wait_for(state="visible", timeout=5000)
            locator.click()
            return selector
        except TimeoutError:
            continue
    raise RuntimeError(f"Login page button not found: {element_name}")


def _get_token(page):
    script = (
        "() => localStorage.getItem('token') || "
        "localStorage.getItem('access_token') || "
        "sessionStorage.getItem('token') || "
        "sessionStorage.getItem('access_token') || ''"
    )
    try:
        return page.evaluate(script)
    except Error:
        page.wait_for_load_state("domcontentloaded")
        return page.evaluate(script)


def auth(username: str, password: str) -> Dict[str, Any]:
    print("Starting Platonus authentication for user:", username)

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(
            headless=os.getenv("PLAYWRIGHT_HEADLESS", "true").lower() != "false"
        )
        page = browser.new_page()
        page.set_default_timeout(DEFAULT_TIMEOUT_MS)

        try:
            page.goto(LOGIN_URL, wait_until="domcontentloaded")

            _fill_first_available(
                page,
                ["#login_input", "#username", "input[name='username']", "input[type='text']"],
                username,
                "username",
            )
            _fill_first_available(
                page,
                ["#pass_input", "#password", "input[name='password']", "input[type='password']"],
                password,
                "password",
            )
            _click_first_available(
                page,
                ["#Submit1", "#kc-login", "input[type='submit']", "button[type='submit']"],
                "submit",
            )

            page.wait_for_load_state("networkidle")

            cookies = page.context.cookies(BASE_URL)
            cookie_map = {cookie["name"]: cookie["value"] for cookie in cookies}
            cookie_header = "; ".join(
                f"{cookie['name']}={cookie['value']}" for cookie in cookies
            )
            user_agent = page.evaluate("() => navigator.userAgent")
            sid_value = cookie_map.get("plt_sid") or cookie_map.get("sid") or ""
            token_value = _get_token(page)

            headers = {
                "cookie": cookie_header,
                "sid": sid_value,
                "token": token_value,
                "user-agent": user_agent,
                "accept": "application/json",
                "accept-language": "kz",
            }

            person_id_response = page.request.get(
                f"{BASE_URL}/rest/api/person/personID",
                headers=headers,
            )
            try:
                person_data = person_id_response.json()
            except ValueError as exc:
                print("person_id_response_status:", person_id_response.status)
                print("person_id_response_text:", person_id_response.text())
                raise RuntimeError("personID response is not JSON") from exc

            person_id = person_data.get("personID")
            if not person_id:
                retry_response = page.request.get(
                    f"{BASE_URL}/rest/api/person/personID",
                    headers=headers,
                )
                try:
                    person_id = retry_response.json().get("personID")
                except ValueError as exc:
                    print("person_id_retry_status:", retry_response.status)
                    print("person_id_retry_text:", retry_response.text())
                    raise RuntimeError("personID retry response is not JSON") from exc

            print("person_id_response:", person_data)
            print("person_id_response_status:", person_id_response.status)
            print("cookies:", cookie_map)
            print("user_agent:", user_agent)
            print("sid:", sid_value)
            print("token:", token_value)
            print("request_headers:", headers)

            roles_response = page.request.get(
                f"{BASE_URL}/rest/api/person/roles",
                headers=headers,
            )
            try:
                roles_data = roles_response.json()
            except ValueError as exc:
                print("roles_response_status:", roles_response.status)
                print("roles_response_text:", roles_response.text())
                raise RuntimeError("roles response is not JSON") from exc

            role_names = [
                str(role.get("name", "")).strip().lower()
                for role in roles_data
                if isinstance(role, dict)
            ]
            print("roles_response:", roles_data)

            if STUDENT_ROLE in role_names:
                student_info_response = page.request.get(
                    f"{BASE_URL}/rest/student/studentInfo/{person_id}/ru",
                    headers=headers,
                )
                try:
                    student_info = student_info_response.json()
                except ValueError as exc:
                    print("student_info_response_status:", student_info_response.status)
                    print("student_info_response_text:", student_info_response.text())
                    raise RuntimeError("studentInfo response is not JSON") from exc
                print("student_info_response:", student_info)
                return {"role": STUDENT_ROLE, "info": student_info}

            if TEACHER_ROLE in role_names or LIBRARY_ROLE in role_names:
                employee_info_response = page.request.get(
                    f"{BASE_URL}/rest/employee/employeeInfo/{person_id}/3/ru?dn=1",
                    headers=headers,
                )
                try:
                    employee_info = employee_info_response.json()
                except ValueError as exc:
                    print("employee_info_response_status:", employee_info_response.status)
                    print("employee_info_response_text:", employee_info_response.text())
                    raise RuntimeError("employeeInfo response is not JSON") from exc
                print("employee_info_response:", employee_info)
                role = TEACHER_ROLE if TEACHER_ROLE in role_names else LIBRARY_ROLE
                return {"role": role, "info": employee_info}

            if DEANERY_ROLE in role_names:
                raise RuntimeError("Selected role is temporarily disabled.")

            raise RuntimeError("Role is not supported for login.")
        finally:
            browser.close()


if __name__ == "__main__":
    env_username = os.getenv("PLATONUS_USERNAME")
    env_password = os.getenv("PLATONUS_PASSWORD")

    if not env_username or not env_password:
        raise SystemExit(
            "Environment variables PLATONUS_USERNAME and PLATONUS_PASSWORD must be set."
        )

    result = auth(env_username, env_password)
    print(result)
