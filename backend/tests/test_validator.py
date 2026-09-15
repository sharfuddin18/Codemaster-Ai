import os
from backend.app.utils.validator import PathValidator

def test_extract_target_paths():
    patch = """
    --- a/backend/app/utils/parser.py
    +++ b/backend/app/utils/parser.py
    @@ -1,2 +1,3 @@
     # test
    +new_line = True
    """
    paths = PathValidator.extract_target_paths_from_patch(patch)
    assert "backend/app/utils/parser.py" in paths

def test_validate_patch_provenance_existing_file(tmp_path):
    test_file = tmp_path / "app.py"
    test_file.write_text("print('hello')")
    
    patch = """
    --- a/app.py
    +++ b/app.py
    @@ -1,1 +1,1 @@
    -print('hello')
    +print('world')
    """
    
    assert PathValidator.validate_patch_provenance(patch, root_dir=str(tmp_path)) is True

def test_validate_patch_provenance_hallucinated_file(tmp_path):
    patch = """
    --- a/hallucinated_file.py
    +++ b/hallucinated_file.py
    @@ -1,1 +1,1 @@
    -old
    +new
    """
    assert PathValidator.validate_patch_provenance(patch, root_dir=str(tmp_path)) is False
