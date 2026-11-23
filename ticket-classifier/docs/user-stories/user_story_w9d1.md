# USER STORY w09d1: Embeddings and Similarity

Connect ScoutBot to a knowledge base, so that triage tickets use 

- use the knowledge base in the exercise folder
- embed chunks with the fastembed library
- store embeddings in a database. pick one of the following:
  - DuckDB (pip install)
  - MongoDB + pymongo (via docker)
  - PostgreSQL + psycopg-binary (via docker)

- implement similarity search in KnowledgeBase.search(query, k)
- connect the similarity search to ScoutBot
- try out different chunking options (size, overlap)
- check what data types the database can use (vector/BLOB/other)

## Far-reaching goals

- check what other text search tools the database offers
- how can you avoid embedding your corpus every time the triage process is started?
- write automated tests
