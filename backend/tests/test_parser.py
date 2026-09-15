from backend.app.utils.parser import LLMParser

def test_extract_code_block_with_chatty_llm():
    chatty_response = """
    Sure! Here is the Python function you requested:
    ```python
    def add(a, b):
        return a + b
    ```
    Hope this helps with your project! Let me know if you need anything else.
    """
    
    extracted = LLMParser.extract_code_block(chatty_response, "python")
    assert "def add(a, b):" in extracted
    assert "return a + b" in extracted
    assert "Sure!" not in extracted
    assert "Hope this helps!" not in extracted

def test_extract_patch_safely():
    response = """
    I have updated the file for you:
    ```diff
    --- a/main.py
    +++ b/main.py
    @@ -1,3 +1,3 @@
    -print("old")
    +print("new")
    ```
    """
    
    patch = LLMParser.extract_patch(response)
    assert "--- a/main.py" in patch
    assert "+print(\"new\")" in patch
    assert "I have updated" not in patch

