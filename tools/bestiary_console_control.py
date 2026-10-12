"""Inspect or gracefully signal a dedicated Windows server console; never force-kill."""
import argparse,ctypes,json,os,time
from ctypes import wintypes

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('pid',type=int);ap.add_argument('--stop',action='store_true');args=ap.parse_args()
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.AttachConsole.argtypes=[wintypes.DWORD];kernel.AttachConsole.restype=wintypes.BOOL
    kernel.GetConsoleProcessList.argtypes=[ctypes.POINTER(wintypes.DWORD),wintypes.DWORD];kernel.GetConsoleProcessList.restype=wintypes.DWORD
    kernel.SetConsoleCtrlHandler.argtypes=[ctypes.c_void_p,wintypes.BOOL];kernel.SetConsoleCtrlHandler.restype=wintypes.BOOL
    kernel.GenerateConsoleCtrlEvent.argtypes=[wintypes.DWORD,wintypes.DWORD];kernel.GenerateConsoleCtrlEvent.restype=wintypes.BOOL
    kernel.FreeConsole()
    if not kernel.AttachConsole(args.pid):raise ctypes.WinError(ctypes.get_last_error())
    try:
        ids=(wintypes.DWORD*256)();count=kernel.GetConsoleProcessList(ids,256)
        if not 0<count<=256:raise RuntimeError('Cannot inventory the target console')
        peers=[int(ids[i]) for i in range(count) if ids[i]!=os.getpid()]
        if peers!=[args.pid]:raise RuntimeError('Refusing to signal a console shared with other processes: '+str(peers))
        if args.stop:
            if not kernel.SetConsoleCtrlHandler(None,True):raise ctypes.WinError(ctypes.get_last_error())
            if not kernel.GenerateConsoleCtrlEvent(0,0):raise ctypes.WinError(ctypes.get_last_error())
            time.sleep(0.5)
        print(json.dumps({'pid':args.pid,'dedicated_console':True,'graceful_signal_sent':args.stop}))
    finally:kernel.FreeConsole()

if __name__=='__main__':main()
