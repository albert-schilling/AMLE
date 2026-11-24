# User Story W09D2: Retrieval

Use the RAG results to formulate an answer to a triage ticket:

- insert a retrieval step into the graph
- cite the sources in the reply
- set a confidence threshold (minimum cosim)
- do not use retrieval results under the threshold

## Consider using *one* class

class Reply(BaseModel)

class RetrievalResult(BaseModel)
