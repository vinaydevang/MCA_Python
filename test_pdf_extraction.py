import requests
import pdfplumber
import pandas as pd

# Test with one Challan URL from the existing Excel file
df = pd.read_excel("annual_filing_details.xlsx")

# Get the first row that has a Challan URL
if 'Challan URL' in df.columns:
    first_url = df[df['Challan URL'].notna()].iloc[0]['Challan URL']
    first_srn = df[df['Challan URL'].notna()].iloc[0]['SRN']
else:
    print("No Challan URL column found!")
    exit(1)

print(f"Testing with SRN: {first_srn}")
print(f"URL: {first_url}")

# Download PDF
try:
    response = requests.get(first_url, timeout=30)
    pdf_path = f"test_{first_srn}.pdf"
    
    with open(pdf_path, 'wb') as f:
        f.write(response.content)
    
    print(f"\nDownloaded PDF to {pdf_path}")
    
    # Extract text
    with pdfplumber.open(pdf_path) as pdf:
        text = ""
        for page in pdf.pages:
            text += page.extract_text() or ""
    
    print(f"\nExtracted text (first 500 chars):\n{text[:500]}\n")
    
    # Parse payment details
    lines = text.split('\n')
    
    date_of_filing = "N/A"
    amount_paid = "N/A"
    late_fee = "N/A"
    
    for line in lines:
        if 'Service Request Date' in line and ':' in line:
            parts = line.split(':', 1)
            if len(parts) == 2:
                date_of_filing = parts[1].strip()
                print(f"Found Date of Filing: {date_of_filing}")
        
        if 'Total' in line:
            parts = line.split()
            for part in reversed(parts):
                if part.replace('.', '', 1).replace(',', '').isdigit():
                    amount_paid = part
                    print(f"Found Amount Paid: {amount_paid}")
                    break
        
        if 'Additional' in line:
            parts = line.split()
            for part in reversed(parts):
                if part.replace('.', '', 1).replace(',', '').isdigit():
                    late_fee = part
                    print(f"Found Late Fee: {late_fee}")
                    break
    
    print(f"\nFinal Results:")
    print(f"Date of Filing: {date_of_filing}")
    print(f"Amount Paid: {amount_paid}")
    print(f"Late Fee: {late_fee}")
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
