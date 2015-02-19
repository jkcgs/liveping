##########################
# admin.py - Run as administrator (this is required by ping)
# On Windows requires Windows XP SP2 or higher
# Cutted version from http://stackoverflow.com/a/19719292
##########################

import ctypes, os, sys

class Admin:
    def isUserAdmin(self):
        if os.name == 'nt':
            try:
                import ctypes
                return ctypes.windll.shell32.IsUserAnAdmin()
            except:
                return False
        elif os.name == 'posix':
            return os.getuid() == 0
        else:
            return True # OS not recognized, assuming true

    def runAsAdmin(self):
        if os.name == 'posix':
            # sudo or gksu depending if running on console or not
            run = "sudo" if sys.stdin.isatty() else "gksudo"
            os.execvp(run, [run] + sys.argv)
        elif os.name != 'nt':
            raise RuntimeError, "Could not run as administrator. Do it manually, please."

        import win32api, win32con, win32event, win32process
        from win32com.shell.shell import ShellExecuteEx
        from win32com.shell import shellcon

        params = " ".join(['"%s"' % (x,) for x in sys.argv])
        procInfo = ShellExecuteEx(fMask=shellcon.SEE_MASK_NOCLOSEPROCESS,
                                  lpVerb='runas', lpFile=sys.prefix+'\pythonw.exe', lpParameters=params)

        procHandle = procInfo['hProcess']    
        obj = win32event.WaitForSingleObject(procHandle, win32event.INFINITE)
        rc = win32process.GetExitCodeProcess(procHandle)