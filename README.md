# NBA Player Stats Scraper

A Python script to scrape NBA player statistics from [Basketball-Reference.com](https://www.basketball-reference.com) for any specified season year. The script extracts player statistics across 8 different stat categories and saves them as CSV files organized by year, with player IDs included for easy database joining.

## Features

- **Multiple Stat Types**: Scrapes 8 different stat categories:
  - Totals
  - Per Game
  - Per 36 Minutes
  - Per 100 Possessions
  - Advanced
  - Play-by-Play
  - Shooting
  - Adjusted Shooting

- **Player ID Extraction**: Automatically extracts player IDs from Basketball-Reference URLs, which serve as primary keys for joining tables in your database

- **Year-Based Organization**: Saves CSV files in year-based folders (e.g., `2025/totals.csv`)

- **Flexible Input**: Accept years via command-line arguments or interactive mode

- **Error Handling**: Gracefully handles network errors, invalid years, and missing data

## Installation

1. **Clone the repository** (if you haven't already):
   ```bash
   git clone git@github.com:zjtippetts/NBA_Database.git
   cd NBA_Database/NBA_Code
   ```

2. **Create and activate a virtual environment** (recommended):
   ```bash
   # Create virtual environment
   python -m venv venv
   
   # Activate virtual environment
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

   Required packages:
   - `pandas` - for HTML table parsing and CSV export
   - `requests` - for HTTP requests
   - `beautifulsoup4` - for HTML parsing
   - `lxml` - for HTML parsing support
   - `html5lib` - for HTML parsing support

## Usage

### Command-Line Arguments

Scrape a single year:
```bash
python scrape_nba_stats.py 2025
```

Scrape multiple years:
```bash
python scrape_nba_stats.py 2024 2025 2023
```

### Interactive Mode

Run without arguments to enter interactive mode:
```bash
python scrape_nba_stats.py
```

Then enter the year(s) when prompted:
```
Enter year(s) to scrape (e.g., 2025 or 2024 2025):
2025
```

## Output Structure

The script creates two types of output files:

1. **Year-specific files**: Individual CSV files for each year in `data/YYYY/` folders
2. **Combined files**: All years combined into single files in `data/all_years/` folder

```
NBA_Code/
├── scrape_nba_stats.py
├── requirements.txt
├── README.md
├── venv/                    # Virtual environment (not tracked in git)
└── data/                    # Data folder (created at runtime)
    ├── all_years/           # Combined files (all years together)
    │   ├── totals_all_years.csv
    │   ├── per_game_all_years.csv
    │   ├── per_36_all_years.csv
    │   ├── per_100_poss_all_years.csv
    │   ├── advanced_all_years.csv
    │   ├── play_by_play_all_years.csv
    │   ├── shooting_all_years.csv
    │   └── adj_shooting_all_years.csv
    └── [year folders created at runtime]
        └── 2025/
            ├── totals_2025.csv
            ├── per_game_2025.csv
            ├── per_36_2025.csv
            ├── per_100_poss_2025.csv
            ├── advanced_2025.csv
            ├── play_by_play_2025.csv
            ├── shooting_2025.csv
            └── adj_shooting_2025.csv
```

### CSV File Format

Each CSV file includes:
- **`player_id`** - Primary key column (first column) extracted from Basketball-Reference player URLs
- **`year`** - Season year column (second column) for easy filtering and analysis
- All standard stat columns for that stat type (with cleaned column names)
- Player information (name, team, position, etc.)
- **Award columns** - Separate columns for each award (MVP, DPOY, AS, NBA1, NBA2, NBA3, etc.)

**Column Name Cleaning:**
- Special characters removed (parentheses, spaces, etc.)
- Columns starting with numbers get underscore prefix (e.g., `2P` → `_2P`, `3P` → `_3P`)
- Percentages converted to `_pct` suffix (e.g., `FG%` → `FG_pct`)
- Range columns use `range_` prefix (e.g., `0-3` → `range_0_3`)

**Awards:**
- Awards with rankings (e.g., `MVP-1`) store the number as the value
- Awards without rankings (e.g., `AS`) are `1` if present, `0` if not

The `player_id` and `year` columns allow you to easily join tables across different stat types and years using these common identifiers.

### Re-scraping

The script handles re-scraping gracefully:
- **Year-specific files**: Overwrites existing files with updated data
- **Combined files**: Automatically removes old data for that year and adds new data (prevents duplicates)
- Safe to run multiple times during a season to get updated statistics

## Example

```bash
# Scrape 2025 NBA season stats
python scrape_nba_stats.py 2025
```

Output:
```
Scraping NBA 2025 season stats...
==================================================
Scraping totals... Saved data/2025/totals_2025.csv (735 rows)
Updated data/all_years/totals_all_years.csv (1470 total rows)
Scraping per_game... Saved data/2025/per_game_2025.csv (735 rows)
Updated data/all_years/per_game_all_years.csv (1470 total rows)
...
==================================================
Completed: 8/8 stat types scraped successfully for 2025
```

## Year Format

The script accepts the **end year** of the NBA season. For example:
- `2025` refers to the 2024-25 NBA season
- `2024` refers to the 2023-24 NBA season

Valid years are between 1946 (first NBA season) and 2100.

## Notes

- **Rate Limiting**: The script includes a 3-second delay between requests to comply with Sports Reference's 20 requests/minute limit
- **Bot Protection**: Uses browser-like headers and fallback mechanisms (requests → urllib) to bypass bot protection
- **Network requests** have a 30-second timeout
- The script automatically creates year folders and `all_years` folder if they don't exist
- Player IDs are extracted from URLs in the format: `/players/[first_letter]/[player_id].html`
- **Automatic Updates**: Combined `all_years` files are automatically updated when you scrape, making it easy to maintain a master dataset across all years
- **Data Cleaning**: Column names are automatically cleaned and standardized for easier database integration

## Troubleshooting

**Error: "Could not find table"**
- The year might not exist or the page structure may have changed
- Check that the year is valid (1946-2100)

**Error: "Error fetching data"**
- Check your internet connection
- Basketball-Reference might be temporarily unavailable
- Try again after a few moments

**Empty or incomplete CSV files**
- Some stat types might not be available for certain years
- Check the Basketball-Reference website directly to verify data availability

## License

This project is for personal/educational use. Please respect Basketball-Reference.com's terms of service and robots.txt when scraping data.

## Contributing

Feel free to submit issues or pull requests if you find bugs or have suggestions for improvements.
