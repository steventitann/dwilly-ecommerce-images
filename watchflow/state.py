import contextlib
import datetime
import json
import os
import sqlite3

def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

class State:
    def __init__(self, directory):
        directory.mkdir(parents=True, exist_ok=True)
        self.directory = directory
        self.db = sqlite3.connect(directory / 'state.sqlite')
        self.db.execute('CREATE TABLE IF NOT EXISTS jobs (key TEXT PRIMARY KEY, payload TEXT NOT NULL)')

    def get(self, key):
        row = self.db.execute('SELECT payload FROM jobs WHERE key=?', (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def close(self):
        self.db.close()

    def set(self, job_key, **payload):
        previous = self.get(job_key) or {}
        previous.update(payload, updated_at=now())
        self.db.execute('INSERT OR REPLACE INTO jobs VALUES (?,?)', (job_key, json.dumps(previous)))
        self.db.commit()
        self.log(job_key, 'state', status=previous.get('status'))
        return previous

    def log(self, key, event, **details):
        entry = {'at': now(), 'job': key, 'event': event, **details}
        with (self.directory / 'operations.jsonl').open('a', encoding='utf-8') as out:
            out.write(json.dumps(entry, ensure_ascii=False) + '\n')

    def resumable(self):
        return [json.loads(x[0]) for x in self.db.execute('SELECT payload FROM jobs')
                if json.loads(x[0]).get('status') in ('PUBLISHING', 'PUBLISHED', 'MOVE_REVIEW', 'MOVE_ERROR')]

@contextlib.contextmanager
def lock(directory):
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / 'runner.lock'
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    os.write(descriptor, str(os.getpid()).encode())
    try:
        yield
    finally:
        os.close(descriptor)
        path.unlink()
