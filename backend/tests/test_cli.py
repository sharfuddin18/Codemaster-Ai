import io

import pytest

from cli_tools.ai import resolve_prompt


def test_multiline_prompt_is_preserved():
    prompt = 'Write Python code\n- read a CSV\n- validate it\nprint("hello")'
    assert resolve_prompt([prompt]) == prompt


def test_markdown_and_cplusplus_are_preserved():
    prompt = '# C++ task\n\n```cpp\n#include <iostream>\nint main() {\n    std::cout << "Hello";\n}\n```\n'
    assert resolve_prompt([prompt]) == prompt


def test_multiple_arguments_are_joined():
    assert resolve_prompt(["write", "Python", "code"]) == "write Python code"


def test_prompt_option_accepts_one_argument():
    prompt = "line one\nline two"
    assert resolve_prompt(["--prompt", prompt]) == prompt


def test_stdin_preserves_multiline_input():
    prompt = "line one\n- line two\nline three\n"
    assert resolve_prompt(["--stdin"], stdin=io.StringIO(prompt)) == prompt


def test_no_arguments_reads_piped_stdin():
    prompt = "# pasted source\nprint('hello')\n"
    assert resolve_prompt([], stdin=io.StringIO(prompt)) == prompt


def test_stdin_rejects_extra_arguments():
    with pytest.raises(ValueError, match="cannot be combined"):
        resolve_prompt(["--stdin", "extra"], stdin=io.StringIO("prompt"))


def test_unknown_option_is_rejected():
    with pytest.raises(ValueError, match="Unknown option"):
        resolve_prompt(["--unknown"])


def test_empty_argument_is_allowed_for_resolution():
    assert resolve_prompt([""]) == ""
