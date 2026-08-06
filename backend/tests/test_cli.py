import io
from pathlib import Path

import requests

from cli_tools.ai import main, resolve_prompt


def test_multiline_prompt_is_preserved():
    prompt = 'Write Python code\n- read a CSV\n- validate it\nprint("hello")'
    assert resolve_prompt([prompt]) == prompt


def test_markdown_and_cplusplus_are_preserved():
    prompt = '# C++ task\n\n```cpp\n#include <iostream>\nint main() {\n    std::cout << "Hello";\n}\n```\n'
    assert resolve_prompt([prompt]) == prompt


def test_python_source_with_quotes_and_indentation_is_preserved():
    prompt = 'Fix this Python:\n\n    message = "hello"\n    if message:\n        print("quoted text")\n'
    assert resolve_prompt([prompt]) == prompt


def test_multiple_arguments_are_joined():
    assert resolve_prompt(["write", "Python", "code"]) == "write Python code"


def test_prompt_option_accepts_one_argument():
    prompt = "line one\nline two"
    assert resolve_prompt(["--prompt", prompt]) == prompt


def test_file_input_preserves_multiline_prompt(tmp_path: Path):
    prompt = "# pasted source\n\nint main() {\n    return 0;\n}\n"
    prompt_file = tmp_path / "prompt.txt"
    prompt_file.write_text(prompt, encoding="utf-8", newline="")
    assert resolve_prompt(["--file", str(prompt_file)]) == prompt


def test_stdin_preserves_multiline_input():
    prompt = "line one\n- line two\nline three\n"
    assert resolve_prompt(["--stdin"], stdin=io.StringIO(prompt)) == prompt


def test_no_arguments_reads_piped_stdin():
    prompt = "# pasted source\nprint('hello')\n"
    assert resolve_prompt([], stdin=io.StringIO(prompt)) == prompt


def test_stdin_rejects_extra_arguments():
    try:
        resolve_prompt(["--stdin", "extra"], stdin=io.StringIO("prompt"))
    except ValueError as exc:
        assert "cannot be combined" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_unknown_option_is_rejected():
    try:
        resolve_prompt(["--unknown"])
    except ValueError as exc:
        assert "Unknown option" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_main_sends_prompt_unchanged_to_generate_code(monkeypatch):
    prompt = 'Write C++ code\n\n#include <iostream>\nint main() {\n    std::cout << "Hello";\n}\n'
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"code": "int main() {}"}

    def fake_post(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return FakeResponse()

    monkeypatch.setattr(requests, "post", fake_post)

    assert main([prompt]) == 0
    assert captured["url"] == "http://localhost:8000/generate-code"
    assert captured["kwargs"]["json"] == {"prompt": prompt}
    assert captured["kwargs"]["headers"] == {"Content-Type": "application/json"}
    assert captured["kwargs"]["timeout"] == 120


def test_main_uses_configured_api_url(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"code": "print('ok')"}

    def fake_post(url, **kwargs):
        captured["url"] = url
        return FakeResponse()

    monkeypatch.setenv("CODEMASTER_API_URL", "http://127.0.0.1:9000/generate-code")
    monkeypatch.setattr(requests, "post", fake_post)

    assert main(["hello"]) == 0
    assert captured["url"] == "http://127.0.0.1:9000/generate-code"


def test_main_rejects_empty_prompt_without_http_request(monkeypatch):
    called = False

    def fake_post(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("HTTP request should not be made")

    monkeypatch.setattr(requests, "post", fake_post)

    assert main([""]) == 2
    assert called is False
