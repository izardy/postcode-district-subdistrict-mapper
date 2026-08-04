# Postcode District & Subdistrict Mapper (Malaysia)

This repository provides a data‑centric pipeline that maps Malaysian postcodes to districts, sub‑districts (mukim), and state information using several public data sources and a local semantic similarity stack.

---
## Table of contents
1. [Why?](#why)
2. [Installation](#installation)
3. [Data sources](#data-sources)
4. [Notebook workflow](#notebook-workflow)
5. [Building the vectorstore](#building-the-vectorstore)
6. [Adding a new address source](#adding-a-new-address-source)
7. [Usage (Python API)](#usage)
8. [Usage (CLI)](#cli-usage)
9. [Testing](#testing)
10. [Contributing](#contributing)
11. [License](#license)

---
## Why?
* Quick lookup of postcode ↔ district/mukim.
* Semantic matching using sentence‑transformer, chromadb vectorstore, and a local LLM.
* No external API keys – everything runs locally.

---
## Installation
```bash
# clone repository
git clone https://github.com/yourorg/postcode-district-subdistrict-mapper.git && cd postcode-district-subdistrict-mapper

# (Optional) create virtualenv — recommended for isolation
python3 -m venv .venv && source .venv/bin/activate

# install dependencies
pip install -r requirements.txt

# download Sentence‑Transformer model on first run
python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# start local Ollama and pull a lightweight model (e.g. llama3.2)
ollama serve &
ollama pull llama3.2:latest
```

---
## Data sources
| Source | Description | Link |
|--------|-------------|------|
| **Malaysia Postcode Directory** | Official postcode list | https://malaysiapostcode.com/download |
| **Mukim JSON** | Sub‑district data | https://mazfreelance.github.io/malaysia-jajahan-api/v1/states/mukim.json |
| **District JSON** | District data | https://mazfreelance.github.io/malaysia-jajahan-api/v1/states/district.json |
| **State JSON** | State data | https://mazfreelance.github.io/malaysia-jajahan-api/v1/states.json |
| **Geofabrik Malaysia OSM** | Spatial extents | https://download.geofabrik.de/asia/malaysia-singapore-brunei.html |
| **Yellow Pages Malaysia** | (Optional) Contact list | https://www.yellowpages.my/ |

---
## Notebook workflow
The notebooks in the `notebook/` folder walk you through the full pipeline:

1. **data‑prep.ipynb**
   * Loads the public JSON tables for states, districts, and mukim.
   * Cleans the data, merges the layers, and patches a handful of missing mukim entries.
   * Joins the postcode CSV (`malaysia‑postcode‑subdistrict‑district‑state.csv`) and standardises state abbreviations, producing a tidy table that is later used to build the vectorstore.

2. **embedding.ipynb**
   * Generates address strings from three source CSVs (`address_src_1`, `address_src_2`, `address_src_3`).
   * Loads each CSV with LangChain’s `CSVLoader` to create `Document` objects.
   * Enriches each `Document.metadata` with `state`, `district`, `postcode`, (and optionally `city`).
   * Uses the Ollama embedding model (`llama3.2`) along with a sentence‑transformer (`all‑MiniLM‑L6‑v2`) to embed the documents in batches.
   * Stores the embeddings in a persistent Chroma collection named `base_address` under `output/vectorstore`.

3. **llm‑rag.ipynb**
   * Demonstrates how to query the vectorstore with a semantic‑search prompt and have an Ollama LLM parse the top‑k results to extract the desired postcode.

4. **yellowpages_address_scrapper.ipynb** (optional)
   * Scrapes address data from YellowPages and injects them into the vectorstore.

---
## Building the vectorstore
If you already ran the notebooks, the vectorstore is ready at `output/vectorstore`. If not, run the `embedding.ipynb` notebook (or the equivalent Python script shown below) after preparing the source CSVs:
```python
import pandas as pd
from sentence_transformers import SentenceTransformer
import chromadb

# Load the cleaned dataframe from data‑prep
chor = pd.read_parquet('output/cleaned_locations.parquet')  # notebook output

# Encode addresses
model = SentenceTransformer('all-MiniLM-L6-v2')
vecs = model.encode(chor['locality'].tolist()).tolist()

# Persist to Chroma
client = chromadb.PersistentClient(path='output/vectorstore')
coll = client.create_collection(name='base_address')
coll.add(vectors=vecs, documents=chor['locality'].tolist(), metadatas=chor.to_dict('records'))
```

---
## Adding a new address source
You can extend the `base_address` collection with any additional address data without re‑building the index:

1. **Prepare the data** – create a list of `Document` objects that contain an `address` string and metadata (`postcode`, `district`, `state`, optional `city`).
   ```python
   import pandas as pd
   from langchain_core.documents import Document

   df = pd.read_csv('new_source.csv', dtype=str)
   docs = [
       Document(
           page_content=row['address'],
           metadata={
               'postcode': row['postcode'],
               'district': row['district'],
               'state'   : row['state'],
           },
       ) for _, row in df.iterrows()
   ]
   ```

2. **Append to the existing collection** – use the same embedding model the index was built with.
   ```python
   from langchain_chroma import Chroma
   from sentence_transformers import SentenceTransformer

   embed = SentenceTransformer('all-MiniLM-L6-v2')
   Chroma.from_documents(
       documents=docs,
       embedding=embed,
       persist_directory='output/vectorstore',
       collection_name='base_address',   # <- same collection name
   )
   ```

3. **Verify** – check the new document count.
   ```python
   client   = Chroma(persist_directory='output/vectorstore')
   count    = client.get_collection('base_address').count()
   print('Vectorstore now has', count, 'documents')
   ```

Because Chroma loads the collection on demand, this operation will simply add the new vectors to the existing index. No downtime or re‑embedding of the old data is required.

---
## Usage (Python API)
```python
from postcode import malaysia_postcode

result = malaysia_postcode(
    "GRN237447 LOT11499 SEKSYEN 1 (HSD16524,PT1560), TAMAN KASIH PUTERA,PEKAN BAHAU, JEMPOL, NEGERI SEMBILAN,PEKAN BAHAU,JEMPOL",
    chroma_path="output/vectorstore",
    model_name="llama3.2:latest"
)
print(result)  # -> ['GRN237447', 'Pekan Baharu', 'Negeri Sembilan', 0.23]
```
The function returns a list: `[postcode, district, state, similarity_distance]`.

---
## Usage (CLI)
```bash
python postcode.py --query "ADDRESS TEXT" --output output.csv
```
It writes a CSV of the top match, the extracted postcode, district, state and similarity score.

---
## Testing
Run `pytest -v` on the `tests/` folder (or any unit tests you create) to validate the lookup against the example addresses in `test_data.csv`.

---
## Contributing
* Fork, add improvements, or report issues.
* Follow the import‑style and typing conventions used in the notebooks.
* Keep tests up‑to‑date and document any changes in the README.

---
## License
MIT © 2026
