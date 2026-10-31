#!/usr/bin/env python3
"""A stand-in for llama-server, with no model: /health, /v1/models and chat completions with a fixed valid reply.

Used only to run the suites' scripts (run_demo.sh, run_cases.py, run_async_cases.py, verify_*.py, pack_run.py)
without a model. It answers every request with schema-valid JSON after DELAY seconds; nothing here reads a picture.
"""
import argparse, json, sys, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

parser = argparse.ArgumentParser()
parser.add_argument('--port', type=int, required=True)
parser.add_argument('--alias', default='stub')
parser.add_argument('--delay', type=float, default=2.0)
args, _ = parser.parse_known_args()

REPLIES = {
    'fluid_observation': {'observations': 'stub reply, no model', 'possible_interpretation': 'stub reply', 'checks': 'stub reply'},
    'fluid_describe': {'flow_description': 'stub reply, no model', 'fastest_flow_x_percent': 50, 'fastest_flow_y_percent': 50,
                       'lowest_pressure_x_percent': 50, 'lowest_pressure_y_percent': 50, 'uncertainties': 'stub reply'},
    'fluid_sequence': {'change_description': 'stub reply, no model', 'max_speed_trend': 'cannot_tell',
                       'min_pressure_trend': 'cannot_tell', 'fastest_flow_region': 'cannot_tell', 'uncertainties': 'stub reply'},
}


class Handler(BaseHTTPRequestHandler):
    def reply(self, payload):
        body = json.dumps(payload).encode()
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == '/health':
            self.reply({'status': 'ok'})
        elif self.path == '/v1/models':
            self.reply({'data': [{'id': args.alias}]})
        else:
            self.send_error(404)

    def do_POST(self):
        request = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))))
        time.sleep(args.delay)
        name = request['response_format']['json_schema']['name']
        self.reply({'choices': [{'index': 0, 'finish_reason': 'stop',
                                 'message': {'role': 'assistant', 'content': json.dumps(REPLIES[name])}}],
                    'usage': {'prompt_tokens': 1, 'completion_tokens': 1, 'total_tokens': 2},
                    'timings': {'cache_n': 0, 'prompt_n': 1, 'predicted_n': 1}})

    def log_message(self, *unused):
        pass


ThreadingHTTPServer(('127.0.0.1', args.port), Handler).serve_forever()
