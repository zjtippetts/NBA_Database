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
    'per_36': 'per_minute',
    'per_100_poss': 'per_poss',
    'advanced': 'advanced',
    'play-by-play': 'play-by-play',
    'shooting': 'shooting',
    'adj_shooting': 'adj_shooting'
}


def clean_column_name(col_name):
    """Clean column names: remove special chars, spaces, handle numbers, etc."""
    if pd.isna(col_name) or col_name == '':
        return 'Unnamed'
    
    col = str(col_name)
    needs_leading_underscore = False
    
    # Handle columns starting with numbers - add underscore prefix
    # Check for ranges first (they contain -)
    if '-' in col and not col.startswith('%'):
        if col.startswith('0-3'):
            col = 'range_0_3' + col[3:]
        elif col.startswith('3-10'):
            col = 'range_3_10' + col[4:]
        elif col.startswith('10-16'):
            col = 'range_10_16' + col[5:]
        elif col.startswith('16-3P'):
            col = 'range_16_3P' + col[5:]
    # Handle columns starting with 2P or 3P
    elif col.startswith('2P'):
        col = '_2P' + col[2:]
        needs_leading_underscore = True
    elif col.startswith('3P'):
        col = '_3P' + col[2:]
        needs_leading_underscore = True
    # Handle other columns starting with digits
    elif col and col[0].isdigit():
        col = '_' + col
        needs_leading_underscore = True
    
    # Remove parentheses and incorporate content
    col = re.sub(r'\(% of FGA\)', '_pct_of_FGA', col)
    col = re.sub(r'\(FG%\)', '_FG_pct', col)
    col = re.sub(r'\(% AST\'d\)', '_pct_ASTd', col)
    col = re.sub(r'\(Corner 3s\)', '_Corner_3s', col)
    col = re.sub(r'\(([^)]+)\)', r'_\1', col)  # Any other parentheses
    
    # Handle percentage signs
    col = col.replace('%', '_pct')
    
    # Handle special characters
    col = col.replace('+', '')  # Remove +, keep _LA
    col = col.replace('/', '_per_')
    col = col.replace('-', '_')
    col = col.replace(' ', '_')
    col = col.replace('.', '')
    col = col.replace('#', '_ct')
    col = col.replace("'", '')
    
    # Clean up multiple underscores
    col = re.sub(r'_+', '_', col)
    
    # Remove trailing underscores, but preserve leading underscore if we added it for numbers
    col = col.rstrip('_')
    if not needs_leading_underscore:
        col = col.lstrip('_')
    
    return col


def handle_traded_players(df):
    """
    Handle players who were traded during the season.
    - Keep only the total row (2TM, 3TM, etc.)
    - Replace TM code with comma-separated team abbreviations in order
    - Remove individual team rows
    
    Args:
        df: DataFrame with player stats
        
    Returns:
        DataFrame with traded players handled
    """
    if df.empty or 'player_id' not in df.columns or 'Team' not in df.columns:
        return df
    
    # Find all rows with TM in Team column (traded players' total rows)
    tm_mask = df['Team'].astype(str).str.contains('TM', na=False)
    tm_rows = df[tm_mask].copy()
    
    if tm_rows.empty:
        return df
    
    # Process each traded player
    indices_to_drop = []
    
    for idx, tm_row in tm_rows.iterrows():
        player_id = tm_row['player_id']
        
        # Get all rows for this player
        player_rows = df[df['player_id'] == player_id].copy()
        
        # Get individual team rows (non-TM rows)
        team_rows = player_rows[~player_rows['Team'].astype(str).str.contains('TM', na=False)]
        
        if not team_rows.empty:
            # Extract team abbreviations in order they appear in the dataframe
            teams = team_rows['Team'].astype(str).tolist()
            # Filter out any NaN or empty values, and ensure no TM codes slip through
            teams = [t for t in teams if t and t != 'nan' and t.strip() and 'TM' not in t]
            
            if teams:
                # Replace TM code with comma-separated teams (with space after comma)
                df.loc[idx, 'Team'] = ', '.join(teams)
                
                # Mark individual team rows for removal
                indices_to_drop.extend(team_rows.index.tolist())
    
    # Remove individual team rows
    if indices_to_drop:
        df = df.drop(index=indices_to_drop).copy()
        df = df.reset_index(drop=True)
    
    return df


def normalize_columns(df: pd.DataFrame, stat_type: str) -> pd.DataFrame:
    """
    Normalize columns across different stat types:
    1. Keep player_id and year in all tables
    2. Keep biographical info (Player, Age, Team, Pos) only in totals
    3. Keep award columns only in totals
    4. Keep percentage columns (FG_pct, _3P_pct, _2P_pct, eFG_pct, FT_pct) only in totals and shooting
    5. Keep G, GS only in totals (remove from all other tables)
    6. Keep MP in totals and per_game (MP is different in per_game - it's per game, not total)
    7. Rename stat columns with suffixes for clarity (_total, _pGame, _p36, _p100)
    
    Args:
        df: DataFrame to normalize
        stat_type: Type of stats (totals, per_game, per_36, per_100_poss, etc.)
    
    Returns:
        Normalized DataFrame
    """
    # Biographical columns (keep only in totals)
    bio_cols = ['Player', 'Age', 'Team', 'Pos']
    
    # Award columns (keep only in totals)
    award_cols = ['6MOY', 'AS', 'CPOY', 'DEF1', 'DEF2', 'DPOY', 'MIP', 'MVP', 
                   'NBA1', 'NBA2', 'NBA3', 'ROY', 'Trp_Dbl']
    
    # Percentage columns (keep only in adj_shooting)
    pct_cols = ['FG_pct', '_3P_pct', '_2P_pct', 'eFG_pct', 'FT_pct', 'TS_pct']
    
    # G and GS (keep only in totals)
    game_cols = ['G', 'GS']
    
    # MP handling: different in per_game (per game average) vs totals (total minutes)
    # Keep MP in totals and per_game, remove from others
    
    # Stat columns that need renaming (columns that have different values across tables)
    # These are the counting/rate stats, not percentages
    stat_cols_to_rename = ['FG', 'FGA', '_3P', '_3PA', '_2P', '_2PA', 'FT', 'FTA',
                           'ORB', 'DRB', 'TRB', 'AST', 'STL', 'BLK', 'TOV', 'PF', 'PTS']
    
    # Determine suffix based on stat_type
    suffix_map = {
        'totals': '_total',
        'per_game': '_pGame',
        'per_36': '_p36',
        'per_100_poss': '_p100'
    }
    suffix = suffix_map.get(stat_type, '')
    
    # Remove biographical columns if not totals
    if stat_type != 'totals':
        cols_to_drop = [col for col in bio_cols if col in df.columns]
        if cols_to_drop:
            df = df.drop(columns=cols_to_drop)
    
    # Remove award columns if not totals
    if stat_type != 'totals':
        cols_to_drop = [col for col in award_cols if col in df.columns]
        if cols_to_drop:
            df = df.drop(columns=cols_to_drop)
    
    # Remove percentage columns if not adj_shooting (keep only in adj_shooting table)
    if stat_type != 'adj_shooting':
        cols_to_drop = [col for col in pct_cols if col in df.columns]
        if cols_to_drop:
            df = df.drop(columns=cols_to_drop)
    
    # Remove G and GS if not totals
    if stat_type != 'totals':
        cols_to_drop = [col for col in game_cols if col in df.columns]
        if cols_to_drop:
            df = df.drop(columns=cols_to_drop)
    
    # Remove MP if not totals or per_game (MP is different in per_game - it's per game average)
    if stat_type not in ['totals', 'per_game']:
        if 'MP' in df.columns:
            df = df.drop(columns=['MP'])
    
    # Rename stat columns with suffixes
    if suffix:
        rename_dict = {}
        for col in stat_cols_to_rename:
            if col in df.columns:
                rename_dict[col] = col + suffix
        
        # Also rename MP in per_game (it's per game, not total)
        if stat_type == 'per_game' and 'MP' in df.columns:
            rename_dict['MP'] = 'MP_pGame'
    
    # Rename MP to MP_total in totals table for consistency
    if stat_type == 'totals' and 'MP' in df.columns:
        if 'rename_dict' not in locals():
            rename_dict = {}
        rename_dict['MP'] = 'MP_total'
    
    if 'rename_dict' in locals() and rename_dict:
        df = df.rename(columns=rename_dict)
    
    return df


def split_awards_column(df):
    """Split Awards column into separate award columns."""
    if 'Awards' not in df.columns:
        # Check if Column_25 or Column_31 exists and has award data
        for col in ['Column_25', 'Column_31']:
            if col in df.columns:
                # Check if this column has award-like data
                sample = df[col].dropna().head(5)
                if len(sample) > 0 and any(',' in str(val) or '-' in str(val) for val in sample if pd.notna(val)):
                    # This looks like awards data - rename it
                    df = df.rename(columns={col: 'Awards'})
                    break
    
    if 'Awards' not in df.columns:
        return df
    
    # Get all unique awards across all rows
    all_awards = set()
    for awards_str in df['Awards'].dropna():
        if pd.notna(awards_str):
            awards = str(awards_str).split(',')
            for award in awards:
                award = award.strip()
                if award:
                    # Extract base award name (remove number if present)
                    if '-' in award:
                        base_award = award.split('-')[0]
                    else:
                        base_award = award
                    all_awards.add(base_award)
    
    # Create columns for each award
    for award in sorted(all_awards):
        award_col = []
        for awards_str in df['Awards']:
            if pd.isna(awards_str):
                award_col.append(0)
            else:
                awards = str(awards_str).split(',')
                found = False
                for a in awards:
                    a = a.strip()
                    if a.startswith(award):
                        # Extract number if present
                        if '-' in a:
                            try:
                                num = int(a.split('-')[1])
                                award_col.append(num)
                            except:
                                award_col.append(1)
                        else:
                            award_col.append(1)
                        found = True
                        break
                if not found:
                    award_col.append(0)
        
        df[award] = award_col
    
    # Drop the original Awards column and any Column_* columns that were awards
    cols_to_drop = ['Awards']
    for col in ['Column_25', 'Column_31']:
        if col in df.columns:
            cols_to_drop.append(col)
    df = df.drop(columns=cols_to_drop)
    
    return df


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


def scrape_stat_table(year: int, stat_type: str, internal_stat_type: str = None) -> Optional[pd.DataFrame]:
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
        # Fetch HTML first (we'll need it for player IDs and potentially for table parsing)
        html_content = fetch_html_with_fallback(url)
        
        if not html_content:
            print(f"Could not fetch HTML")
            return None
        
        # Parse HTML with BeautifulSoup to find the table
        soup = BeautifulSoup(html_content, 'html.parser')
        table = soup.find('table', {'id': stat_type})
        if not table:
            table = soup.find('table', class_='sortable')
        
        if not table:
            print(f"Could not find table")
            return None
        
        # Check if this stat type has multi-level headers
        has_multi_headers = stat_type in ['adj_shooting', 'play-by-play', 'shooting']
        
        if has_multi_headers:
            # Read with multi-level headers to get both levels
            dfs_multi = pd.read_html(str(table), header=[0, 1])
            if not dfs_multi:
                print(f"Could not parse table with multi-level headers")
                return None
            
            df_multi = dfs_multi[0]
            first_level = df_multi.columns.get_level_values(0).tolist()
            second_level = df_multi.columns.get_level_values(1).tolist()
            
            # Use the DataFrame with multi-level headers - we'll process the headers later
            df = df_multi.copy()
        else:
            # Single level headers - read normally
            dfs = pd.read_html(str(table))
            if not dfs:
                print(f"Could not parse table")
                return None
            df = dfs[0]
            first_level = None
            second_level = None
        
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
        
        # Process multi-level headers if we detected them earlier
        if first_level is not None and second_level is not None and stat_type in ['adj_shooting', 'play-by-play', 'shooting']:
            df = process_multi_level_headers(df, stat_type, first_level, second_level)
        
        # Clean column names
        df.columns = [clean_column_name(col) for col in df.columns]
        
        # Remove Rk column if it exists
        if 'Rk' in df.columns:
            df = df.drop(columns=['Rk'])
        
        # Handle traded players - keep only total row and replace TM with team abbreviations
        df = handle_traded_players(df)
        
        # Split awards column
        df = split_awards_column(df)
        
        # Normalize columns: remove redundant columns and rename stat columns
        # Use internal_stat_type if provided, otherwise use stat_type
        normalize_type = internal_stat_type if internal_stat_type else stat_type
        df = normalize_columns(df, normalize_type)
        
        return df
        
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data for {stat_type} in {year}: {e}")
        return None
    except Exception as e:
        print(f"Error parsing data for {stat_type} in {year}: {e}")
        return None


def process_multi_level_headers(df: pd.DataFrame, stat_type: str, first_level: list, second_level: list) -> pd.DataFrame:
    """
    Process multi-level headers for stat types that have them.
    
    Args:
        df: DataFrame with multi-level headers (MultiIndex columns)
        stat_type: Type of stats being processed
        first_level: First level of headers
        second_level: Second level of headers
    
    Returns:
        DataFrame with processed single-level headers
    """
    # If df has MultiIndex columns, flatten them first
    if isinstance(df.columns, pd.MultiIndex):
        # Get the column levels
        first_level = df.columns.get_level_values(0).tolist()
        second_level = df.columns.get_level_values(1).tolist()
    else:
        # Already flattened, but we have the levels from parameters
        first_level = first_level if first_level else [str(c) for c in df.columns]
        second_level = second_level if second_level else [str(c) for c in df.columns]
    
    new_columns = []
    
    # Process all columns
    for i in range(len(first_level)):
        first = str(first_level[i])
        second = str(second_level[i]) if i < len(second_level) else ''
        
        # Handle the first column (usually Player)
        if i == 0:
            new_columns.append('player_id')
            continue
        
        # Use second level as the base column name
        if (i >= len(second_level) or pd.isna(second_level[i])) or second in ['nan', '', 'Unnamed: 0_level_1', 'Unnamed: 0']:
            if first not in ['nan', ''] and not first.startswith('Unnamed'):
                new_col = first
            else:
                new_col = f'Column_{i}'
        else:
            new_col = second
        
        # Apply transformations based on stat type and first level header
        if stat_type == 'adj_shooting':
            # If first level contains "League-Adjusted" or "League Adjusted", add " LA" to the column name
            if 'League-Adjusted' in first or 'League Adjusted' in first:
                new_col = new_col + ' LA'
        
        elif stat_type == 'play-by-play':
            # If first row says "+/- Per 100 Poss", add " p100" to the end
            if '+/- Per 100 Poss' in first:
                new_col = new_col + ' p100'
            # If it says "Turnovers", add " TO" to the end
            elif 'Turnovers' in first:
                new_col = new_col + ' TO'
            # If it says "Fouls Committed", add " Foul" to the end
            elif 'Fouls Committed' in first:
                new_col = new_col + ' Foul'
            # If it says "Fouls Drawn", add " Drawn" to the end
            elif 'Fouls Drawn' in first:
                new_col = new_col + ' Drawn'
        
        elif stat_type == 'shooting':
            # If 1st row says "% of FGA by Distance", add " (% of FGA)" to the end
            if '% of FGA by Distance' in first:
                new_col = new_col + ' (% of FGA)'
            # If it says "FG% by Distance", add " (FG%)" to the end
            elif 'FG% by Distance' in first:
                new_col = new_col + ' (FG%)'
            # If it says "% of FG Ast'd", add " (% AST'd)" to the end
            elif '% of FG Ast\'d' in first or '% of FG Ast\'d' in first:
                new_col = new_col + ' (% AST\'d)'
            # If it says "Dunks", add "Dunks " to the start
            elif 'Dunks' in first:
                new_col = 'Dunks ' + new_col
            # If it says "Corner 3s", add " (Corner 3s)" to the end
            elif 'Corner 3s' in first:
                new_col = new_col + ' (Corner 3s)'
            # If it says "1/2 Court", add "Half Court " to the start
            elif '1/2 Court' in first:
                new_col = 'Half Court ' + new_col
        
        new_columns.append(new_col)
    
    # Make sure we have the right number of columns
    if len(new_columns) != len(df.columns):
        while len(new_columns) < len(df.columns):
            new_columns.append(f'Column_{len(new_columns)}')
        new_columns = new_columns[:len(df.columns)]
    
    # Assign new column names
    df.columns = new_columns
    return df


def save_to_csv(df: pd.DataFrame, year: int, stat_type: str) -> bool:
    """
    Save scraped data to CSV in year folder.
    Also adds year column and saves to combined all_years file.
    
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
        
        # Map stat_type to base filename (without year and extension)
        filename_map = {
            'totals': 'totals',
            'per_game': 'per_game',
            'per_36': 'per_36',
            'per_100_poss': 'per_100_poss',
            'advanced': 'advanced',
            'play-by-play': 'play_by_play',
            'shooting': 'shooting',
            'adj_shooting': 'adj_shooting'
        }
        
        base_filename = filename_map.get(stat_type, stat_type)
        filename = f"{base_filename}_{year}.csv"
        filepath = os.path.join(year_folder, filename)
        
        # Add year column
        df_with_year = df.copy()
        df_with_year.insert(1, 'year', year)
        
        # Save year-specific file
        df_with_year.to_csv(filepath, index=False)
        print(f"Saved {filepath} ({len(df_with_year)} rows)")
        
        # Also update/append to combined all_years file
        all_years_folder = os.path.join(data_folder, 'all_years')
        os.makedirs(all_years_folder, exist_ok=True)
        combined_file = os.path.join(all_years_folder, f"{base_filename}_all_years.csv")
        if os.path.exists(combined_file):
            # Read existing combined file
            combined_df = pd.read_csv(combined_file)
            # Remove rows for this year if they exist (in case of re-scraping)
            combined_df = combined_df[combined_df['year'] != year]
            # Append new data
            combined_df = pd.concat([combined_df, df_with_year], ignore_index=True)
        else:
            combined_df = df_with_year
        
        # Reorder columns: player_id, year first
        cols = ['player_id', 'year'] + [c for c in combined_df.columns if c not in ['player_id', 'year']]
        combined_df = combined_df[cols]
        
        # Save combined file
        combined_df.to_csv(combined_file, index=False)
        print(f"Updated {combined_file} ({len(combined_df)} total rows)")
        
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
    stat_types_list = list(STAT_TYPES.keys())
    for i, stat_type in enumerate(stat_types_list):
        print(f"Scraping {stat_type}...", end=" ")
        # Use the URL mapping for scraping, but keep the internal name for file operations
        url_stat_type = STAT_TYPES[stat_type]
        df = scrape_stat_table(year, url_stat_type, stat_type)
        
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

