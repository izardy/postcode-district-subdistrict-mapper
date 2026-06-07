import csv
from collections import defaultdict

# Read the CSV file and create postcodeMap
postcodeMap = defaultdict(list)

with open('data_source/malaysia-postcode-subdistrict-district-state.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        district = row['district']
        postcode = row['postcode']
        if postcode not in postcodeMap[district]:
            postcodeMap[district].append(postcode)

# Convert defaultdict to regular dict
postcodeMap = dict(postcodeMap)

# Display sample
print("Sample postcodeMap:")
for district in list(postcodeMap.keys())[:5]:
    print(f"'{district}': {postcodeMap[district][:5]}{'...' if len(postcodeMap[district]) > 5 else ''}")

# Optional: Save to Python file for import
with open('postcodeMap.py', 'w', encoding='utf-8') as f:
    f.write("postcodeMap = ")
    f.write(repr(postcodeMap))
