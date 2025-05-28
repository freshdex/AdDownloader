"""
This module provides the AdLibAPI class to interact with the Meta Ad Library API.
It handles fetching ads data based on specified parameters.
"""
# AdDownloader/adlib_api.py

import requests
import pandas as pd
import time
import os
import datetime
from rich import print as rprint # For rich console output
# from rich.progress import track # Optional for later
# Removed: from .helpers import load_config (as it's not needed here)

class AdLibAPI:
    """
    A class to interact with the Meta Ad Library API.

    This class provides methods to set parameters for API requests,
    download ad data, and save it to specified formats.
    """
    BASE_URL = 'https://graph.facebook.com/v22.0/ads_archive' # Base URL for the API
    
    FIELDS = 'id, ad_delivery_start_time, ad_delivery_stop_time, ad_creative_bodies, ad_creative_link_captions, ad_creative_link_descriptions, ad_creative_link_titles, ad_snapshot_url, beneficiary_payers, languages, page_id, page_name, target_ages, target_gender, target_locations, eu_total_reach, age_country_gender_reach_breakdown'
    LIMIT = '300' 

    def __init__(self, access_token: str, project_name: str = "default_project"):
        if not access_token:
            rprint("[red]Error: Access token cannot be empty.[red]")
            raise ValueError("Access token is required to initialize AdLibAPI.")
        
        self.access_token = access_token
        self.project_name = project_name if project_name and project_name.strip() else "default_project"
        self.params = {
            'access_token': self.access_token,
            'fields': self.FIELDS,
            'limit': self.LIMIT 
        }
        self.data_path = f'output/{self.project_name}/ads_data'
        if not os.path.exists(self.data_path):
            try:
                os.makedirs(self.data_path)
                rprint(f"[green]Created directory: {self.data_path}[green]")
            except OSError as e:
                rprint(f"[red]Error creating directory {self.data_path}: {e}[red]")
                # Decide if this is a critical error that should stop execution
                raise

    def read_excel_pages_id(self, file_name: str) -> list:
        rprint(f"[cyan]Method read_excel_pages_id: Attempting to read Excel file: 'data/{file_name}'...[cyan]")
        page_ids_list = []
        # Assuming 'data' folder is in the current working directory from where AdDownloader is run
        # which should be the project root (D:\jackpoteh\AdDownloader)
        file_path = os.path.join("data", file_name) 
        
        rprint(f"[cyan]Method read_excel_pages_id: Calculated full file path: {os.path.abspath(file_path)}[cyan]")

        try:
            if not os.path.exists(file_path):
                rprint(f"[red]Method read_excel_pages_id: Error - Excel file '{file_path}' does not exist at the expected location.[red]")
                return []
            
            rprint(f"[yellow]Method read_excel_pages_id: File 'data/{file_name}' exists. Attempting to read with pandas...[yellow]")
            # This is the potentially slow part
            df = pd.read_excel(file_path, sheet_name=0) 
            rprint(f"[green]Method read_excel_pages_id: Pandas has finished reading 'data/{file_name}'. Processing data...[green]")
            
            if df.empty:
                rprint(f"[orange3]Method read_excel_pages_id: Warning - Excel file 'data/{file_name}' is empty after reading.[orange3]")
                return []

            id_col_name = None
            # Try to find a column named 'page_id' or 'Page ID' (case-insensitive)
            for col in df.columns:
                if str(col).strip().lower() == 'page_id': # Added strip() for column names
                    id_col_name = col
                    rprint(f"[cyan]Method read_excel_pages_id: Found 'page_id' column: '{id_col_name}'[cyan]")
                    break
            
            if id_col_name:
                page_ids_list = df[id_col_name].astype(str).str.strip().dropna().unique().tolist()
            else:
                rprint(f"[yellow]Method read_excel_pages_id: No 'page_id' column found. Using first column (index 0) for page IDs.[yellow]")
                page_ids_list = df.iloc[:, 0].astype(str).str.strip().dropna().unique().tolist()
            
            # Filter out any potential empty strings or 'nan' strings that might have resulted from empty cells
            page_ids_list = [pid for pid in page_ids_list if pid and pid.lower() != 'nan' and pid.strip()]
            rprint(f"[cyan]Method read_excel_pages_id: Finished processing IDs. Found {len(page_ids_list)} unique, non-empty IDs.[cyan]")

            if page_ids_list:
                rprint(f"[green]Method read_excel_pages_id: Successfully processed {len(page_ids_list)} unique page IDs from 'data/{file_name}'.[green]")
            else:
                rprint(f"[orange3]Method read_excel_pages_id: No valid page IDs extracted from 'data/{file_name}'.[orange3]")
            
            return page_ids_list

        except Exception as e:
            rprint(f"[bold red]Method read_excel_pages_id: An unexpected error occurred: {e}[bold red]")
            import traceback
            rprint(traceback.format_exc()) # Print full traceback for debugging
            return []


    def add_parameters(self, ad_reached_countries="NL", ad_type="ALL", search_page_ids=None, 
                       search_terms=None, ad_delivery_date_min='2023-01-01', 
                       ad_delivery_date_max=datetime.date.today().strftime('%Y-%m-%d'), limit=None):
        rprint("[cyan]Method add_parameters: Adding parameters...[cyan]")
        self.params['ad_reached_countries'] = ad_reached_countries if ad_reached_countries else "NL"
        self.params['ad_type'] = ad_type if ad_type else "ALL"
        
        if search_page_ids:
            rprint(f"[cyan]Method add_parameters: Processing search_page_ids input: {search_page_ids}[cyan]")
            if isinstance(search_page_ids, str): 
                processed_page_ids = self.read_excel_pages_id(search_page_ids)
                if not processed_page_ids:
                    rprint(f"[orange3]Method add_parameters: Warning - Proceeding without page IDs as none were loaded from '{search_page_ids}'.[orange3]")
                    self.params['search_page_ids'] = None 
                else:
                    self.params['search_page_ids'] = ','.join(processed_page_ids) 
            elif isinstance(search_page_ids, list):
                self.params['search_page_ids'] = ','.join(str(pid) for pid in search_page_ids if str(pid).strip()) # Ensure all are strings and not empty
            else:
                rprint(f"[orange3]Method add_parameters: search_page_ids is not a string or list, ignoring: {type(search_page_ids)}[orange3]")
                self.params['search_page_ids'] = None
        else:
             self.params.pop('search_page_ids', None) 

        if search_terms:
            self.params['search_terms'] = search_terms
        else:
            self.params.pop('search_terms', None)

        if self.params.get('search_page_ids') and self.params.get('search_terms'):
            rprint("[orange3]Method add_parameters: Warning - Both search_page_ids and search_terms provided. API behavior may vary.[orange3]")

        self.params['ad_delivery_date_min'] = ad_delivery_date_min if ad_delivery_date_min else '2023-01-01'
        self.params['ad_delivery_date_max'] = ad_delivery_date_max if ad_delivery_date_max else datetime.date.today().strftime('%Y-%m-%d')
        
        if limit:
            self.params['limit'] = str(limit) 
        else:
            self.params['limit'] = self.LIMIT 
        rprint("[cyan]Method add_parameters: Parameters updated.[cyan]")


    def get_parameters(self) -> dict:
        return self.params

    def start_download(self, output_format: str = "csv"):
        all_ads_data = []
        page_counter = 1
        data_fetched_successfully = False

        raw_json_dir = os.path.join(self.data_path, 'raw_json_responses')
        if not os.path.exists(raw_json_dir):
            try:
                os.makedirs(raw_json_dir)
            except OSError as e:
                rprint(f"[red]Error creating raw JSON directory {raw_json_dir}: {e}[red]")
                # Potentially stop if this dir is critical
                return


        current_params = self.params.copy() 

        while True:
            rprint(f"[cyan]##### Starting reading page {page_counter} from API #####[cyan]")
            try:
                response = requests.get(self.BASE_URL, params=current_params, timeout=60) 
                response.raise_for_status() 
                data = response.json()
            except requests.exceptions.HTTPError as e:
                rprint(f"[red]HTTP Error on page {page_counter}: {e.response.status_code} - {e.response.text[:500]}...[red]")
                api_error_content = {}
                try:
                    api_error_content = e.response.json()
                except ValueError: # Handle cases where response is not JSON
                    pass # rprint above already logged text part
                if api_error_content.get("error", {}).get("message"):
                     rprint(f"[red]API Error Message: {api_error_content['error']['message']}[red]")
                break 
            except requests.exceptions.Timeout:
                rprint(f"[red]Request timed out on page {page_counter}. Try increasing timeout or check network.[red]")
                break
            except requests.exceptions.RequestException as e:
                rprint(f"[red]Request failed on page {page_counter}: {e}[red]")
                break
            except ValueError as e: # Includes JSONDecodeError
                rprint(f"[red]Error decoding JSON response on page {page_counter}: {e}[red]")
                if 'response' in locals() and response is not None: # Check if response object exists
                    rprint(f"[red]Response content (first 500 chars): {response.text[:500]}...[red]")
                break

            try:
                with open(os.path.join(raw_json_dir, f'{self.project_name}_page_{page_counter}.json'), 'w', encoding='utf-8') as f:
                    json.dump(data, f, ensure_ascii=False, indent=4)
            except Exception as e:
                rprint(f"[orange3]Warning: Could not save raw JSON for page {page_counter}: {e}[orange3]")

            if data.get('data'): 
                all_ads_data.extend(data['data'])
                data_fetched_successfully = True 
                rprint(f"[green]Fetched {len(data['data'])} ads from page {page_counter}. Total ads so far: {len(all_ads_data)}.[green]")
                
                if 'paging' in data and 'next' in data['paging']:
                    if 'cursors' in data['paging'] and 'after' in data['paging']['cursors']:
                         current_params['after'] = data['paging']['cursors']['after']
                         page_counter += 1
                    else: 
                         rprint("[yellow]No 'after' cursor in paging information. Assuming end of results by this method.[yellow]")
                         break 
                else:
                    rprint("[yellow]No 'next' page in paging information. Download complete for this query.[yellow]")
                    break 
            else:
                rprint(f"[orange3]No data in 'data' field on page {page_counter}.[orange3]")
                if "error" in data:
                    rprint(f"[red]API Error: {data['error'].get('message', 'Unknown error')}[red]")
                elif not data: # Empty response
                     rprint(f"[orange3]Empty response from API on page {page_counter}.[orange3]")
                break 

            time.sleep(1)

        if not data_fetched_successfully:
            rprint("[red]No ad data was successfully fetched from the API.[red]")
            return

        if not all_ads_data:
            rprint("[orange3]No ad data was collected after processing all pages.[orange3]")
            return

        df_all_ads = pd.DataFrame(all_ads_data)
        rprint(f"[green]Total ads collected: {len(df_all_ads)}[green]")

        file_basename = os.path.join(self.data_path, f"{self.project_name}_original_data")
        output_path = ""

        try:
            if output_format == 'csv':
                output_path = f"{file_basename}.csv"
                df_all_ads.to_csv(output_path, index=False, encoding='utf-8-sig')
            elif output_format == 'json':
                output_path = f"{file_basename}.json"
                df_all_ads.to_json(output_path, orient='records', indent=4, force_ascii=False)
            elif output_format == 'xlsx':
                output_path = f"{file_basename}.xlsx"
                df_all_ads.to_excel(output_path, index=False, engine='openpyxl')
            else:
                rprint(f"[red]Unsupported output format: {output_format}. Defaulting to CSV.[red]")
                output_path = f"{file_basename}.csv"
                df_all_ads.to_csv(output_path, index=False, encoding='utf-8-sig')
            
            if output_path:
                 rprint(f"[green bold]All ad data saved to {output_path}[green bold]")

        except Exception as e:
             rprint(f"[red]Error saving data to {output_format} at {output_path}: {e}[red]")
             rprint(f"[orange3]Attempting to save as CSV fallback...[orange3]")
             try:
                 output_path_csv_fallback = f"{file_basename}_fallback.csv"
                 df_all_ads.to_csv(output_path_csv_fallback, index=False, encoding='utf-8-sig')
                 rprint(f"[green bold]Fallback data saved to {output_path_csv_fallback}[green bold]")
             except Exception as fb_e:
                 rprint(f"[bold red]Failed to save data even as CSV fallback: {fb_e}[bold red]")


if __name__ == '__main__':
    # Example usage (for testing this module directly)
    if not os.path.exists("data"):
        os.makedirs("data")
    dummy_excel_data = {'page_id': ['12345', '67890', ' ', None, 'nan']} # Added more test cases
    dummy_df = pd.DataFrame(dummy_excel_data)
    dummy_excel_path = os.path.join("data", "test_pages.xlsx")
    if not os.path.exists(dummy_excel_path):
        dummy_df.to_excel(dummy_excel_path, index=False)
        rprint(f"Created dummy Excel file: {dummy_excel_path}")

    TEST_ACCESS_TOKEN = "YOUR_ACTUAL_ACCESS_TOKEN" 

    if TEST_ACCESS_TOKEN == "YOUR_ACTUAL_ACCESS_TOKEN":
        rprint("[bold red]Please replace 'YOUR_ACTUAL_ACCESS_TOKEN' with a real token to test API calls.[bold red]")
        # Test local file reading without API call
        rprint("\n--- Testing Excel Reading Locally ---")
        api_client_local_test = AdLibAPI(access_token="dummy_token_for_local_test", project_name="local_excel_read_test")
        ids = api_client_local_test.read_excel_pages_id("test_pages.xlsx")
        rprint(f"IDs read: {ids}")
        api_client_local_test.add_parameters(search_page_ids="test_pages.xlsx")
        rprint(f"Parameters after adding page IDs: {api_client_local_test.get_parameters()}")

    else:
        rprint(f"Using test access token: {TEST_ACCESS_TOKEN[:10]}...") 
        api_client = AdLibAPI(access_token=TEST_ACCESS_TOKEN, project_name="api_test_project")
        api_client.add_parameters(
            search_terms="sustainable products", 
            ad_reached_countries="US",
            ad_delivery_date_min="2024-01-01",
            ad_delivery_date_max="2024-01-15",
            limit=5
        )
        rprint("Parameters for Test 1:")
        rprint(api_client.get_parameters())
        # api_client.start_download(output_format="csv") 

        api_client_pages = AdLibAPI(access_token=TEST_ACCESS_TOKEN, project_name="api_test_pages_project")
        api_client_pages.add_parameters(
            search_page_ids="test_pages.xlsx", 
            ad_reached_countries="GB",
            limit=3
        )
        rprint("\nParameters for Test 2 (Page IDs):")
        rprint(api_client_pages.get_parameters())
        # api_client_pages.start_download(output_format="json") 
    
    rprint("\nModule direct test finished.")