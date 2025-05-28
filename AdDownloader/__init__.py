"""Top-level package for AdDownloader."""
# AdDownloader/__init__.py

__app_name__ = "AdDownloader"
__version__ = "0.2.11" # You might want to update this if you're making changes for Python 3.13

# Import the Typer application object from the cli.py module
# and make it available as 'cli' when someone imports from 'AdDownloader' package.
# e.g., from AdDownloader import cli
from .cli import app as cli

# You can also choose to expose specific functions or classes directly at the package level if desired,
# for example:
# from .adlib_api import AdLibAPI
# from .media_download import start_media_download
# This would allow imports like `from AdDownloader import AdLibAPI`
# For now, just exposing 'cli' and the dunder variables is the main change needed.