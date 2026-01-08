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

2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

   Required packages:
   - `pandas` - for HTML table parsing and CSV export
   - `requests` - for HTTP requests
   - `beautifulsoup4` - for HTML parsing
   - `lxml` - for HTML parsing support

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

The script creates year-based folders and saves CSV files for each stat type:

```
NBA_Code/
├── scrape_nba_stats.py
├── requirements.txt
├── README.md
└── [year folders created at runtime]
    └── 2025/
        ├── totals.csv
        ├── per_game.csv
        ├── per_minute.csv
        ├── per_poss.csv
        ├── advanced.csv
        ├── play_by_play.csv
        ├── shooting.csv
        └── adj_shooting.csv
```

### CSV File Format

Each CSV file includes:
- **`player_id`** - Primary key column (first column) extracted from Basketball-Reference player URLs
- All standard stat columns for that stat type
- Player information (name, team, position, etc.)

The `player_id` column allows you to easily join tables across different stat types using this common identifier.

## Example

```bash
# Scrape 2025 NBA season stats
python scrape_nba_stats.py 2025
```

Output:
```
Scraping NBA 2025 season stats...
==================================================
Scraping totals... Saved 2025/totals.csv (219 rows)
Scraping per_game... Saved 2025/per_game.csv (219 rows)
Scraping per_minute... Saved 2025/per_minute.csv (219 rows)
Scraping per_poss... Saved 2025/per_poss.csv (219 rows)
Scraping advanced... Saved 2025/advanced.csv (219 rows)
Scraping play-by-play... Saved 2025/play_by_play.csv (219 rows)
Scraping shooting... Saved 2025/shooting.csv (219 rows)
Scraping adj_shooting... Saved 2025/adj_shooting.csv (219 rows)
==================================================
Completed: 8/8 stat types scraped successfully for 2025
```

## Year Format

The script accepts the **end year** of the NBA season. For example:
- `2025` refers to the 2024-25 NBA season
- `2024` refers to the 2023-24 NBA season

Valid years are between 1946 (first NBA season) and 2100.

## Notes

- The script includes a User-Agent header to avoid being blocked by Basketball-Reference
- Network requests have a 30-second timeout
- The script automatically creates year folders if they don't exist
- Player IDs are extracted from URLs in the format: `/players/[first_letter]/[player_id].html`

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
