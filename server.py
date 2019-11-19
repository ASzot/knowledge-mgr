from flask import Flask, Response, redirect, url_for, request, session, abort
from flask.ext.login import LoginManager, UserMixin, login_required, login_user, logout_user
from flask.ext.cors import CORS, cross_origin
import os.path as osp
from flask import jsonify
import os
from flask_httpauth import HTTPBasicAuth
import json


# Directory you wish to load your content from.
BASE_CONTENT_DIR = 'content'

auth = HTTPBasicAuth()

app = Flask(__name__)

def load_user_data():
    auth_users = {}
    user_ids = {}
    app_secret = None
    with open('settings.json', 'r') as f:
        jf = json.load(f)
        for u in jf['users']:
            auth_users[u['name']] = u['passwd']
            user_ids[u['id']] = u['name']
    return auth_users, user_ids, jf['app_secret']

auth_users, user_ids, app_secret = load_user_data()

# config
app.config.update(
        DEBUG = False,
        SECRET_KEY = app_secret
        )

# Allowed endpoints for the frontend to access.
cors = CORS(app, resources={
    r"/all_papers": {"origins": "*"},
    r"/login": {"origins": "*"},
    r"/papers/*": {"origins": "*"}

    })
app.config['CORS_HEADERS'] = 'Content-Type'

# flask-login
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"

reverse_user_ids = {v: k for k,v in user_ids.items()}

# silly user model
class User(UserMixin):
    def __init__(self, id):
        username = user_ids[int(id)]
        password = auth_users[username]
        self.id = id
        self.name = username
        self.password = password

    def __repr__(self):
        return "%d/%s/%s" % (self.id, self.name, self.password)


# some protected url
@app.route('/')
def home():
    return Response("Hello World!")

def get_basic_info(fname):
    with open(fname) as f:
        lines = f.readlines()

    total = '\n'.join(lines)
    parts = total.split('|')
    def clean(x):
        return x.replace('\n', '')
    title = clean(parts[0])
    tags = clean(parts[1])
    date = clean(parts[2])
    desc = clean(parts[3])
    return title, tags, date, desc

@app.route('/all_papers', methods=['GET', 'OPTIONS'])
@cross_origin(origin='*',headers=['Content-Type','Authorization'])
@auth.login_required
def get_all_papers():
    papers = []
    for r, d, f in os.walk(BASE_CONTENT_DIR):
        for result in f:
            result_name = result.split('.')[0]
            base_path = '/'.join(r.split('/')[1:])

            title, tags, date, desc = get_basic_info(osp.join(r, result))
            path = osp.join(base_path, result_name)
            papers.append({
                'title': title,
                'tags': tags,
                'date': date,
                'desc': desc,
                'path': path
                })

    papers = sorted(papers, key=lambda x: x['date'], reverse=True)

    response = jsonify(papers=papers)
    #response.headers.add('Access-Control-Allow-Origin', '*')
    return response



@auth.verify_password
def verify_password(username, password):
    print('Checking password', username, password)
    return username in auth_users and auth_users[username] == password



@app.route('/papers/<path:filename>')
@cross_origin(origin='*',headers=['Content-Type','Authorization'])
@auth.login_required
def get_paper(filename):
    print('Fetching ' + filename)
    paper_name = '/'.join(request.path.split('/')[2:])
    open_path = osp.join(BASE_CONTENT_DIR, paper_name + '.txt')

    with open(open_path) as f:
        lines = f.readlines()

    def convert_reg(x):
        return x.strip()

    def convert_multi(x):
        x = x.strip()
        if x.startswith('<li>'):
            return x
        return '<p>' + x.replace("\n\n\n\n", '</p><p>') + '</p>'

    all_content = '\n'.join(lines)
    title, tags, date, desc, url, who, problem, motivation, cont, method, exps, personal= all_content.split('|')

    return jsonify(
            title=convert_reg(title),
            tags=convert_reg(tags),
            date=convert_reg(date),
            url=convert_reg(url),
            who=convert_multi(who),
            problem=convert_multi(problem),
            motivation=convert_multi(motivation),
            cont=convert_multi(cont),
            method=convert_multi(method),
            exps=convert_multi(exps),
            personal=convert_multi(personal))


# somewhere to login
@app.route('/login', methods=['POST', 'OPTIONS'])
@cross_origin(origin='*',headers=['Content-Type','Authorization'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username in auth_users and auth_users[username] == password:
            id = reverse_user_ids[username]
            user = User(id)
            login_user(user)
            return Response('ok')
        else:
            return Response('login failed')
    else:
        return Response('invalid method')



@app.route("/logout")
def logout():
    logout_user()
    return Response('<p>Logged out</p>')


# handle login failed
@app.errorhandler(401)
def page_not_found(e):
    return Response('login failed')


# callback to reload the user object
@login_manager.user_loader
def load_user(userid):
    return User(userid)


if __name__ == "__main__":
    # SSL certificate information. This is needed for responding to requests
    # over HTTPS.
    context = ('/etc/letsencrypt/live/www.andrewszot.com/cert.pem', '/etc/letsencrypt/live/www.andrewszot.com/privkey.pem', )
    app.run(host='0.0.0.0', port=3001, ssl_context=context)
