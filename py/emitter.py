#!/usr/bin/env python

from flask import Flask
from flask import jsonify
import json


__author__ = 'Wolfrax'

app = Flask(__name__)


class CloverError(Exception):
    status_code = 500  # Server internal error

    def __init__(self, message, status_code=None, payload=None):
        Exception.__init__(self)
        self.message = message
        if status_code is not None:
            self.status_code = status_code
        self.payload = payload

    def to_dict(self):
        rv = dict(self.payload or ())
        rv['message'] = self.message
        return rv


@app.errorhandler(CloverError)
def handle_err(error):
    response = jsonify(error.to_dict())
    response.status_code = error.status_code
    return response


@app.route("/clover_data")
def get_data():
    name = "/var/local/clover_weather.js"  # Hardcoded filename
    try:
        with open(name, 'r') as json_file:
            return json.dumps(json.load(json_file))
    except (FileNotFoundError, ValueError) as msg:
        raise CloverError('JSON decode error: {}'.format(msg))


if __name__ == "__main__":
    app.run(host='0.0.0.0', debug=True)
