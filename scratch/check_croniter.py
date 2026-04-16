try:
    import croniter
    print("croniter version:", croniter.__version__ if hasattr(croniter, "__version__") else "installed")
except ImportError:
    print("croniter not found")
