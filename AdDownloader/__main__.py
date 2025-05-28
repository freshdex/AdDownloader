"""AdDownloader entry point script.

This script allows the package to be run as a module using `python -m AdDownloader`.
It imports the main Typer application object (`cli`) from the package's
__init__.py (which in turn gets it from cli.py) and executes it.
"""
# AdDownloader/__main__.py

# Import the Typer 'app' object (aliased as 'cli') and '__app_name__'
# from the AdDownloader package (via AdDownloader/__init__.py)
from AdDownloader import cli, __app_name__

def main():
    """
    Main function to execute the Typer CLI application.
    """
    # When 'cli' is the Typer application instance itself,
    # you invoke it directly. Typer handles parsing arguments
    # and calling the appropriate command (e.g., 'run-analysis').
    # The prog_name is usually handled by Typer itself based on how it's called
    # or can be set during Typer app initialization if needed, but often not here.
    cli()

if __name__ == "__main__":
    # This block executes when the script is run directly,
    # e.g., `python AdDownloader/__main__.py` or `python -m AdDownloader`
    main()