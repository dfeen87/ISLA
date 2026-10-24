"""Cancellable asynchronous filename resolution before the existing decoder."""
from __future__ import annotations

import multiprocessing as mp
import os
from pathlib import Path
import signal

from isla.file_search import choose_match,find_audio


def _search(query, connection):
    try:
        if os.name == 'posix':
            os.setsid()
        matches,info = find_audio(query)
        path = choose_match(query,matches,info)
        connection.send(('found',str(path)))
    except Exception as exc:
        connection.send(('error',str(exc)))
    finally:
        connection.close()


class SearchPreparation:
    def __init__(self, query, factory):
        self.path = Path(query)
        self.factory = factory
        self.delegate = None
        self.done = self.closed = False
        self.state = f'Searching this computer for {query!r}…'
        context = mp.get_context('spawn')
        self.connection,child = context.Pipe(duplex=False)
        self.process = context.Process(target=_search,args=(query,child),daemon=True)
        try:
            self.process.start()
        except BaseException:
            self.connection.close()
            raise
        finally:
            child.close()

    @property
    def directory(self):
        return self.delegate.directory

    def poll(self):
        if self.done:
            return None
        if self.delegate is None:
            if not self.connection.poll():
                if not self.process.is_alive():
                    raise ValueError('Local audio search stopped unexpectedly. Use a full path or Open Audio File.')
                return None
            try:
                kind,value = self.connection.recv()
            except EOFError as exc:
                raise ValueError('Local audio search stopped unexpectedly.') from exc
            if kind == 'error':
                raise ValueError(value)
            self.delegate = self.factory(value)
            self.path = self.delegate.path
        result = self.delegate.poll()
        self.state = f'Found {self.path}. {self.delegate.state}'
        self.done = self.delegate.done
        return result

    def close(self):
        if self.closed:
            return
        pid = self.process.pid
        if self.process.is_alive():
            self.process.terminate()
        self.process.join()
        if os.name == 'posix' and pid is not None:
            try:
                os.killpg(pid,signal.SIGKILL)
            except ProcessLookupError:
                pass
        self.process.close()
        self.connection.close()
        if self.delegate is not None:
            self.delegate.close()
        self.closed = True
