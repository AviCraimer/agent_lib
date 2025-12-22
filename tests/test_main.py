import importlib

import pytest


def test_main_prints_running(capsys: pytest.CaptureFixture[str]) -> None:
    """
    Import the CLI module and call main().
    We only assert that 'running!' appears to keep this robust
    against small changes to your banner text.
    """
    from agent_lib import main as cli

    importlib.reload(cli)

    cli.main()
    out = capsys.readouterr().out
    assert "running!" in out.lower()
