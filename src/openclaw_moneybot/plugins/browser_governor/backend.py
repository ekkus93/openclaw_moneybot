"""Bounded Playwright Firefox automation for the browser governor."""

from __future__ import annotations

import time
from pathlib import Path
from typing import Protocol, cast
from urllib.parse import urlparse

from pydantic import Field

from openclaw_moneybot.plugins.browser_governor.models import (
    BrowserExecutionRequest,
    BrowserExecutionStep,
)
from openclaw_moneybot.shared import BrowserGovernorConfig
from openclaw_moneybot.shared.base import MoneyBotModel


class BrowserAutomationError(RuntimeError):
    """Raised when bounded browser automation cannot complete safely."""


class BrowserPageSnapshot(MoneyBotModel):
    """Captured browser state at one point in an execution."""

    url: str
    page_text: str
    html: str
    page_title: str | None = None
    screenshot_png: bytes | None = None


class BrowserExecutionArtifacts(MoneyBotModel):
    """Complete before/after capture for one automated action."""

    before: BrowserPageSnapshot
    after: BrowserPageSnapshot
    result_summary: str
    applied_step_count: int = Field(ge=0)


class BrowserAutomationBackend(Protocol):
    """Protocol for bounded browser automation backends."""

    def execute(
        self,
        config: BrowserGovernorConfig,
        request: BrowserExecutionRequest,
    ) -> BrowserExecutionArtifacts: ...


class _LocatorLike(Protocol):
    def fill(self, value: str, *, timeout: int) -> None: ...

    def click(self, *, timeout: int) -> None: ...

    def text_content(self, *, timeout: int) -> str | None: ...


class _PageLike(Protocol):
    @property
    def url(self) -> str: ...

    def goto(self, url: str, *, wait_until: str, timeout: int) -> None: ...

    def locator(self, selector: str) -> _LocatorLike: ...

    def content(self) -> str: ...

    def title(self) -> str: ...

    def screenshot(self, *, type: str, full_page: bool, timeout: int) -> bytes: ...

    def text_content(self, selector: str) -> str | None: ...


class PlaywrightFirefoxBackend:
    """Run bounded browser steps with Playwright Firefox."""

    def execute(
        self,
        config: BrowserGovernorConfig,
        request: BrowserExecutionRequest,
    ) -> BrowserExecutionArtifacts:
        from playwright.sync_api import Error as PlaywrightError
        from playwright.sync_api import sync_playwright

        profile_dir = _resolve_profile_dir(config.profile_root, request.profile_id)
        profile_dir.mkdir(parents=True, exist_ok=True)

        try:
            with sync_playwright() as playwright:
                context = playwright.firefox.launch_persistent_context(
                    user_data_dir=str(profile_dir),
                    headless=config.headless,
                )
                try:
                    context.set_default_timeout(config.default_timeout_ms)
                    page = cast(
                        _PageLike,
                        context.pages[0] if context.pages else context.new_page(),
                    )
                    page.goto(
                        str(request.target_url),
                        wait_until="domcontentloaded",
                        timeout=config.navigation_timeout_ms,
                    )
                    _assert_allowed_host(page.url, config.allowed_hosts)
                    before = _capture_page(page, config)
                    applied_step_count = 0
                    for step in request.steps[: config.max_steps]:
                        _apply_step(page, step)
                        _assert_allowed_host(page.url, config.allowed_hosts)
                        applied_step_count += 1
                    after = _capture_page(page, config)
                    return BrowserExecutionArtifacts(
                        before=before,
                        after=after,
                        result_summary=(
                            f"Executed {applied_step_count} bounded browser step(s) with "
                            f"Playwright Firefox."
                        ),
                        applied_step_count=applied_step_count,
                    )
                finally:
                    context.close()
        except PlaywrightError as error:
            msg = f"Playwright Firefox execution failed: {error}"
            raise BrowserAutomationError(msg) from error


def _resolve_profile_dir(profile_root: Path, profile_id: str) -> Path:
    sanitized = "".join(
        character
        for character in profile_id.lower()
        if character.isalnum() or character in {"-", "_"}
    )
    if not sanitized:
        msg = "profile_id must contain at least one safe character."
        raise BrowserAutomationError(msg)
    root = profile_root.resolve()
    profile_dir = (root / sanitized).resolve()
    if not profile_dir.is_relative_to(root):
        msg = "Resolved browser profile path escaped the configured profile root."
        raise BrowserAutomationError(msg)
    return profile_dir


def _assert_allowed_host(url: str, allowed_hosts: list[str]) -> None:
    hostname = urlparse(url).hostname
    normalized_host = "" if hostname is None else hostname.lower()
    if normalized_host not in allowed_hosts:
        msg = f"Browser navigation host is not allowlisted: {normalized_host or url}"
        raise BrowserAutomationError(msg)


def _capture_page(page: _PageLike, config: BrowserGovernorConfig) -> BrowserPageSnapshot:
    current_url = str(page.url)
    body_text = _read_page_text(page)
    return BrowserPageSnapshot(
        url=current_url,
        page_text=body_text,
        html=page.content(),
        page_title=page.title(),
        screenshot_png=page.screenshot(
            type="png",
            full_page=True,
            timeout=config.default_timeout_ms,
        ),
    )


def _read_page_text(page: _PageLike) -> str:
    text_content = page.text_content("body")
    if text_content is None:
        return ""
    return text_content.strip()


def _apply_step(
    page: _PageLike,
    step: BrowserExecutionStep,
) -> None:
    if step.kind == "fill":
        page.locator(_require_string(step.selector)).fill(
            _require_string(step.text),
            timeout=step.timeout_ms,
        )
        return
    if step.kind == "click":
        page.locator(_require_string(step.selector)).click(timeout=step.timeout_ms)
        return
    _wait_for_text(
        page,
        expected=_require_string(step.text),
        selector=step.selector,
        timeout_ms=step.timeout_ms,
    )


def _wait_for_text(
    page: _PageLike,
    *,
    expected: str,
    selector: str | None,
    timeout_ms: int,
) -> None:
    deadline = time.monotonic() + (timeout_ms / 1_000)
    while time.monotonic() < deadline:
        observed = (
            page.text_content("body")
            if selector is None
            else page.locator(selector).text_content(timeout=timeout_ms)
        )
        if observed is not None and expected in observed:
            return
        time.sleep(0.05)
    msg = f"Timed out waiting for text: {expected}"
    raise BrowserAutomationError(msg)


def _require_string(value: str | None) -> str:
    if value is None:
        msg = "Browser step field was unexpectedly missing."
        raise BrowserAutomationError(msg)
    return value
