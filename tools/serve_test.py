"""Ephemeral browser QA server; never writes real learning state."""
from http.server import ThreadingHTTPServer
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'liuren-paipan'))
sys.path.insert(0, str(ROOT / 'tools'))
import webapp
import curriculum_v3

with tempfile.TemporaryDirectory() as folder:
    curriculum_v3.STATE = Path(folder) / '60-掌握度/_tutor_v3_state.json'
    server = ThreadingHTTPServer(('127.0.0.1', 0), webapp.TrainerHandler)
    print(f'QA_URL=http://127.0.0.1:{server.server_port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
