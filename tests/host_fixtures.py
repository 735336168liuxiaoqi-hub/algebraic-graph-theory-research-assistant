"""Verify OS fixture postconditions before exercising a protection boundary.

Hosts can reject or silently broker a creation request. A missing fixture is
reported as unavailable, never as a passed protection test or an ordinary dir.
"""
import os
from pathlib import Path
import stat
import subprocess


def real_link_or_skip(test,link,target,*,directory=False):
    link=Path(link);target=Path(target)
    if os.path.lexists(link):raise AssertionError('Link fixture path must be fresh')
    problem=None
    try:link.symlink_to(target,target_is_directory=directory)
    except OSError as error:problem=type(error).__name__+': '+str(error)
    def real_link():
        try:info=link.lstat()
        except FileNotFoundError:return False
        return stat.S_ISLNK(info.st_mode) or bool(getattr(info,'st_file_attributes',0)&0x400)
    if real_link():return
    if os.name=='nt' and directory and not os.path.lexists(link):
        quote=lambda p:"'"+str(p).replace("'","''")+"'"
        command="$ErrorActionPreference='Stop'; New-Item -ItemType Junction -Path "+quote(link)+' -Target '+quote(target)+' -ErrorAction Stop | Out-Null'
        created=subprocess.run(['powershell','-NoProfile','-NonInteractive','-Command',command],
            capture_output=True,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        problem='junction exit='+str(created.returncode)
        if real_link():return
    test.skipTest('Host link fixture unavailable: no real symlink/reparse point was created; boundary behavior NOT TESTED. '+(problem or 'Creation returned without creating a link.'))
