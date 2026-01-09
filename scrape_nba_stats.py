#!/usr/bin/env python3
"""
NBA Player Stats Scraper
Scrapes player statistics from Basketball-Reference.com for specified years.
"""

import os
import sys
import re
import time
import argparse
import gzip
import urllib.request
from typing import List, Optional
import requests
import pandas as pd
from bs4 import BeautifulSoup


# Stat types and their URL mappings
STAT_TYPES = {
    'totals': 'totals',
    'per_game': 'per_game',
    'per_minute': 'per_minute',
    'per_poss': 'per_poss',
    'advanced': 'advanced',
    'play-by-play': 'play-by-play',
    'shooting': 'shooting',
    'adj_shooting': 'adj_shooting'
}


def extract_player_id(url: str) -> Optional[str]:
    """
    Extract player ID from Basketball-Reference player URL.
    
    Args:
        url: Player URL (e.g., '/players/g/gilgesh01.html')
    
    Returns:
        Player ID (e.g., 'gilgesh01') or None if not found
    """
    if not url or not isinstance(url, str):
        return None
    
    # Pattern: /players/[first_letter]/[player_id].html
    pattern = r'/players/[a-z]/([a-z0-9]+)\.html'
    match = re.search(pattern, url)
    
    if match:
        return match.group(1)
    return None


# Create a session to maintain cookies and appear more browser-like
_session = None

def get_session():
    """Get or create a requests session with browser-like headers."""
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Cache-Control': 'max-age=0',
        })
    return _session


def get_headers():
    """Get headers dictionary for urllib requests."""
    return {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Cache-Control': 'max-age=0',
    }


def fetch_html_with_fallback(url: str) -> Optional[str]:
    """Fetch HTML using requests, with urllib fallback if requests fails."""
    # Try requests first
    try:
        session = get_session()
        response = session.get(url, timeout=30)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException:
        # Fallback to urllib (sometimes works when requests is blocked)
        try:
            req = urllib.request.Request(url, headers=get_headers())
            with urllib.request.urlopen(req, timeout=30) as response:
                data = response.read()
                # Check if content is gzipped
                if data[:2] == b'\x1f\x8b':  # Gzip magic number
                    return gzip.decompress(data).decode('utf-8')
                else:
                    return data.decode('utf-8')
        except Exception as e:
            print(f"urllib fallback also failed: {e}")
            return None


def scrape_stat_table(year: int, stat_type: str) -> Optional[pd.DataFrame]:
    """
    Scrape a single stat table for a given year from Basketball-Reference.
    Uses pandas.read_html() directly on URL for table parsing.
    
    Args:
        year: NBA season year (e.g., 2025 for 2024-25 season)
        stat_type: Type of stats to scrape (e.g., 'totals', 'per_game')
    
    Returns:
        DataFrame with player stats, or None if scraping fails
    """
    # Construct URL
    url = f"https://www.basketball-reference.com/leagues/NBA_{year}_{stat_type}.html"
    
    try:
        # Try using pandas.read_html() directly on the URL first
        # This is simpler and pandas handles the HTTP request internally
        dfs = None
        html_content = None
        
        try:
            dfs = pd.read_html(url, attrs={'id': stat_type})
            # If successful, try to get HTML for player ID extraction
            html_content = fetch_html_with_fallback(url)
        except (ValueError, Exception) as e:
            # pandas.read_html() failed - try fallback method
            pass
        
        if not dfs:
            try:
                # Try without specifying table ID
                dfs = pd.read_html(url)
                if dfs:
                    html_content = fetch_html_with_fallback(url)
            except (ValueError, Exception) as e:
                # Still failed - use fallback method
                pass
        
        # If pandas.read_html() didn't work, use our fallback approach
        if not dfs:
            # Fetch HTML using fallback method (requests -> urllib)
            html_content = fetch_html_with_fallback(url)
            
            if not html_content:
                print(f"Could not fetch HTML")
                return None
            
            # Parse HTML with BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            table = soup.find('table', {'id': stat_type})
            if not table:
                table = soup.find('table', class_='sortable')
            
            if not table:
                print(f"Could not find table")
                return None
            
            # Parse table with pandas from HTML string
            dfs = pd.read_html(str(table))
        
        if not dfs:
            print(f"Could not parse table")
            return None
        
        df = dfs[0]
        
        # Get HTML for player ID extraction if we don't have it yet
        if html_content is None:
            html_content = fetch_html_with_fallback(url)
        
        if html_content:
            soup = BeautifulSoup(html_content, 'html.parser')
        else:
            print(f"Warning: Could not fetch HTML for player ID extraction")
            soup = None
        
        # Find the stats table to extract player links
        if soup:
            table = soup.find('table', {'id': stat_type})
            if not table:
                table = soup.find('table', class_='sortable')
        else:
            table = None
        
        if not table:
            print(f"Warning: Could not find table HTML for player ID extraction")
            # Continue without player IDs - user can add them manually
            return df
        
        # Extract player IDs from HTML rows
        player_ids = []
        tbody = table.find('tbody')
        if tbody:
            rows = tbody.find_all('tr')
        else:
            all_rows = table.find_all('tr')
            rows = [r for r in all_rows if not (r.get('class') and 'thead' in r.get('class'))]
        
        for row in rows:
            if row.get('class') and 'thead' in row.get('class'):
                continue
            link = row.find('a', href=re.compile(r'/players/'))
            if link and link.get('href'):
                player_id = extract_player_id(link.get('href'))
                player_ids.append(player_id)
            else:
                player_ids.append(None)
        
        # Polite delay to avoid rate limiting (3 seconds between requests)
        # Sports Reference limit: 20 requests per minute (60/20 = 3 seconds)
        time.sleep(3)
        
        # Clean up dataframe - remove header rows that pandas might have included
        # Remove rows where first column is 'Rk' or 'Player'
        if len(df) > 0:
            first_col = df.iloc[:, 0]
            df = df[~first_col.isin(['Rk', 'Player'])].copy()
            df = df[df.iloc[:, 0].notna()].copy()
        
        # Match player_ids to dataframe rows
        # Remove None entries from player_ids that don't correspond to data rows
        valid_player_ids = [pid for pid in player_ids if pid is not None]
        
        # If we have more player_ids than rows, trim to match
        # If we have fewer, pad with None
        if len(valid_player_ids) >= len(df):
            player_ids_for_df = valid_player_ids[:len(df)]
        else:
            # Pad with None if needed
            player_ids_for_df = valid_player_ids + [None] * (len(df) - len(valid_player_ids))
            player_ids_for_df = player_ids_for_df[:len(df)]
        
        # Alternative: match by extracting player names and matching
        # This is more reliable if row counts don't match
        if len(player_ids_for_df) != len(df) or any(pid is None for pid in player_ids_for_df):
            # Re-extract by matching player names
            player_ids_for_df = []
            player_name_col = None
            
            # Find player name column
            for col in df.columns:
                col_str = str(col).lower()
                if 'player' in col_str and 'id' not in col_str:
                    player_name_col = col
                    break
            
            if player_name_col:
                # Create a mapping from HTML
                name_to_id = {}
                for row in rows:
                    link = row.find('a', href=re.compile(r'/players/'))
                    if link:
                        player_id = extract_player_id(link.get('href'))
                        player_name = link.get_text(strip=True)
                        if player_id and player_name:
                            name_to_id[player_name] = player_id
                
                # Match by player name
                for _, df_row in df.iterrows():
                    player_name = str(df_row[player_name_col]).strip()
                    player_id = name_to_id.get(player_name)
                    player_ids_for_df.append(player_id)
            else:
                # Fallback: use the original method
                player_ids_for_df = player_ids[:len(df)]
        
        # Add player_id column at the beginning
        if len(player_ids_for_df) == len(df):
            df.insert(0, 'player_id', player_ids_for_df)
        else:
            # Last resort: pad or trim
            while len(player_ids_for_df) < len(df):
                player_ids_for_df.append(None)
            player_ids_for_df = player_ids_for_df[:len(df)]
            df.insert(0, 'player_id', player_ids_for_df)
        
        # Clean up: remove rows where player_id is None (shouldn't happen, but just in case)
        df = df[df['player_id'].notna()].copy()
        
        return df
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data for {stat_type} in {year}: {e}")
        return None
    except Exception as e:
        print(f"Error parsing data for {stat_type} in {year}: {e}")
        return None


def save_to_csv(df: pd.DataFrame, year: int, stat_type: str) -> bool:
    """
    Save scraped data to CSV in year folder.
    
    Args:
        df: DataFrame to save
        year: NBA season year
        stat_type: Type of stats (used for filename)
    
    Returns:
        True if successful, False otherwise
    """
    if df is None or df.empty:
        print(f"Warning: No data to save for {stat_type} in {year}")
        return False
    
    try:
        # Create data/year folder structure if it doesn't exist
        data_folder = 'data'
        year_folder = os.path.join(data_folder, str(year))
        os.makedirs(year_folder, exist_ok=True)
        
        # Map stat_type to filename
        filename_map = {
            'totals': 'totals.csv',
            'per_game': 'per_game.csv',
            'per_minute': 'per_minute.csv',
            'per_poss': 'per_poss.csv',
            'advanced': 'advanced.csv',
            'play-by-play': 'play_by_play.csv',
            'shooting': 'shooting.csv',
            'adj_shooting': 'adj_shooting.csv'
        }
        
        filename = filename_map.get(stat_type, f"{stat_type}.csv")
        filepath = os.path.join(year_folder, filename)
        
        # Save to CSV
        df.to_csv(filepath, index=False)
        print(f"Saved {filepath} ({len(df)} rows)")
        return True
        
    except Exception as e:
        print(f"Error saving {stat_type} for {year}: {e}")
        return False


def scrape_year(year: int) -> None:
    """
    Scrape all 8 stat types for a single year.
    
    Args:
        year: NBA season year
    """
    print(f"\nScraping NBA {year} season stats...")
    print("=" * 50)
    
    success_count = 0
    stat_types_list = list(STAT_TYPES.values())
    for i, stat_type in enumerate(stat_types_list):
        print(f"Scraping {stat_type}...", end=" ")
        df = scrape_stat_table(year, stat_type)
        
        if df is not None and not df.empty:
            if save_to_csv(df, year, stat_type):
                success_count += 1
            else:
                print(f"Failed to save {stat_type}")
        else:
            print(f"Failed to scrape {stat_type}")
        
        # Note: No additional delay needed here - the 3-second delay in scrape_stat_table()
        # already ensures we stay within Sports Reference's 20 requests/minute limit
    
    print("=" * 50)
    print(f"Completed: {success_count}/{len(STAT_TYPES)} stat types scraped successfully for {year}")


def main():
    """Handle command-line arguments and orchestrate scraping."""
    parser = argparse.ArgumentParser(
        description='Scrape NBA player statistics from Basketball-Reference.com'
    )
    parser.add_argument(
        'years',
        nargs='*',
        type=int,
        help='Year(s) to scrape (e.g., 2025 or 2024 2025). If not provided, will prompt for input.'
    )
    
    args = parser.parse_args()
    
    years = args.years
    
    # If no years provided, prompt for input
    if not years:
        print("Enter year(s) to scrape (e.g., 2025 or 2024 2025):")
        user_input = input().strip()
        try:
            years = [int(y.strip()) for y in user_input.split()]
        except ValueError:
            print("Error: Invalid input. Please enter one or more years (e.g., 2025 or 2024 2025)")
            sys.exit(1)
    
    if not years:
        print("Error: No years specified")
        sys.exit(1)
    
    # Validate years (NBA started in 1946, reasonable upper bound)
    valid_years = []
    for year in years:
        if 1946 <= year <= 2100:
            valid_years.append(year)
        else:
            print(f"Warning: Skipping invalid year {year} (must be between 1946 and 2100)")
    
    if not valid_years:
        print("Error: No valid years to scrape")
        sys.exit(1)
    
    # Scrape each year
    for i, year in enumerate(valid_years):
        try:
            scrape_year(year)
            # Add delay between years (except after the last one)
            if i < len(valid_years) - 1:
                print(f"\nWaiting 3 seconds before next year...")
                time.sleep(3)
        except KeyboardInterrupt:
            print("\n\nScraping interrupted by user")
            sys.exit(1)
        except Exception as e:
            print(f"\nError scraping year {year}: {e}")
            continue
    
    print("\nAll scraping completed!")


if __name__ == '__main__':
    main()

