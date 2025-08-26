# Postcode District & Subdistrict Mapper (Malaysia)

This project maps Malaysian postcodes to their corresponding districts, sub-districts (mukim), and locations. It integrates multiple public datasets and supports semantic search using local sentence-transformer models. Ideal for civic tech, geospatial analysis, and regional data normalization.

---

## Features

- Map postcodes to mukim, district, state, and location
- Semantic matching using sentence-transformers, chromadb vectorstore and llama3.2 model.

---

## Repository Structure

| Folder/File                  | Description |
|-----------------------------|-------------|
| `data_source/`              | Raw JSON and CSV data sources |
| `local_model/models-sentence-transformers/` | Pretrained transformer models for semantic matching |
| `notebook/`                 | Jupyter notebooks for exploration and prototyping |
| `output/`                   | Generated outputs (CSV, logs, etc.) |
| `output/vectorstore`                   | Vectorized address via Chromadb |
| `postcode.py`               | Core mapping logic and utilities |
| `test_data.csv`             | Sample input for testing postcode resolution |
| `.gitignore`, `.gitattributes` | Git configuration files |
| `README.md`                 | Project documentation |

---

## 🔗 Data Sources

- [Malaysia Postcode Directory](https://malaysiapostcode.com/download)
- [Mukim JSON](https://mazfreelance.github.io/malaysia-jajahan-api/v1/states/mukim.json)  
- [District JSON](https://mazfreelance.github.io/malaysia-jajahan-api/v1/states/district.json)  
- [State JSON](https://mazfreelance.github.io/malaysia-jajahan-api/v1/states.json)  
- [Geofabrik Malaysia OSM](https://download.geofabrik.de/asia/malaysia-singapore-brunei.html)  
- [Yellow Pages Malaysia](https://www.yellowpages.my/)

---

## 🚀 Getting Started

### Prerequisites

- Python 3.8+
- `pandas`, `sentence-transformers`, `scikit-learn`
- Optional: Jupyter Notebook for exploration

### Installation

```bash
git clone https://github.com/izardy/postcode-district-subdistrict-mapper.git
cd postcode-district-subdistrict-mapper
pip install -r requirements.txt
