# Indexer

This portion of the project is meant to create the Elasticsearch index needed for the search API using the mappings found in `mappings.json`, validate records from the raw data provided for this project, and insert them using the `streaming_bulk` utility function from the `elasticsearch-py` package.

## To Run

*Important note - I've chosen to add the raw data to the gitignore of this repository. To run this tool, the raw data must first be downloaded and placed in a file called `./raw_data/blog-info`.

Once following the instructions to start the Docker network (found in the parent directory's README), follow these steps in a terminal:
- `docker exec -it indexer bash`
- `python index.py --alias_name blogs --chunk_size 10000`

The script will first create an index named `<alias_name>_<unix_timestamp>`, then load the data in from the `blog-info` file. Once finished, this script will refresh the index, and then apply an alias named `<alias_name>` (the default is `blogs`).

Any records from the `blog-info` raw data file that cannot be validated will be placed in a file called `data-errors`. My strategy, for now, is to omit records from the index if there are any issues fetching data from the expected positions in the tab-delimited array of fields, or if the fetched fields are not able to be cast into the expected types. I may revisit this later in the project to try and 'infer' fields based on context, etc., if the need arises.
