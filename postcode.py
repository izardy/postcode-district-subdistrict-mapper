import re
import json
import numpy as np
import chromadb
from langchain_ollama import OllamaLLM
from langchain.embeddings import HuggingFaceEmbeddings
from sentence_transformers import SentenceTransformer

def malaysia_postcode(address_input, chroma_path="../output/vectorstore", model_name="llama3.2:latest", embedding_model="../local_model/models--sentence-transformers--all-MiniLM-L6-v2/snapshots/c9745ed1d9f207416be6d2e6f8de32d1f16199bf", n_results=5, max_attempts=3):

    # Initialize the persistent ChromaDB client
    chroma_client = chromadb.PersistentClient(path=chroma_path)
    address = chroma_client.get_collection(name="base_address")

    # Initialize the LLM
    llm = OllamaLLM(model=model_name, base_url="http://localhost:11434")

    # Generate embeddings for the query

    #hfembed = HuggingFaceEmbeddings(model_name=embedding_model)
    #query_embedding = hfembed.embed_query(address_input.upper())
    
    hfembed = SentenceTransformer(embedding_model)
    query_embedding = hfembed.encode(address_input.upper()).tolist()

    # Perform the query using the generated embedding
    results = address.query(
        query_embeddings=[query_embedding],
        n_results=n_results
    )

    attempt = 0
    postcode = np.nan
    similarity_distance = np.nan  

    while attempt < max_attempts and postcode is np.nan:
        answer = llm.invoke(
            f"Given the following informations \
            {results['documents'][0][0]}; \
            {results['documents'][0][1]}; \
            {results['documents'][0][2]}; \
            {results['documents'][0][3]}; \
            {results['documents'][0][4]}; \
            for evaluation. \
            What is the possible postcode for {address_input} strictly based on the informations?\
            Answer 1 postcode value only in json format"
        )
        json_match = re.search(r'\{\s*"postcode"\s*:\s*"\d{5}"\s*\}', answer)
        if json_match:
            extracted_json = json_match.group(0)
            
            postcode = json.loads(extracted_json)["postcode"].strip()

            i = [0,1,2,3,4]

            for j in i:
                doc_postcode = results['documents'][0][j].split(",")[1].strip()
                if postcode == doc_postcode:
                    similarity_distance = results['distances'][0][j]
                    district = results['metadatas'][0][j]['district']
                    state = results['metadatas'][0][j]['state']
                else:
                    continue                    
            return [postcode,district,state,similarity_distance]
        else:
            print("No required JSON pattern found in answer. Retrying...")
            attempt += 1
    return [postcode,district,state,similarity_distance]