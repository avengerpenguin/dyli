import uuid
import requests
import yarl
from rdflib import Graph, URIRef, Literal, RDF, RDFS
from flask import Flask, redirect, request
from .hyperflask import Hyperflask, Response, make_query


app = Flask('dyli')
app.debug = True
hf = Hyperflask(app)


hf.initialise({
    '@context': {
        '@base': 'http://example.com',
        'html': 'http://www.w3.org/1999/xhtml/vocab#',
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

    print(hf.server_state.serialize(format='turtle').decode('utf-8'))
    r = hf.server_state.query('''
    PREFIX schema: <http://schema.org/>
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX dyli: <http://example.com/vocab#>

    CONSTRUCT { ?x ?p ?y . ?y ?p2 ?z . }
    WHERE {
        ?x a dyli:Thing .
        ?x ?p ?y .
        ?x rdfs:label ?name
        OPTIONAL {
          ?y ?p2 ?z .
        }
    }
    ''', initBindings={'name': Literal(q, lang='en')})

    g = Graph()
    for r_ in r:
        print('Found: ' + str(r_))
        g.add(r_)

    return g


def create_thing(url: str):
    if URIRef(url) not in hf.server_state.subjects():
        new_url = URIRef(str(yarl.URL('http://example.com').with_path('/' + str(uuid.uuid4()))))

        r = requests.get(url, headers={'Accept': 'text/turtle'})

        g = Graph()
        g.parse(format='turtle', data=r.content, publicID='http://example.com')

        for p, o in g.predicate_objects(URIRef(url)):
            if p == RDFS.label:
                g.add((new_url, p, o))

        g.add((new_url, RDF.type, URIRef(str(yarl.URL('http://example.com').with_path('/vocab').with_fragment('Thing')))))
        g.add((new_url, URIRef('http://www.w3.org/1999/xhtml/vocab#search'), URIRef(str(yarl.URL('http://example.com').with_path('/search')))))

        hf.add_data(g)
