"""Optional native Qt desktop application; no browser or model required."""


def gui_main():
    from graph_research.runtime.integrity import assert_integrity
    assert_integrity()
    from .app import desktop_command
    return desktop_command([])
