import re
import pytest
import httpretty
import testypie
import requests
import hyperspace

import dyli


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

        r = client.put(uri, data=http_request.body, headers=dict(http_request.headers))

        response_headers = {
            'content-type': r.headers['Content-Type'],
            'content-length': len(r.headers['Content-Length']),
        }
        response_headers.update(headers)

        return int(r.status_code), response_headers, r.data

    httpretty.register_uri(httpretty.GET, re.compile('http://example.com/.*'), body=get_callback)
    httpretty.register_uri(httpretty.PUT, re.compile('http://example.com/.*'), body=put_callback)

    def callback(http_request, uri, headers):
        print('Mocking request: {}, {}, {}'.format(http_request, uri, headers))

        httpretty.disable()

        response = testypie.get_response(uri, http_request.headers)
        headers.update({key.lower(): value for key, value in response['headers'].items()})

        httpretty.enable()

        return response['code'], headers, response['body']

    httpretty.register_uri(httpretty.GET, re.compile('.*'), body=callback)

    httpretty.enable()
    request.addfinalizer(httpretty.disable)
    request.addfinalizer(httpretty.reset)


@pytest.fixture
def home():
    http = requests.Session()
    http.headers = {'Accept': 'text/turtle'}
    return hyperspace.jump('http://example.com/', http)


def test_item(home):
    dyli.create_thing('http://dbpedia.org/resource/Barolo')
    assert 'Barolo' in set(home.search(q='Barolo')[0].rdfs_label)


def test_search_no_param(home):
    assert home.search(q='').response.status_code == 200
