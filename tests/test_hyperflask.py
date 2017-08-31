import pytest
from flask import Flask
from rdflib import Graph, URIRef, RDF

from dyli import Hyperflask


@pytest.fixture
def service():
    app = Flask('test')
    hf = Hyperflask(app)
    hf.initialise({
        '@id': 'http://example.com/foo',
        'http://xmlns.com/foaf/0.1/primaryTopic': {
            '@id': 'http://example.com/topic/Foo'
        }
    })

    @hf.resource('/custom')
    def custom():
        g = Graph()
        g.add((
            URIRef('http://example.com/Custom'),
            RDF.type,
            URIRef('http://example.com/CustomThing'),
        ))

    return hf


def test_fallback_get_gives_data_about_route(service):
    with service.app.test_request_context():
        from flask import request
        request.url = 'http://example.com/foo'
        response = service.fallback_get()

        assert response.status_code == 200

        g = Graph()
        g.parse(data=response.data, publicID='http://example.com/foo')

        assert len(g) == 1
        assert (
            URIRef('http://example.com/foo'),
            URIRef('http://xmlns.com/foaf/0.1/primaryTopic'),
            URIRef('http://example.com/topic/Foo'),
        ) in g


def test_fallback_get_gives_404_for_unknown_uris(service):
    with service.app.test_request_context():
        from flask import request
        request.url = 'http://example.com/notreal'
        response = service.fallback_get()

        assert response.status_code == 404


def test_fallback_get_honours_additional_data_from_custom_handler(service):
    with service.app.test_request_context():
        from flask import request
        request.url = 'http://example.com/custom'
        g1 = Graph()
        g1.add((
            URIRef('http://example.com/Custom'),
            RDF.type,
            URIRef('http://example.com/CustomThing'),
        ))
        response = service.fallback_get(graph=g1)

        assert response.status_code == 200

        g2 = Graph()
        g2.parse(data=response.data, publicID='http://example.com/foo')

        assert len(g2) == 1
        assert (
            URIRef('http://example.com/Custom'),
            RDF.type,
            URIRef('http://example.com/CustomThing'),
        ) in g2
