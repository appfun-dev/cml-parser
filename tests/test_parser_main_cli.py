import sys
from pathlib import Path
from io import StringIO
import contextlib
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from cml_parser.parser import main

def test_cli_help():
    with contextlib.redirect_stdout(StringIO()) as stdout:
        try:
            main(["--help"])
        except SystemExit as e:
            assert e.code == 0
    assert "usage: cml-parse" in stdout.getvalue()

def test_cli_no_args():
    # When no args, it prints usage to stderr and returns 1
    with contextlib.redirect_stderr(StringIO()) as stderr:
        ret = main([])
        assert ret == 1
    assert "usage: cml-parse" in stderr.getvalue()

def test_cli_parse_file(tmp_path):
    f = tmp_path / "test.cml"
    f.write_text('ContextMap M {}')
    
    with contextlib.redirect_stdout(StringIO()) as stdout:
        ret = main([str(f)])
        assert ret == 0
    assert "Successfully parsed" in stdout.getvalue()

def test_cli_json(tmp_path):
    f = tmp_path / "test.cml"
    f.write_text('ContextMap M {}')
    
    with contextlib.redirect_stdout(StringIO()) as stdout:
        ret = main([str(f), "--json"])
        assert ret == 0
    output = stdout.getvalue()
    assert '"ok": true' in output

def test_cli_summary(tmp_path):
    f = tmp_path / "test.cml"
    f.write_text('ContextMap M {}')
    
    with contextlib.redirect_stdout(StringIO()) as stdout:
        ret = main([str(f), "--summary"])
        assert ret == 0
    output = stdout.getvalue()
    assert "Context Maps: 1" in output

def test_cli_error(tmp_path):
    f = tmp_path / "bad.cml"
    f.write_text('ContextMap "M"') # Invalid quotes, syntax error
    
    with contextlib.redirect_stderr(StringIO()) as stderr:
        ret = main([str(f)])
        assert ret == 1
    assert "Error parsing" in stderr.getvalue()
