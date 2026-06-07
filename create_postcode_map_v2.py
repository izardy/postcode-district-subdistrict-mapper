import csv
from collections import defaultdict

# Read the CSV and create nested postcodeMap: state -> district -> [postcodes]
postcodeMap = defaultdict(lambda: defaultdict(list))

with open('data_source/malaysia-postcode-subdistrict-district-state.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        state = row['state']
        district = row['district'].upper()  # Convert district to uppercase
        postcode = row['postcode']
        
        # Add postcode if not already in the list (deduplicate)
        if postcode not in postcodeMap[state][district]:
            postcodeMap[state][district].append(postcode)

# Convert nested defaultdicts to regular dicts
postcodeMap = {state: dict(districts) for state, districts in postcodeMap.items()}

# Display sample
print("Sample postcodeMap structure:")
for state in list(postcodeMap.keys())[:3]:
    print(f"\n'{state}':")
    for district in list(postcodeMap[state].keys())[:3]:
        print(f"  '{district}': {postcodeMap[state][district][:3]}{'...' if len(postcodeMap[state][district]) > 3 else ''}")

# Check duplicate districts
print("\n\nDistricts with same name in multiple states:")
all_districts = defaultdict(set)
for state, districts in postcodeMap.items():
    for district in districts.keys():
        all_districts[district].add(state)

duplicates = {d: states for d, states in all_districts.items() if len(states) > 1}
for district, states in sorted(duplicates.items()):
    print(f"  {district}: {states}")

# Save to file
with open('data_source/postcodeMap.txt', 'w', encoding='utf-8') as f:
    f.write("postcodeMap = ")
    f.write(repr(postcodeMap))

print(f"\n\nTotal states: {len(postcodeMap)}")
print(f"Total unique districts: {sum(len(districts) for districts in postcodeMap.values())}")
print(f"File saved to: data_source/postcodeMap.txt")
