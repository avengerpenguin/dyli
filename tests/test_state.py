import re
from functools import wraps
from typing import List
from uuid import uuid4

import pytest
import httpretty
import testypie
import requests
import hyperspace
from hyperspace.affordances import Page as ClientState
from hashlib import md5

import yarl
from hypothesis import settings, Verbosity, assume
from hypothesis.strategies import just, tuples, sampled_from, composite, \
    dictionaries, text, integers, lists
from rdflib import URIRef, RDF

import dyli

from hypothesis.stateful import RuleBasedStateMachine, Bundle, rule


@pytest.fixture(autouse=True, scope='module')
def mock_requests_to_use_flask_test_client(request):
    client = dyli.app.test_client()

    def get_callback(http_request, uri, headers):
        r = client.get(uri, headers=dict(http_request.headers))

        response_headers = {
            'content-type': r.headers['Content-Type'],
            'content-length': len(r.headers['Content-Length']),
        }
        response_headers.update(headers)

        return int(r.status_code), response_headers, r.data

    def put_callback(http_request, uri, headers):
        r = client.put(uri, data=http_request.body,
                       headers=dict(http_request.headers))

        response_headers = {
            'content-type': r.headers['Content-Type'],
            'content-length': len(r.headers['Content-Length']),
        }
        response_headers.update(headers)

        return int(r.status_code), response_headers, r.data

    httpretty.register_uri(httpretty.GET, re.compile('http://example.com/.*'),
                           body=get_callback)
    httpretty.register_uri(httpretty.PUT, re.compile('http://example.com/.*'),
                           body=put_callback)

    def callback(http_request, uri, headers):
        print('Mocking request: {}, {}, {}'.format(http_request, uri, headers))

        httpretty.disable()

        response = testypie.get_response(uri, http_request.headers)
        headers.update(
            {key.lower(): value for key, value in response['headers'].items()})

        httpretty.enable()

        return response['code'], headers, response['body']

    httpretty.register_uri(httpretty.GET, re.compile('.*'), body=callback)

    httpretty.enable()
    request.addfinalizer(httpretty.disable)
    request.addfinalizer(httpretty.reset)


TEST_DATA = {
    'Barolo': 'http://dbpedia.org/resource/Barolo',
    'Amarone': 'http://dbpedia.org/resource/Amarone',
}


def ensure_state_preserved(rule):
    def wrapper(self, *args, **kwargs):
        if self.get_state:
            before = self.get_state()
            result = rule(self, *args, **kwargs)
            after = self.get_state()
            assert before == after
            return result
        else:
            return rule(self, *args, **kwargs)
    wrapper.__name__ = rule.__name__
    return wrapper


class Client(RuleBasedStateMachine):

    clients = Bundle('clients')

    def __init__(self):
        super().__init__()
        self.get_state = None

    @rule(target=clients)
    def new_user(self):
        http = requests.Session()
        http.headers = {'Accept': 'text/turtle'}
        return hyperspace.jump('http://example.com/', http)

    @rule(target=clients, client=clients, query_index=sampled_from([0, 1]),
          values=lists(elements=text()),
          extraneous_data=dictionaries(keys=text(alphabet='abc'), values=text()))
    @ensure_state_preserved
    def random_query(self, client: ClientState, query_index: int, values: List[str], extraneous_data: dict) -> ClientState:
        assume(0 <= query_index < len(client.queries))

        data = {}

        query = client.queries[query_index]
        params = sorted(query.keys())
        for value, param in zip(values, params):
            data[param] = value

        # First interpolate advertised query params in a controlled way
        query.build(data)

        if extraneous_data:
            # Forcibly override the query string rather than rely on safe
            # URI template interpolation
            query.uri = str(yarl.URL(query.uri).update_query(extraneous_data))

        result = query.submit()
        return result


    @rule(target=clients, client=clients, entity_index=integers())
    @ensure_state_preserved
    def click_entity(self, client: ClientState, entity_index: int):
        assume(0 <= entity_index < len(client.entities))
        result = client.entities[entity_index].follow()
        return result


class DYLIClient(Client):

    clients = Client.clients
    labels = Bundle('labels')

    def __init__(self):
        super().__init__()
        self.get_state = lambda: md5(dyli.hf.server_state.serialize(format='nt')).hexdigest()

    @rule(target=labels, label_uri=sampled_from(sorted(TEST_DATA.items())))
    def item_added(self, label_uri):
        label, uri = label_uri
        dyli.create_thing(uri)
        return label

    @rule(target=clients, client=clients, label=labels)
    @ensure_state_preserved
    def search_item(self, client: ClientState, label: str):
        results = client.search(q=label)
        assert len(results.entities) == 1

        return results

    @rule(target=clients, client=clients, data=dictionaries(keys=just('q'), values=text()))
    @ensure_state_preserved
    def search_random(self, client: ClientState, data: dict):
        if 'q' in data:
            assume(data['q'] not in TEST_DATA)

        results = client.search(**data)

        assert len(results.entities) == 0

        return results

    @rule(target=clients, client=clients, username=text(), password=text())
    def register(self, client: ClientState, username: str, password: str):
        result = client.register(username=username, password=password)
        return result

    #@rule(target=clients, thing=clients)
    def like_thing(self, thing: ClientState):
        # Check we're actually on a 'thing' page
        assume((
            URIRef(thing.url),
            RDF.type,
            URIRef(self.vocab(thing, 'Thing')),
        ) in thing.data)

        result = thing.like()

        return result

    def vocab(self, client, term):
        return str(yarl.URL(client.url).with_path('/vocab').with_fragment(term))


TestClient = DYLIClient.TestCase
TestClient.settings = settings(verbosity=Verbosity.verbose, max_examples=10000)
