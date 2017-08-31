import uuid
import requests
from rdflib import Graph, URIRef, Literal, RDF
from flask import Flask, redirect, request
from .hyperflask import Hyperflask, Response, make_query


import logging
logging.getLogger(__name__).addHandler(logging.NullHandler())


app = Flask('dyli')
app.debug = True
hf = Hyperflask(app)


hf.initialise({
    '@context': {
        '@base': 'http://example.com',
        'html': 'https://www.w3.org/1999/xhtml/vocab#',
        'hydra': 'http://www.w3.org/ns/hydra/core#',
    },
    '@id': '/',
    'html:search': {
        'html:search': {'@id': '/search'},
        '@id': '/search',
        "@type": "hydra:IriTemplate",
        "hydra:template": "/search{?q}",
    },
})


@hf.resource('/search')
def search():
    q = request.args.get('q')

    r = hf.server_state.query('''
    PREFIX schema: <http://schema.org/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX dyli: </vocab#>

    CONSTRUCT { ?x ?p ?y . }
    WHERE {
        ?x a dyli:Thing .
        ?x ?p ?y .
        ?x rdfs:label ?name
    }
    ''', initBindings={'name': Literal(q, lang='en')})

    g = Graph()
    for r_ in r:
        g.add(r_)

    return g


def create_thing(url: str):
    if URIRef(url) not in hf.server_state.subjects():
        new_url = URIRef('/' + str(uuid.uuid4()))

        r = requests.get(url, headers={'Accept': 'text/turtle'})

        g = Graph()
        g.parse(format='turtle', data=r.content, publicID=url)

        for p, o in g.predicate_objects(URIRef(url)):
            g.add((new_url, p, o))

        g.add((new_url, RDF.type, URIRef('/vocab#Thing')))

        hf.add_data(g)
