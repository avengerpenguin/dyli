import uuid
import requests
import yarl
from flask_login import LoginManager
from flask_security import UserMixin, SQLAlchemyUserDatastore, Security, \
    login_required, RoleMixin
from flask_sqlalchemy import SQLAlchemy
from rdflib import Graph, URIRef, Literal, RDF, RDFS
from flask import Flask, redirect, request
from .hyperflask import Hyperflask, Response, make_query


app = Flask('dyli')
app.config['DEBUG'] = True
app.config['SECRET_KEY'] = 'super-secret'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite://'
db = SQLAlchemy(app)
hf = Hyperflask(app)


hf.initialise({
    '@context': {
        '@base': 'http://example.com',
        'html': 'http://www.w3.org/1999/xhtml/vocab#',
        'hydra': 'http://www.w3.org/ns/hydra/core#',
    },
    '@id': '/',
    'html:search': {
        '@id': '/search',
        '@type': 'hydra:IriTemplate',
        'hydra:template': '/search{?q}',
        'html:search': {'@id': '/search'},
    },
})


class Role(db.Model, RoleMixin):
    id = db.Column(db.Integer(), primary_key=True)
    name = db.Column(db.String(80), unique=True)
    description = db.Column(db.String(255))


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True)
    password = db.Column(db.String(255))
    active = db.Column(db.Boolean())
    confirmed_at = db.Column(db.DateTime())


user_datastore = SQLAlchemyUserDatastore(db, User, Role)
security = Security(app, user_datastore)


@app.before_first_request
def setupDatabase():
    db.create_all()


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


# @hf.post('/<str:thing_id>/like')
# def like_thing(thing_id: str):
#     hf.get('/' + thing_id)


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


