### Postcode District & Subdistrict Mapper (Malaysia)

This project maps Malaysian postcodes to their corresponding districts, sub-districts (mukim), and locations. It integrates multiple public datasets and supports semantic search using local sentence-transformer models. Ideal for civic tech, geospatial analysis, and regional data normalization.
<br>
**Features**

- Map postcodes to mukim, district, state, and location
- Semantic matching using sentence-transformers, chromadb vectorstore and llama3.2 model.
<br>

**Repository Structure**

| Folder/File                  | Description |
|-----------------------------|-------------|
| data_source/              | Raw JSON and CSV data sources |
| local_model/models-sentence-transformers/ | Pretrained transformer models for semantic matching |
| notebook/                 | Jupyter notebooks for exploration and prototyping |
| output/                   | Generated outputs (CSV, logs, etc.) |
| output/vectorstore                   | Vectorized address via Chromadb |
| postcode.py               | Core mapping logic and utilities |
| test_data.csv             | Sample input for testing postcode resolution |
| .gitignore, .gitattributes | Git configuration files |
| README.md                 | Project documentation |
<br>

**Data Sources**

- [x] Malaysia Postcode Directory (https://malaysiapostcode.com/download)
- [x] Mukim JSON (https://mazfreelance.github.io/malaysia-jajahan-api/v1/states/mukim.json)  
- [x] District JSON (https://mazfreelance.github.io/malaysia-jajahan-api/v1/states/district.json)  
- [x] State JSON (https://mazfreelance.github.io/malaysia-jajahan-api/v1/states.json)  
- [x] Geofabrik Malaysia OSM (https://download.geofabrik.de/asia/malaysia-singapore-brunei.html)  
- [ ] Yellow Pages Malaysia (https://www.yellowpages.my/)
<br>
**Usage Example**
```
import sys
sys.path.append()  # or the actual path to the script (postcode.py)
from postcode import malaysia_postcode

print(malaysia_postcode("GRN237447 LOT11499 SEKSYEN 1 (HSD16524,PT1560), TAMAN KASIH PUTERA,PEKAN BAHAU, JEMPOL, NEGERI SEMBILAN,PEKAN BAHAU,JEMPOL"))
```
