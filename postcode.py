def malaysia_postcode(address_input, chroma_path="../output/vectorstore", model_name="llama3.2:latest", embedding_model="../local_model/models--sentence-transformers--all-MiniLM-L6-v2/snapshots/c9745ed1d9f207416be6d2e6f8de32d1f16199bf", n_results=5, max_attempts=3):
    import re
    import json
    import chromadb
    from langchain_ollama import OllamaLLM
    from langchain.embeddings import HuggingFaceEmbeddings

    # Initialize the persistent ChromaDB client
    chroma_client = chromadb.PersistentClient(path=chroma_path)
    address = chroma_client.get_collection(name="base_address")

    # Initialize the LLM
    llm = OllamaLLM(model=model_name, base_url="http://localhost:11434")

    # Generate embeddings for the query
    hfembed = HuggingFaceEmbeddings(model_name=embedding_model)
    query_embedding = hfembed.embed_query(address_input.upper())

    # Perform the query using the generated embedding
    results = address.query(
        query_embeddings=[query_embedding],
        n_results=n_results
    )

    attempt = 0
    postcode = None

    while attempt < max_attempts and postcode is None:
        answer = llm.invoke(
            f"Given the following informations {results['documents'][0][0]} with similarity score {results['distances'][0][0]} ; \
            {results['documents'][0][1]} with similarity score {results['distances'][0][1]} ; \
            {results['documents'][0][2]} with similarity score {results['distances'][0][2]} ; \
            {results['documents'][0][3]} with similarity score {results['distances'][0][3]} ; \
            {results['documents'][0][4]} with similarity score {results['distances'][0][4]} for evaluation. \
            What is the possible postcode and the similarity_score for {address_input} strictly based on the informations?\
            Answer 1 postcode and score value only in json format"
        )
        json_match = re.search(r"\{[\s\S]*?\}", answer)
        if json_match:
            extracted_json = json_match.group(0)
            try:
                postcode = json.loads(extracted_json)["postcode"]
                similarity_distance = json.loads(extracted_json)["similarity_score"]
                return [postcode,similarity_distance]
            except Exception:
                postcode = None
        else:
            print("No JSON found in answer. Retrying...")
            attempt += 1
    return None