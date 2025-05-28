"""
This module provides helper classes and functions for the AdDownloader tool,
including input validators, utility functions, and logging configuration.
"""
# AdDownloader/helpers.py

import os
import re
import pandas as pd
from datetime import datetime
import inquirer3 # Main import for inquirer3
from inquirer3.errors import ValidationError # Correct import for the exception
from rich import print as rprint # For rich console output
from loguru import logger # For logging

# --- Logging Configuration ---
LOGURU_HANDLERS = {}

def configure_logging(project_name: str, log_level: str = "INFO"):
    global LOGURU_HANDLERS
    for handler_id in list(LOGURU_HANDLERS.keys()):
        try:
            logger.remove(handler_id)
            del LOGURU_HANDLERS[handler_id]
        except ValueError:
            pass

    log_dir = "logs"
    if not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir)
            rprint(f"[green]Created log directory: {log_dir}[green]")
        except OSError as e:
            rprint(f"[red]Error creating log directory {log_dir}: {e}. Logging to console only for file logs.[red]")

    log_file_path = os.path.join(log_dir, f"{project_name}_ad_downloader.log")
    
    try:
        handler_config = {
            "sink": log_file_path, "level": log_level.upper(), "rotation": "10 MB",
            "retention": "7 days", "compression": "zip", "enqueue": True,
            "format": "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}"
        }
        new_handler_id = logger.add(**handler_config)
        LOGURU_HANDLERS[project_name] = new_handler_id
        rprint(f"[green]Logging configured for project '{project_name}'. Log file: {log_file_path} (Handler ID: {new_handler_id})[green]")
    except Exception as e:
        rprint(f"[red]Failed to configure file logging for project '{project_name}': {e}[red]")
        rprint("[orange3]Logging will proceed with default stderr/console loggers if any.[orange3]")

def close_logger():
    pass # Loguru usually handles cleanup

# --- Validators ---
class NumberValidator:
    @staticmethod
    def validate_number(answers, current):
        if not current.isdigit():
            raise ValidationError("", reason="Invalid input. Please enter a valid number.")
        return True

class DateValidator:
    @staticmethod
    def validate_date(answers, current):
        if not current:
            rprint("[yellow]Validator DateValidator: Date input is empty. A date is required.[yellow]")
            raise ValidationError("", reason="Date cannot be empty. Please use YYYY-MM-DD format.")
        try:
            datetime.strptime(current, "%Y-%m-%d")
            return True
        except ValueError:
            rprint(f"[red]Validator DateValidator: Invalid date format for '{current}'.[red]")
            raise ValidationError("", reason="Invalid date format. Please use YYYY-MM-DD.")

class CountryValidator:
    @staticmethod
    def validate_country(answers, current):
        if not current.strip():
            return True 
        countries = [country.strip().upper() for country in current.split(',')]
        for country_code in countries:
            if not re.match(r"^[A-Z]{2}$", country_code):
                rprint(f"[red]Validator CountryValidator: Invalid country code format for '{country_code}'.[red]")
                raise ValidationError("", reason=f"Invalid country code: '{country_code}'.")
        return True

class ExcelValidator:
    @staticmethod
    def validate_excel(answers, current):
        filename_to_validate = current.strip()
        rprint(f"[cyan]Validator ExcelValidator: Validating Excel filename: '{filename_to_validate}'...[cyan]")
        
        # --- Added CWD and explicit path logging ---
        current_working_directory = os.getcwd()
        rprint(f"[magenta]Validator ExcelValidator: Current Working Directory is: {current_working_directory}[magenta]")
        
        if not filename_to_validate:
            rprint(f"[red]Validator ExcelValidator: Excel filename cannot be empty.[red]")
            raise ValidationError("", reason="Excel filename cannot be empty.")

        # Construct path relative to CWD
        file_path_relative_to_cwd = os.path.join("data", filename_to_validate)
        # Resolve to absolute path
        abs_file_path = os.path.abspath(file_path_relative_to_cwd)
        
        rprint(f"[cyan]Validator ExcelValidator: Relative path constructed: '{file_path_relative_to_cwd}'[cyan]")
        rprint(f"[cyan]Validator ExcelValidator: Absolute path resolved to: {abs_file_path}[cyan]")

        if not filename_to_validate.lower().endswith(('.xlsx', '.xls')):
            rprint(f"[red]Validator ExcelValidator: Invalid file extension for '{filename_to_validate}'. Must be .xlsx or .xls.[red]")
            raise ValidationError("", reason=f"Invalid file extension: '{filename_to_validate}'.")

        # Explicitly check existence using the absolute path
        if not os.path.exists(abs_file_path):
            rprint(f"[red]Validator ExcelValidator (checking absolute path '{abs_file_path}'): File does not exist.[red]")
            # For thoroughness, also show if the relative path check would fail from the CWD
            if not os.path.exists(file_path_relative_to_cwd):
                 rprint(f"[red]Validator ExcelValidator (checking relative path '{file_path_relative_to_cwd}' from CWD): File also does not exist.[red]")
            raise ValidationError(
                "",
                reason=f"File '{filename_to_validate}' (expected at '{abs_file_path}') does not exist. Ensure it's in the 'data' folder inside your project directory '{current_working_directory}'."
            )
        
        # If we reach here, os.path.exists(abs_file_path) was true
        rprint(f"[yellow]Validator ExcelValidator: File '{abs_file_path}' confirmed to exist. Attempting minimal read (sheet names) for validation...[yellow]")
        try:
            excel_file_obj = pd.ExcelFile(abs_file_path) # Use absolute path for pd.ExcelFile
            if not excel_file_obj.sheet_names:
                 rprint(f"[orange3]Validator ExcelValidator: Excel file '{abs_file_path}' contains no sheets.[orange3]")
                 raise ValidationError("", reason=f"Excel file '{filename_to_validate}' (at '{abs_file_path}') has no sheets or is empty.")
            rprint(f"[green]Validator ExcelValidator: Excel file '{abs_file_path}' seems valid and readable (sheets: {excel_file_obj.sheet_names}).[green]")
        except Exception as e:
            rprint(f"[red]Validator ExcelValidator: Error during minimal validation of '{abs_file_path}': {e}[red]")
            import traceback
            rprint(traceback.format_exc())
            raise ValidationError(
                "",
                reason=f"Could not validate Excel file '{filename_to_validate}' (at '{abs_file_path}'). It might be corrupted or not a valid Excel format. Error: {type(e).__name__} - {e}"
            )
        return True

# --- Other Utility Functions ---
def update_access_token(data: pd.DataFrame, new_access_token: str) -> pd.DataFrame:
    rprint(f"[cyan]Attempting to update access tokens in ad snapshot URLs...[cyan]")
    if 'ad_snapshot_url' not in data.columns:
        rprint("[orange3]Warning: 'ad_snapshot_url' column not found in data. Cannot update access tokens.[orange3]")
        return data
    if not new_access_token:
        rprint("[orange3]Warning: Provided new access token is empty. Snapshot URLs will not be updated.[orange3]")
        return data
    updated_count = 0
    def replace_token(url):
        nonlocal updated_count
        if isinstance(url, str) and 'access_token=' in url:
            new_url = re.sub(r'access_token=([^&]+)', f'access_token={new_access_token}', url)
            if new_url != url:
                updated_count +=1
            return new_url
        return url
    data['ad_snapshot_url'] = data['ad_snapshot_url'].apply(replace_token)
    if updated_count > 0:
        rprint(f"[green]Access tokens updated in {updated_count} ad snapshot URLs.[green]")
    else:
        rprint(f"[yellow]No ad snapshot URLs required an access token update (or no URLs found with tokens).[yellow]")
    return data

if __name__ == '__main__':
    rprint("Testing AdDownloader helper functions (run this file directly for isolated tests)")
    configure_logging("helpers_direct_test")
    logger.info("Test log message from helpers.py direct execution.")
    
    # --- Test ExcelValidator ---
    rprint("\n--- Testing ExcelValidator ---")
    if not os.path.exists("data"): # Ensure 'data' directory exists in CWD for test
        try:
            os.makedirs("data")
            rprint(f"Created 'data' directory in {os.getcwd()} for testing.")
        except Exception as e:
            rprint(f"Failed to create 'data' directory in {os.getcwd()}: {e}")

    dummy_excel_valid_name = "validate_me_valid.xlsx"
    dummy_excel_valid = os.path.join("data", dummy_excel_valid_name)
    if not os.path.exists(dummy_excel_valid):
        try:
            pd.DataFrame({'col1': [1,2]}).to_excel(dummy_excel_valid, index=False)
            rprint(f"Created dummy file for validation: {dummy_excel_valid}")
        except Exception as e:
            rprint(f"Could not create {dummy_excel_valid}: {e}")

    # ... (rest of the __main__ test block from previous version) ...
    test_cases = [
        ("Test 1: Valid file", dummy_excel_valid_name, True),
        ("Test 2: Non-existent file", "non_existent.xlsx", False),
    ]
    for desc, filename, should_pass in test_cases:
        rprint(f"\n{desc}: '{filename}' (Expected to {'pass' if should_pass else 'fail'})")
        try:
            # Simulate 'answers' dict being empty as it's not used by this static validator
            result = ExcelValidator.validate_excel({}, filename) 
            if should_pass:
                rprint(f"[green]PASSED (as expected)[green]")
            else:
                rprint(f"[red]FAILED (was expected to fail validation but passed)[red]")
        except ValidationError as e:
            if not should_pass:
                rprint(f"[green]PASSED (correctly failed with reason: {e.reason})[green]")
            else:
                rprint(f"[red]FAILED (was expected to pass but failed with reason: {e.reason})[red]")
        except Exception as e:
            rprint(f"[bold red]UNEXPECTED ERROR during '{desc}': {e}[bold red]")
            import traceback
            rprint(traceback.format_exc())

    close_logger()
    rprint("\nHelper module direct test finished.")