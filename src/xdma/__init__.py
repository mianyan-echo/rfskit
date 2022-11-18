from rfskit.tools.printLog import printWarning

simulation_ctl = False
try:
    if simulation_ctl:
        from .xdma_sim import Xdma
    else:
        from .xdma import Xdma
except OSError as e:
    printWarning(e)
    from .xdma_sim import Xdma
