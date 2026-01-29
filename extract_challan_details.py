"""
Standalone script to download Challan PDFs and extract payment details.
This script reads an Excel file with Challan URLs and extracts:
- Date of Filing
- Amount Paid  
- Late Fee

Run this after check_annual_filing.py has extracted the basic table.
"""

import os
import requests
import pdfplumber
import pandas as pd
from tqdm import tqdm  # For progress bar

# Configuration
INPUT_FILE = "annual_filing_with_urls.xlsx"  # File with Challan URLs
OUTPUT_FILE = "annual_filing_details_complete.xlsx"
PDF_DIR = "challan_pdfs"

def download_and_extract_challan(url, srn):
    """Download a Challan PDF and extract payment details."""
    
    date_of_filing = "N/A"
    amount_paid = "N/A"
    late_fee = "N/A"
    
    try:
        # Download PDF
        pdf_path = f"{PDF_DIR}/{srn}.pdf"
        response = requests.get(url, timeout=30)
        
        with open(pdf_path, 'wb') as f:
            f.write(response.content)
        
        # Extract text from PDF
        with pdfplumber.open(pdf_path) as pdf:
            text = ""
            for page in pdf.pages:
                text += page.extract_text() or ""
        
        # Parse text to find payment details
        lines = text.split('\n')
        
        for line in lines:
            # Find Service Request Date
            if 'Service Request Date' in line and ':' in line:
                parts = line.split(':', 1)
                if len(parts) == 2:
                    date_of_filing = parts[1].strip()
            
            # Find Total amount
            if 'Total' in line:
                parts = line.split()
                for part in reversed(parts):
                    # Check if it's a number (allows . and ,)
                    if part.replace('.', '', 1).replace(',', '').isdigit():
                        amount_paid = part
                        break
            
            # Find Additional (Late Fee)
            if 'Additional' in line:
                parts = line.split()
                for part in reversed(parts):
                    if part.replace('.', '', 1).replace(',', '').isdigit():
                        late_fee = part
                        break
        
        # If no Additional fee found, set to 0.00
        if late_fee == "N/A":
            late_fee = "0.00"
            
    except Exception as e:
        print(f"Error processing {srn}: {e}")
    
    return date_of_filing, amount_paid, late_fee


def main():
    print(f"Reading input file: {INPUT_FILE}")
    
    # Read the Excel file
    df = pd.read_excel(INPUT_FILE)
    
    print(f"Found {len(df)} rows")
    print(f"Columns: {list(df.columns)}")
    
    # Check if Challan URL column exists
    if 'Challan URL' not in df.columns:
        print("\nERROR: 'Challan URL' column not found!")
        print("This script needs the Challan URLs from the initial scraping.")
        print("Please run check_annual_filing.py first to get the basic data.")
        return
    
    # Create PDF directory
    if not os.path.exists(PDF_DIR):
        os.makedirs(PDF_DIR)
        print(f"Created directory: {PDF_DIR}")
    
    # Initialize payment detail columns if they don't exist
    if 'Date of Filing' not in df.columns:
        df['Date of Filing'] = "N/A"
    if 'Amount Paid' not in df.columns:
        df['Amount Paid'] = "N/A"
    if 'Late Fee' not in df.columns:
        df['Late Fee'] = "N/A"
    
    # Process each Challan
    print(f"\nProcessing {len(df)} Challan PDFs...")
    
    for idx, row in tqdm(df.iterrows(), total=len(df), desc="Downloading PDFs"):
        challan_url = row.get('Challan URL', 'N/A')
        srn = row['SRN']
        
        if pd.notna(challan_url) and str(challan_url).startswith('http'):
            date, amount, fee = download_and_extract_challan(challan_url, srn)
            
            df.at[idx, 'Date of Filing'] = date
            df.at[idx, 'Amount Paid'] = amount
            df.at[idx, 'Late Fee'] = fee
            
            print(f"  {srn}: Date={date}, Amount={amount}, Fee={fee}")
        else:
            print(f"  {srn}: No valid URL, skipping")
    
    # Save the complete data
    # Remove Challan URL column from final output
    output_columns = ['SRN', 'Form Name', 'Event Date', 'Date of Filing', 'Amount Paid', 'Late Fee']
    df_output = df[output_columns]
    
    df_output.to_excel(OUTPUT_FILE, index=False)
    print(f"\nSaved complete data to: {OUTPUT_FILE}")
    print(f"Total rows: {len(df_output)}")
    
    # Show summary
    filled_count = len(df_output[df_output['Date of Filing'] != 'N/A'])
    print(f"Rows with payment details: {filled_count}/{len(df_output)}")


if __name__ == "__main__":
    main()
