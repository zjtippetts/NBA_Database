#!/usr/bin/env python3
"""
NBA Stats Streamlit App
A simple web app to explore NBA player statistics.
"""

import streamlit as st
import pandas as pd
import os
import glob

# Page configuration
st.set_page_config(
    page_title="NBA Player Stats Explorer",
    page_icon="🏀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Title
st.title("🏀 NBA Player Stats Explorer")
st.markdown("Explore NBA player statistics across multiple seasons and stat categories.")

# Load data function with caching
@st.cache_data
def load_stat_file(stat_type):
    """Load a stat file from all_years folder."""
    filepath = f"data/all_years/{stat_type}_all_years.csv"
    if os.path.exists(filepath):
        return pd.read_csv(filepath)
    return None

# Sidebar for navigation
st.sidebar.header("Navigation")
page = st.sidebar.selectbox(
    "Choose a page",
    ["Player Search", "Stat Explorer", "Year Comparison"]
)

# Get available stat types
stat_types = {
    "Totals": "totals",
    "Per Game": "per_game",
    "Per 36 Minutes": "per_minute",
    "Per 100 Possessions": "per_poss",
    "Advanced": "advanced",
    "Play-by-Play": "play_by_play",
    "Shooting": "shooting",
    "Adjusted Shooting": "adj_shooting"
}

# Player Search Page
if page == "Player Search":
    st.header("Player Search")
    
    # Load totals data for player list
    df_totals = load_stat_file("totals")
    
    if df_totals is not None:
        # Get unique players
        players = sorted(df_totals['Player'].unique())
        
        # Player search
        selected_player = st.selectbox(
            "Select a player",
            players,
            index=0
        )
        
        if selected_player:
            # Filter data for selected player
            player_data = df_totals[df_totals['Player'] == selected_player].copy()
            
            if not player_data.empty:
                # Display player info
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Seasons", len(player_data))
                
                with col2:
                    latest_year = player_data['year'].max()
                    st.metric("Latest Season", int(latest_year))
                
                with col3:
                    total_points = player_data['PTS'].sum()
                    st.metric("Career Points", f"{int(total_points):,}")
                
                with col4:
                    player_id = player_data['player_id'].iloc[0]
                    st.metric("Player ID", player_id)
                
                # Year selector
                years = sorted(player_data['year'].unique(), reverse=True)
                selected_year = st.selectbox(
                    "Select a season",
                    years,
                    index=0
                )
                
                # Display stats for selected year
                year_data = player_data[player_data['year'] == selected_year].iloc[0]
                
                st.subheader(f"{selected_player} - {int(selected_year)} Season")
                
                # Key stats
                col1, col2, col3, col4, col5 = st.columns(5)
                
                with col1:
                    st.metric("Games", int(year_data['G']) if pd.notna(year_data['G']) else 0)
                with col2:
                    st.metric("Points/Game", f"{year_data['PTS']:.1f}" if pd.notna(year_data['PTS']) else "N/A")
                with col3:
                    st.metric("Rebounds/Game", f"{year_data['TRB']:.1f}" if pd.notna(year_data['TRB']) else "N/A")
                with col4:
                    st.metric("Assists/Game", f"{year_data['AST']:.1f}" if pd.notna(year_data['AST']) else "N/A")
                with col5:
                    st.metric("FG%", f"{year_data['FG_pct']:.3f}" if pd.notna(year_data['FG_pct']) else "N/A")
                
                # Career stats table
                st.subheader("Career Stats (All Seasons)")
                display_cols = ['year', 'Team', 'Pos', 'G', 'GS', 'MP', 'PTS', 'TRB', 'AST', 'STL', 'BLK', 'FG_pct', '_3P_pct', 'FT_pct']
                available_cols = [col for col in display_cols if col in player_data.columns]
                st.dataframe(
                    player_data[available_cols].sort_values('year', ascending=False),
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.warning("No data found for this player.")
    else:
        st.error("Could not load data. Please make sure you have run the scraper first.")

# Stat Explorer Page
elif page == "Stat Explorer":
    st.header("Stat Explorer")
    
    # Stat type selector
    selected_stat_type = st.sidebar.selectbox(
        "Select stat type",
        list(stat_types.keys())
    )
    
    # Load selected stat file
    df = load_stat_file(stat_types[selected_stat_type])
    
    if df is not None:
        # Year filter
        years = sorted(df['year'].unique(), reverse=True)
        selected_years = st.sidebar.multiselect(
            "Filter by year(s)",
            years,
            default=years[:5] if len(years) >= 5 else years
        )
        
        if selected_years:
            df_filtered = df[df['year'].isin(selected_years)].copy()
        else:
            df_filtered = df.copy()
        
        # Player filter
        players = sorted(df_filtered['Player'].unique())
        selected_players = st.sidebar.multiselect(
            "Filter by player(s)",
            players,
            default=[]
        )
        
        if selected_players:
            df_filtered = df_filtered[df_filtered['Player'].isin(selected_players)]
        
        # Display data
        st.subheader(f"{selected_stat_type} Statistics")
        st.dataframe(
            df_filtered,
            use_container_width=True,
            hide_index=True
        )
        
        # Download button
        csv = df_filtered.to_csv(index=False)
        st.download_button(
            label="Download filtered data as CSV",
            data=csv,
            file_name=f"{stat_types[selected_stat_type]}_filtered.csv",
            mime="text/csv"
        )
    else:
        st.error(f"Could not load {selected_stat_type} data. Please make sure you have run the scraper first.")

# Year Comparison Page
elif page == "Year Comparison":
    st.header("Year Comparison")
    
    # Load totals data
    df = load_stat_file("totals")
    
    if df is not None:
        # Year selector
        years = sorted(df['year'].unique(), reverse=True)
        year1 = st.selectbox("Select first year", years, index=0)
        year2 = st.selectbox("Select second year", years, index=1 if len(years) > 1 else 0)
        
        if year1 != year2:
            df_year1 = df[df['year'] == year1].copy()
            df_year2 = df[df['year'] == year2].copy()
            
            # Top players comparison
            st.subheader(f"Top 10 Scorers Comparison")
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"**{int(year1)} Season**")
                top_year1 = df_year1.nlargest(10, 'PTS')[['Player', 'Team', 'PTS', 'G']]
                st.dataframe(top_year1, use_container_width=True, hide_index=True)
            
            with col2:
                st.write(f"**{int(year2)} Season**")
                top_year2 = df_year2.nlargest(10, 'PTS')[['Player', 'Team', 'PTS', 'G']]
                st.dataframe(top_year2, use_container_width=True, hide_index=True)
            
            # League averages
            st.subheader("League Averages")
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric(
                    f"{int(year1)} Avg PPG",
                    f"{df_year1['PTS'].mean():.1f}",
                    delta=f"{df_year1['PTS'].mean() - df_year2['PTS'].mean():.1f}"
                )
            with col2:
                st.metric(
                    f"{int(year1)} Avg RPG",
                    f"{df_year1['TRB'].mean():.1f}",
                    delta=f"{df_year1['TRB'].mean() - df_year2['TRB'].mean():.1f}"
                )
            with col3:
                st.metric(
                    f"{int(year1)} Avg APG",
                    f"{df_year1['AST'].mean():.1f}",
                    delta=f"{df_year1['AST'].mean() - df_year2['AST'].mean():.1f}"
                )
        else:
            st.warning("Please select two different years to compare.")
    else:
        st.error("Could not load data. Please make sure you have run the scraper first.")

# Footer
st.sidebar.markdown("---")
st.sidebar.markdown("**Data Source:** Basketball-Reference.com")
st.sidebar.markdown("**Last Updated:** Check data files for latest scrape date")
