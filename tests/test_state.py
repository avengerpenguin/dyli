import re
from uuid import uuid4

import pytest
import httpretty
import testypie
import requests
import hyperspace
from hashlib import md5

import yarl
from hypothesis import settings, Verbosity, assume
from hypothesis.strategies import just, tuples, sampled_from, composite, \
    dictionaries, text, integers
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


class Client(RuleBasedStateMachine):

    clients = Bundle('clients')


class DYLIClient(Client):

    clients = Client.clients
    labels = Bundle('labels')

    @rule(target=clients)
    def new_user(self):
        http = requests.Session()
        http.headers = {'Accept': 'text/turtle'}
        return hyperspace.jump('http://example.com/', http)

    @rule(target=labels, label_uri=sampled_from(sorted(TEST_DATA.items())))
    def item_added(self, label_uri):
        label, uri = label_uri
        dyli.create_thing(uri)
        return label

    @rule(target=clients, client=clients, label=labels)
    def search_item(self, client: hyperspace.affordances.Page, label: str):
        state_before = md5(dyli.hf.server_state.serialize(format='nt')).hexdigest()

        results = client.search(q=label)
        assert len(results.entities) == 1

        state_after = md5(dyli.hf.server_state.serialize(format='nt')).hexdigest()
        assert state_before == state_after

        return results

    @rule(target=clients, client=clients, data=dictionaries(keys=just('q'), values=text()))
    def search_random(self, client: hyperspace.affordances.Page, data: dict):
        state_before = md5(dyli.hf.server_state.serialize(format='nt')).hexdigest()

        if 'q' in data:
            assume(data['q'] not in TEST_DATA)

        results = client.search(**data)

        assert len(results.entities) == 0

        state_after = md5(dyli.hf.server_state.serialize(format='nt')).hexdigest()
        assert state_before == state_after
        return results

    @rule(target=clients, client=clients)
    def click_entity(self, client: hyperspace.affordances.Page):
        assume(len(client.entities) > 0)
        state_before = md5(dyli.hf.server_state.serialize(format='nt')).hexdigest()

        result = client.entities[0].follow()

        state_after = md5(dyli.hf.server_state.serialize(format='nt')).hexdigest()
        assert state_before == state_after

        return result

    #@rule(target=clients, thing=clients)
    def like_thing(self, thing: hyperspace.affordances.Page):
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
TestClient.settings = settings(verbosity=Verbosity.verbose)
