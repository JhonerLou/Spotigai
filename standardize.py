import pandas as pd
import os
import numpy as np # Import numpy for NaN comparison

# --- Configuration ---
INPUT_CSV_PATH = 'full_song_list.csv'
OUTPUT_CSV_PATH = 'standardized_song_list.csv' # Name of the cleaned output file

# Define potential column names AND the desired standardized names
# Order within the list indicates priority (first is preferred)
COLUMN_MAPPING = {
    'track_id': ['track_id', 'id'],
    'track_name': ['track_name', 'name'],
    'artist_name': ['artist_name', 'track_artist', 'artists'],
    'year': ['year'],
    'Mood': ['Mood', 'Predicted_Mood']
}

# Define the *absolutely* essential columns required after attempting to fill/merge.
# If these are still missing after merging, the row will be dropped.
CRITICAL_COLS_STANDARDIZED = ['track_id', 'track_name', 'artist_name', 'Mood']


def find_col(df_cols_set, options):
    """Helper to find the first existing column from a list of options."""
    for col in options:
        if col in df_cols_set:
            return col
    return None

def clean_column(series):
    """Applies standard cleaning: string, strip, replace common NAs."""
    # Convert to string, strip whitespace, replace various NA representations
    # Using regex=False for exact string replacements is safer here
    cleaned = series.astype(str).str.strip().replace(['nan', 'NaN', 'None', '', '.'], np.nan, regex=False)
    return cleaned

def standardize_data(input_path, output_path):
    """
    Loads, cleans, merges alternative columns using defined priorities,
    drops rows missing critical data, ensures standard column names, and saves.
    """
    if not os.path.exists(input_path):
        print(f"❌ ERROR: Input file not found at '{input_path}'.")
        return

    try:
        df = pd.read_csv(input_path, low_memory=False)
        print(f"Loaded {len(df)} initial rows from '{input_path}'.")
        df_cols_set = set(df.columns)

        # --- 1. Identify Existing Columns for Each Standard Field ---
        found_columns_options = {}
        missing_critical_flag = False
        print("\n--- Identifying Available Columns ---")
        for standard_name, options in COLUMN_MAPPING.items():
            existing_options = [col for col in options if col in df_cols_set]
            if existing_options:
                found_columns_options[standard_name] = existing_options
                print(f"Found options for '{standard_name}': {existing_options}")
            elif standard_name in CRITICAL_COLS_STANDARDIZED:
                print(f"❌ ERROR: Could not find ANY suitable column for critical field '{standard_name}' from options: {options}")
                missing_critical_flag = True
            else:
                 print(f"Optional field '{standard_name}' not found (options: {options}).")

        if missing_critical_flag:
            print("Processing stopped due to missing critical columns.")
            return

        # --- 2. Clean All Identified Columns ---
        print("\n--- Cleaning Identified Columns ---")
        all_found_cols = [col for options in found_columns_options.values() for col in options]
        year_col_original_name = None # Track the original name used for year

        for col in set(all_found_cols): # Use set to avoid cleaning the same column multiple times
            print(f"Cleaning column '{col}'...")
            # Special handling for year
            if col in found_columns_options.get('year', []):
                 year_col_original_name = col
                 df[col] = pd.to_numeric(df[col], errors='coerce')
                 if col in df.columns: # Check if column still exists (it should)
                     valid_year_count = df[col].notna().sum()
                     print(f"   -> Found {valid_year_count} valid numeric years in '{col}' after cleaning.")
            else:
                 df[col] = clean_column(df[col])


        # --- 3. Coalesce/Merge Data into Standard Columns ---
        print("\n--- Merging Data into Standard Columns ---")
        df_merged = pd.DataFrame(index=df.index) # Create new DF with same index as original

        for standard_name, options in COLUMN_MAPPING.items():
            if standard_name in found_columns_options:
                existing_options_for_std = found_columns_options[standard_name]
                primary_col = existing_options_for_std[0]
                print(f"Creating standard column '{standard_name}' using '{primary_col}' as primary source.")
                df_merged[standard_name] = df[primary_col].copy() # Start with the highest priority column

                # Fill missing values using lower priority columns if they exist
                if len(existing_options_for_std) > 1:
                    for alt_col in existing_options_for_std[1:]:
                         # Only fill where the standard column is currently NA
                         fill_mask = df_merged[standard_name].isna()
                         values_to_fill = df.loc[fill_mask, alt_col] # Get values from alt col only where needed
                         if not values_to_fill.empty:
                            print(f"   -> Filling {fill_mask.sum()} missing values in '{standard_name}' using '{alt_col}'...")
                            df_merged.loc[fill_mask, standard_name] = values_to_fill
                         else:
                            print(f"   -> No values to fill from '{alt_col}' for '{standard_name}'.")

        # Specific check for 'year' column type after merging
        if 'year' in df_merged.columns:
             df_merged['year'] = pd.to_numeric(df_merged['year'], errors='coerce') # Ensure float for NA support

        print(f"\nColumns available after merging: {list(df_merged.columns)}")
        print(f"DataFrame shape after merging columns: {df_merged.shape}")


        # --- 4. Drop Rows with Missing Critical Data AFTER Merging ---
        print(f"\n--- Dropping Rows with Missing Critical Data ---")
        initial_rows = len(df_merged)
        # Use the CRITICAL_COLS_STANDARDIZED list directly as column names now exist
        # Ensure these critical columns actually exist in the merged df before dropping
        actual_critical_cols = [col for col in CRITICAL_COLS_STANDARDIZED if col in df_merged.columns]
        print(f"Checking for missing values in critical standardized columns: {actual_critical_cols}")

        df_merged.dropna(subset=actual_critical_cols, inplace=True)

        rows_after_na = len(df_merged)
        print(f"Removed {initial_rows - rows_after_na} rows with missing critical data.")
        print(f"DataFrame shape after dropping NA: {df_merged.shape}")

        if df_merged.empty:
            print("❌ ERROR: No valid data remaining after cleaning, merging, and removing missing values.")
            return

        # --- 5. Final Column Selection & Type Conversion ---
        # Select the desired standard columns plus 'year' if it exists
        final_columns_list = CRITICAL_COLS_STANDARDIZED[:] # Start with a copy
        if 'year' in df_merged.columns:
            if 'year' not in final_columns_list: # Add year if not already critical
                final_columns_list.append('year')
        else:
            print("   -> 'year' column is missing from df_merged before final selection.")

        # Ensure only existing columns are selected
        final_columns_list = [col for col in final_columns_list if col in df_merged.columns]

        print(f"\nFinal columns selected for output: {final_columns_list}")

        df_final = df_merged[final_columns_list].copy()

        # Optional: Convert year to nullable integer type
        if 'year' in df_final.columns:
            # Check if dtype is float and if there are non-finite values before conversion
            if pd.api.types.is_float_dtype(df_final['year']) and not df_final['year'].map(lambda x: pd.isna(x) or np.isfinite(x)).all():
                print("Warning: Non-finite float values found in year column before Int64 conversion. Setting them to NA.")
                df_final['year'] = df_final['year'].replace([np.inf, -np.inf], pd.NA)

            try:
                # Convert to pandas nullable integer type
                df_final['year'] = df_final['year'].astype('Int64')
                print("   -> Converted 'year' column to nullable Int64 type.")
            except Exception as e:
                 print(f"   -> Warning: Could not convert 'year' to Int64. Keeping as float. Error: {e}")


        # --- 6. Save the standardized data ---
        df_final.to_csv(output_path, index=False)
        print(f"\n✅ Successfully saved {len(df_final)} standardized rows to '{output_path}'.")
        print(f"   Final Columns: {list(df_final.columns)}")

        # Optional: Display unique moods from the final data
        if 'Mood' in df_final.columns:
            final_unique_moods = list(df_final['Mood'].unique())
            print(f"   Unique mood labels in final output: {final_unique_moods}")


    except Exception as e:
        print(f"❌ ERROR: An unexpected error occurred during processing.")
        import traceback; traceback.print_exc()

# --- Run the standardization ---
if __name__ == "__main__":
    standardize_data(INPUT_CSV_PATH, OUTPUT_CSV_PATH)

