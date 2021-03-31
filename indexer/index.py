import argparse
import os
import json
import time
from elasticsearch import Elasticsearch
from elasticsearch.helpers import streaming_bulk

DEFAULT_CHUNK_SIZE = 10000

TAG_POSITION = 9
FIELD_POSITIONS = {
    'blog_id': 0,
    'follower_count': 3,
    'name': 4,
    'title': 5,
    'created_timestamp': 7,
}

TAG_FIELD_POSITIONS = {
    'tag_name': 1,
    'tf_idf': 2,
    'like_count': 3,
    'reblog_count': 4,
    'tag_count': 5,
    'post_count': 6,
    'global_rank_score': 7,
    'tag_score': 8,
}

def cast_with_default(val, to_type, default=None):
    try:
        return to_type(val)
    except (ValueError, TypeError):
        return default


class Tag:
    def __init__(self, data):
        self.tag_name = cast_with_default(data['tag_name'], str, '')
        self.tf_idf = cast_with_default(data['tf_idf'], float, 0.0)
        self.like_count = cast_with_default(data['like_count'], int, 0)
        self.reblog_count = cast_with_default(data['reblog_count'], int, 0)
        self.tag_count = cast_with_default(data['tag_count'], int, 0)
        self.post_count = cast_with_default(data['post_count'], int, 0)
        self.global_rank_score = cast_with_default(data['global_rank_score'], float, 0.0)
        self.tag_score = cast_with_default(data['tag_score'], float, 0.0)

    def _serialize(self):
        return {
            'tag_name': self.tag_name,
            'tf_idf': self.tf_idf,
            'like_count': self.like_count,
            'reblog_count': self.reblog_count,
            'tag_count': self.tag_count,
            'post_count': self.post_count,
            'global_rank_score': self.global_rank_score,
            'tag_score': self.tag_score,
        }

class Blog:
    def __init__(self, data):
        self.blog_id = data['blog_id']
        self.follower_count = cast_with_default(data['follower_count'], int, 0)
        self.name = cast_with_default(data['name'], str, '')
        self.title = cast_with_default(data['title'], str, '')
        self.created_timestamp = cast_with_default(data['created_timestamp'], int, 0)
        self.tags = [Tag(tag) for tag in data.get('tags', [])]

    def _serialize(self):
        return {
            'blog_id': self.blog_id,
            'follower_count': self.follower_count,
            'name': self.name,
            'title': self.title,
            'created_timestamp': self.created_timestamp,
            'tags': [tag._serialize() for tag in self.tags]
        }


class Indexer:
    def __init__(self, args):
        self._es = Elasticsearch(os.getenv('ELASTICSEARCH_HOST'))
        self._mappings = self.get_mappings()
        self._index_name = '{}_{}'.format(args.alias_name, int(time.time()))
        self._alias_name = args.alias_name
        self.chunk_size = args.chunk_size

    def add_alias(self):
        self._es.indices.put_alias(index=self._index_name, name=self._alias_name)

    def refresh_index(self):
        self._es.indices.refresh(index=self._index_name)

    def get_mappings(self):
        with open('mappings.json', 'r') as mappings_file:
            return json.loads(mappings_file.read())

    def get_config(self):
        return {
            'limit': self._limit
        }

    def create_index(self):
        return self._es.indices.create(self._index_name, body=self._mappings)

    def parse_tags(self, unformatted):
        tags = unformatted.split('|')
        formatted = []
        for item in tags:
            tag_fields = item.split(',')
            formatted.append({
                name: tag_fields[pos].strip()
                for (name, pos) in TAG_FIELD_POSITIONS.items()
            })
        return formatted

    def parse_fields(self, line):
        fields = line.split('\t')
        data = {
            name: fields[pos].strip()
            for (name, pos) in FIELD_POSITIONS.items()
        }

        if len(fields) > TAG_POSITION:
            data['tags'] = self.parse_tags(fields[TAG_POSITION])

        return Blog(data)._serialize()

    def load_data(self):
        with open('./raw_data/blog-info', 'r') as datafile, open('./data-errors', 'w') as errorfile:
            for line in datafile:
                try:
                    fields = self.parse_fields(line)
                    yield fields
                except:
                    errorfile.write('{}'.format(line))
                    continue

    def run(self):
        # Create index with mappings first
        print('Creating index {}'.format(self._index_name))
        self.create_index()

        print('Indexing data')
        indexed = 0
        for ok, action in streaming_bulk(client=self._es, index=self._index_name, actions=self.load_data(), chunk_size=self.chunk_size):
            if ok == True:
                indexed += len(action)

        print('Refreshing index')
        self.refresh_index()

        print('Adding alias \'{}\''.format(self._alias_name))
        self.add_alias()

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Index raw data')
    parser.add_argument('--alias_name', type=str, help='What to name the index', default='blogs', required=False)
    parser.add_argument('--chunk_size', type=int, help='Chunk size to be sent to ES via bulk operations', default=DEFAULT_CHUNK_SIZE, required=False)
    args = parser.parse_args()

    indexer = Indexer(args)
    indexer.run()