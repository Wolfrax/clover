#!/usr/bin/env python

from flask import Flask, render_template, send_from_directory
import os


__author__ = 'Wolfrax'

app = Flask(__name__)


class ReverseProxied(object):
    def __init__(self, app, script_name):
        self.app = app
        self.script_name = script_name

    def __call__(self, environ, start_response):
        environ['SCRIPT_NAME'] = self.script_name
        return self.app(environ, start_response)


app.wsgi_app = ReverseProxied(app.wsgi_app, script_name='/clover')


@app.route("/", methods=['GET'])
def index():
    return render_template('voronoi.html')


@app.route('/files/<filename>', methods=['GET'])
def download(filename):
    return send_from_directory(directory=os.path.join(app.root_path, 'static'), path=filename)


if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=True)
