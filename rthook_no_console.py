"""PyInstaller runtime hook — suppress ALL CLI console windows."""
import sys
if sys.platform == "win32":
    import subprocess
    _CREATE_NO_WINDOW = 0x08000000
    _SW_HIDE = 0

    # Popen patch
    _popen = subprocess.Popen.__init__
    def _popen_nw(self, *args, **kwargs):
        kwargs.setdefault("creationflags", _CREATE_NO_WINDOW)
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = _SW_HIDE
        kwargs.setdefault("startupinfo", si)
        _popen(self, *args, **kwargs)
    subprocess.Popen.__init__ = _popen_nw

    # run patch
    _run = subprocess.run
    def _run_nw(*args, **kwargs):
        kwargs.setdefault("creationflags", _CREATE_NO_WINDOW)
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = _SW_HIDE
        kwargs.setdefault("startupinfo", si)
        return _run(*args, **kwargs)
    subprocess.run = _run_nw

    # call, check_call, check_output
    for _n in ("call", "check_call", "check_output"):
        _o = getattr(subprocess, _n)
        setattr(subprocess, _n, lambda *a, _o=_o, **kw: _o(*a, **dict(kw, creationflags=kw.get("creationflags", _CREATE_NO_WINDOW))))
