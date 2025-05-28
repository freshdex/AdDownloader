"""This module provides the AdDownloader Command-line Interface."""
# AdDownloader/cli.py

import typer
import inquirer3 # Main import
from inquirer3.errors import ValidationError as InquirerValidationError # Import for PageIDValidator
from inquirer3.themes import load_theme_from_dict
from rich import print as rprint
import time
import pandas as pd
import os
from loguru import logger

from AdDownloader.adlib_api import AdLibAPI
from AdDownloader.media_download import start_media_download
# PageIDValidator is defined locally in this file, so it's removed from helpers import
from AdDownloader.helpers import NumberValidator, DateValidator, CountryValidator, update_access_token, configure_logging, close_logger

# Theme for inquirer3 prompts
default_style = load_theme_from_dict(
    {
        "Question": {"mark_color": "bold_firebrick3", "brackets_color": "mediumpurple", "default_color": "bold_blue"},
        "List": {"selection_color": "bold_dodgerblue3_on_goldenrod1", "selection_cursor": "➤", "unselected_color": "dodgerblue2"}
    }
)

# Validator for comma-separated Page IDs - defined locally in cli.py
class PageIDValidator:
    @staticmethod
    def validate_page_ids(answers, current):
        rprint(f"\n[PageIDValidator] Received for Page IDs: '{current}' (Type: {type(current)})")
        current_stripped = current.strip()
        if not current_stripped:
            rprint("[PageIDValidator] Validation Fail: Page IDs cannot be empty.")
            # For inquirer3, an empty message string for ValidationError is fine if 'reason' is used by theme/handler
            raise InquirerValidationError("", reason="VALIDATOR FAIL: Page IDs cannot be empty if chosen as search method.")
        
        # Split by comma and strip whitespace from each potential ID
        ids = [pid.strip() for pid in current_stripped.split(',')]
        rprint(f"[PageIDValidator] IDs after split and strip: {ids}")

        # Filter out any empty strings that might result from multiple commas (e.g., "123,,456") or trailing commas
        actual_ids_to_check = [pid for pid in ids if pid] # Keeps only non-empty strings
        
        if not actual_ids_to_check: # If list is empty after filtering (e.g., input was ",," or just " ")
            rprint("[PageIDValidator] Validation Fail: No actual Page IDs provided after stripping and splitting.")
            raise InquirerValidationError("", reason="VALIDATOR FAIL: Please provide at least one valid Page ID.")

        for pid_to_check in actual_ids_to_check:
            if not pid_to_check.isdigit():
                rprint(f"[PageIDValidator] Validation Fail: ID '{pid_to_check}' is not composed of only digits.")
                raise InquirerValidationError("", reason=f"VALIDATOR FAIL: Page ID '{pid_to_check}' is not valid. All Page IDs must be numbers (e.g., '12345' or '123,456').")
        
        rprint("[PageIDValidator] Page IDs validation passed.")
        return True

def request_params_task_AC():
    """Prompt user for additional parameters for API request in tasks A and C."""
    add_questions = [
        inquirer3.List("ad_type", message="What type of ads do you want to search?", choices=['All', 'Political/Elections'], default='All'),
        inquirer3.Text("ad_reached_countries", message="What reached countries? (Codes, comma-separated, e.g., US,GB. Default 'NL')", validate=CountryValidator.validate_country, default="NL"),
        inquirer3.Text("ad_delivery_date_min", message="Min ad delivery date? (YYYY-MM-DD, default '2023-01-01')", validate=DateValidator.validate_date, default='2023-01-01'),
        inquirer3.Text("ad_delivery_date_max", message="Max ad delivery date? (YYYY-MM-DD, default today)", validate=DateValidator.validate_date, default=time.strftime('%Y-%m-%d')),
        inquirer3.List("search_by", message="Search by specific Page IDs or by search terms?", choices=['Enter Page IDs directly', 'Search Terms'], default='Search Terms'),
        inquirer3.Text("search_page_ids_direct", message="Page IDs, comma-separated:", ignore=lambda answers: answers.get('search_by') != 'Enter Page IDs directly', validate=PageIDValidator.validate_page_ids),
        inquirer3.Text("search_terms", message="Search terms, comma-separated:", ignore=lambda answers: answers.get('search_by') != 'Search Terms', validate=lambda _, current: True if current.strip() else "Search terms cannot be empty if this search method is chosen.")
    ]
    rprint("[yellow]Configuring search parameters for Task A/C...[yellow]")
    answers = inquirer3.prompt(add_questions, theme=default_style)
    if not answers: # Handles Ctrl+C during prompt
        rprint("[red]Parameter configuration cancelled.[red]")
        return None
    return answers

def run_task_A(project_name: str, answers_main_task: dict):
    """Runs Task A: Download ads data."""
    if not project_name or not project_name.strip():
        rprint("[red]Project name cannot be empty for Task A.[red]")
        logger.error("Task A aborted: Project name was empty.")
        return
    logger.info(f"Starting Task A for project: {project_name}")

    access_token = answers_main_task.get('access_token')
    if not access_token: # Should be caught by AdLibAPI init, but good to check early
        rprint("[red]Access token is missing. Cannot proceed with Task A.[red]")
        logger.error("Task A aborted: Access token missing.")
        return
        
    ads = AdLibAPI(access_token=access_token, project_name=project_name)
    
    param_answers = request_params_task_AC()
    if not param_answers:
        logger.warning("Task A aborted: Detailed parameter input cancelled by user.")
        return

    search_by = param_answers.get('search_by')
    ad_type = param_answers.get('ad_type', 'All') # Default if somehow missing
    page_ids_to_pass, search_terms_to_pass = None, None

    if search_by == 'Enter Page IDs directly':
        raw_page_ids_str = param_answers.get('search_page_ids_direct', "")
        # Validator should ensure this is fine, but double check parsing
        page_ids_to_pass = [pid.strip() for pid in raw_page_ids_str.split(',') if pid.strip().isdigit()]
        if not page_ids_to_pass:
            rprint("[red]No valid numerical Page IDs provided after parsing for 'Enter Page IDs directly' search. Aborting Task A.[red]")
            logger.error("Task A failed: No valid numerical Page IDs after parsing direct input.")
            return
        logger.info(f"Task A using directly entered Page IDs: {page_ids_to_pass}")
    elif search_by == 'Search Terms':
        search_terms_to_pass = param_answers.get('search_terms')
        if not search_terms_to_pass or not search_terms_to_pass.strip():
            rprint("[red]No search terms provided for 'Search Terms' method. Aborting Task A.[red]")
            logger.error("Task A failed: No search terms provided for search terms method.")
            return
        logger.info(f"Task A using search terms: {search_terms_to_pass}")
            
    ads.add_parameters(
        ad_reached_countries=param_answers.get('ad_reached_countries', "NL"),
        ad_delivery_date_min=param_answers.get('ad_delivery_date_min', '2023-01-01'),
        ad_delivery_date_max=param_answers.get('ad_delivery_date_max', time.strftime('%Y-%m-%d')),
        search_page_ids=page_ids_to_pass,
        search_terms=search_terms_to_pass,
        ad_type="ALL" if ad_type == 'All' else "POLITICAL_AND_ISSUE_ADS"
    )
    
    rprint(f"[yellow]API Parameters for Task A:[yellow]\n[green bold]{ads.get_parameters()}.[green bold]")
    logger.info(f"API Parameters for Task A: {ads.get_parameters()}")

    rprint("[yellow]Ad data download will begin now for Task A.[yellow]")
    start_time = time.time()
    ads.start_download() # Consider prompting for output_format or getting from config
    end_time = time.time()
    elapsed_time = end_time - start_time
    minutes, seconds = divmod(int(elapsed_time), 60)
    rprint(f"Task A data download finished in {minutes} minutes and {seconds} seconds.")
    logger.info(f"Task A download finished in {minutes}m {seconds}s.")

def run_task_B(project_name: str, answers_main_task: dict):
    """Runs Task B: Download media content."""
    if not project_name or not project_name.strip():
        rprint("[red]Project name cannot be empty for Task B.[red]")
        logger.error("Task B aborted: Project name was empty.")
        return
    logger.info(f"Starting Task B for project: {project_name}")

    try:
        output_data_path = f'output/{project_name}/ads_data/{project_name}_original_data'
        file_path_xlsx = f'{output_data_path}.xlsx'
        file_path_csv = f'{output_data_path}.csv'
        
        data_df = None
        used_file_path = ""

        if os.path.exists(file_path_xlsx):
            used_file_path = file_path_xlsx
            rprint(f"[yellow]Reading data from Excel for Task B: {used_file_path}[yellow]")
            data_df = pd.read_excel(used_file_path)
        elif os.path.exists(file_path_csv):
            used_file_path = file_path_csv
            rprint(f"[yellow]Reading data from CSV for Task B: {used_file_path}[yellow]")
            data_df = pd.read_csv(used_file_path)
        else:
            rprint(f"[red]Error: Ads data file not found for project '{project_name}'.[red]")
            rprint(f"[red]Expected at '{file_path_xlsx}' or '{file_path_csv}'. Please run Task A or C first.[red]")
            logger.error(f"Ads data file not found for Task B: {file_path_xlsx} or {file_path_csv}")
            return
        
        if data_df.empty:
            rprint(f"[orange3]The ads data file ('{used_file_path}') is empty. No media to download for Task B.[orange3]")
            logger.warning(f"Ads data file for Task B ('{used_file_path}') is empty.")
            return
        total_ads = len(data_df)

        access_token_for_update = answers_main_task.get('access_token')
        if access_token_for_update:
             data_df = update_access_token(data_df, access_token_for_update)
        else:
            rprint("[orange3]Access token not found/empty in main task answers. Snapshot URLs may not be updated for media download.[orange3]")
            logger.warning("Access token not available in main task answers for Task B media download URL update.")
       
        rprint("[yellow]Starting media content download process for Task B...[yellow]")
        questions_down = [
            inquirer3.List("nr_ads_option", message=f"Found {total_ads} ads in '{used_file_path}'. Download media for how many?", choices=['A - 50', 'B - 100', 'C - 200', 'D - Custom number', f'E - All ({total_ads})'], default='A - 50'),
            inquirer3.Text("custom_ads_nr", message="Custom number of ads for media download:", ignore=lambda ans: ans.get('nr_ads_option') != 'D - Custom number', validate=NumberValidator.validate_number, default='10'),
        ]
        answers_down = inquirer3.prompt(questions_down, theme=default_style)
        if not answers_down:
            rprint("[red]Media download configuration cancelled.[red]")
            logger.warning("Task B aborted: Media download configuration cancelled by user.")
            return
            
        nr_ads_str = answers_down.get("nr_ads_option")
        nr_ads_to_download = 0
        if nr_ads_str == 'A - 50': nr_ads_to_download = 50
        elif nr_ads_str == 'B - 100': nr_ads_to_download = 100
        elif nr_ads_str == 'C - 200': nr_ads_to_download = 200
        elif nr_ads_str == f'E - All ({total_ads})': nr_ads_to_download = total_ads
        elif nr_ads_str == 'D - Custom number':
            try: nr_ads_to_download = int(answers_down.get("custom_ads_nr", 0))
            except ValueError: rprint("[red]Invalid custom number for media download. Defaulting to 0.[red]")
        
        if nr_ads_to_download <= 0:
            rprint("[orange3]Number of ads for media download must be greater than 0.[orange3]")
            logger.warning(f"Task B: Invalid number of ads selected for media download: {nr_ads_to_download}")
            return
        nr_ads_to_download = min(nr_ads_to_download, total_ads) 
        
        logger.info(f"Task B: Attempting to download media for {nr_ads_to_download} ads from project '{project_name}'.")
        start_media_download(project_name, nr_ads=nr_ads_to_download, data=data_df) # Pass dataframe
        logger.info(f"Task B: Media download process initiated for {nr_ads_to_download} ads.")
    except Exception as e:
        rprint(f"[bold red]An unexpected error occurred in Task B: {e}[bold red]")
        import traceback
        logger.error(f"Task B unexpected error: {e}\n{traceback.format_exc()}")

def intro_messages():
    """Display introductory messages and gather user input for the selected task."""
    questions = [
        inquirer3.List("task", message="Welcome to the AdDownloader! Select the task you want to perform:", choices=['A - Ads data only', 'B - Media content only', 'C - Both data and media', 'D - Open dashboard'], default='A - Ads data only'),
        inquirer3.Password("access_token", message='Meta Ad Library access token (Required for Tasks A, B, C - Press Enter if only doing Task D):', 
                           validate=lambda ans, token_str: (True if ans.get('task') == 'D - Open dashboard' else (True if token_str.strip() and len(token_str.strip()) > 10 else "Access token is required for this task and appears to be missing or too short.")),
                           ignore=lambda answers: answers.get('task') == 'D - Open dashboard' # Only ignore if task D is chosen
                           ),
        inquirer3.Confirm("start", message="Are you sure you want to proceed?", default=True),
    ]
    answers_main_task = inquirer3.prompt(questions, theme=default_style)

    if not answers_main_task or not answers_main_task.get('start'):
        rprint("[orange3]Operation cancelled by user at main prompt.[orange3]")
        logger.info("User cancelled operation from main prompt.")
        return None 

    task_choice = answers_main_task.get('task')
    rprint(f"[green bold]Task selected: {task_choice}.[green bold]")
    logger.info(f"User selected task: {task_choice}")

    project_name = ""
    # Ask for project name only if a task requiring it is selected
    if task_choice in ['A - Ads data only', 'B - Media content only', 'C - Both data and media']:
        name_questions = [inquirer3.Text("project_name", message="Please enter a name for your project (e.g., 'my_ad_research'):", 
                                           validate=lambda _, x: True if x.strip() else "Project name cannot be empty.")]
        name_answer = inquirer3.prompt(name_questions, theme=default_style)
        if not name_answer or not name_answer.get('project_name'):
            rprint("[red]Project name not provided. Aborting.[red]")
            logger.error("Project name not provided by user.")
            return None 
        project_name = name_answer.get('project_name').strip().replace(" ", "_") # Sanitize project name
        logger.info(f"Project name set to: {project_name}")
        # Configure logging as soon as project name is available and valid for these tasks
        configure_logging(project_name) 
    
    answers_main_task['project_name'] = project_name 
    return answers_main_task


app = typer.Typer(
    name="AdDownloader",
    help="A CLI tool for downloading ads and media from the Meta Ad Library.",
    add_completion=True # Enables Typer's shell completion features
)

@app.command() # This becomes the default command since it's the only one on 'app'
def run_analysis():
    """
    Main entry point to start the AdDownloader interactive tasks.
    This function will be executed when `AdDownloader` is run.
    """
    rprint("[bold blue]AdDownloader Initialized.[/bold blue]")
    # Initial general logging (before project name is known) can be configured here if needed
    # For example, to ensure logs go somewhere even if user cancels before project name:
    # if not logger.handlers: # Check if any handlers are configured by default by loguru
    #    logger.add(sys.stderr, level="INFO") 

    try:
        while True:
            main_task_details = intro_messages()
            if not main_task_details: 
                rprint("[orange3]No task details provided or operation cancelled. Exiting current loop.[orange3]")
                break 

            task_choice = main_task_details.get('task')
            project_name = main_task_details.get('project_name') # Already sanitized and logger configured if needed

            if task_choice == 'A - Ads data only':
                run_task_A(project_name, main_task_details)
            elif task_choice == 'B - Media content only':
                run_task_B(project_name, main_task_details)
            elif task_choice == 'C - Both data and media':
                run_task_A(project_name, main_task_details)
                # Check if Task A produced data before proceeding to Task B
                ads_data_file_xlsx = f'output/{project_name}/ads_data/{project_name}_original_data.xlsx'
                ads_data_file_csv = f'output/{project_name}/ads_data/{project_name}_original_data.csv'
                if project_name and (os.path.exists(ads_data_file_xlsx) or os.path.exists(ads_data_file_csv)):
                    run_task_B(project_name, main_task_details)
                elif project_name: # project_name was given, but files don't exist
                    rprint(f"[red]Task A (data download) did not produce an output file for project '{project_name}'. Skipping media download (Task B).[red]")
                    logger.error(f"Task A failed for project '{project_name}', skipping Task B for combined Task C.")
                # If project_name was empty, run_task_A would have already handled it
            elif task_choice == 'D - Open dashboard':
                rprint("[yellow]The dashboard feature might require additional dependencies (like 'dash').[yellow]")
                rprint("[yellow]Attempting to start dashboard... Press Ctrl+C in the terminal to close it.[yellow]")
                try:
                    from AdDownloader.start_app import start_gui 
                    start_gui(project_name_for_dashboard=project_name if project_name else None) # Pass project_name if available
                    logger.info("Dashboard started.")
                except ImportError:
                    rprint("[red]Dashboard components (AdDownloader.start_app) not found or 'dash' dependencies might be missing.[red]")
                    logger.error("ImportError for AdDownloader.start_app (dashboard).")
                except Exception as e:
                    rprint(f"[red]Could not start dashboard: {e}[red]")
                    logger.error(f"Failed to start dashboard: {e}")
            
            rprint("\n[yellow]----------------------------------------------------[yellow]")
            rprint("[green]Current task set finished.[green]")
            
            confirm_questions = [inquirer3.Confirm("rerun", message="Do you want to perform a new analysis?", default=False)]
            rerun_answer = inquirer3.prompt(confirm_questions, theme=default_style)
            if not rerun_answer or not rerun_answer.get('rerun'):
                rprint("[bold blue]Exiting AdDownloader. Thank you for using the tool![/bold blue]")
                logger.info("User chose to end analysis session.")
                break
            logger.info("User chose to perform a new analysis.")
            rprint("\n") # Add a newline for better separation before next run
            
    except KeyboardInterrupt:
        rprint("\n[orange3]Operation cancelled by user (Ctrl+C).[orange3]")
        logger.warning("Operation cancelled by KeyboardInterrupt in main loop.")
    except Exception as e:
        rprint(f"[bold red]An unexpected critical error occurred in the main application loop: {e}[bold red]")
        import traceback
        logger.critical(f"Main application loop critical error: {e}\n{traceback.format_exc()}")
    finally:
        close_logger() # Call to allow loguru to flush handlers, etc.

# This is for making the cli.py file runnable directly with `python AdDownloader/cli.py` for development/testing
if __name__ == "__main__":
    rprint("[yellow]Running AdDownloader CLI directly (cli.py __main__)...[yellow]")
    # Basic logger for direct script run if configure_logging isn't hit early by tasks
    logger.remove() # Remove default handlers
    logger.add(sys.stderr, level="INFO") # Add a simple stderr logger for direct script test
    import sys
    
    app()