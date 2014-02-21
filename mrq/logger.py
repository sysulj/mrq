
from collections import defaultdict
import datetime


class LoggerInterface(object):
  """ This object acts as a logger from python's logging module. """

  def __init__(self, handler, **kwargs):
    self._handler = handler
    self.kwargs = kwargs

  @property
  def handler(self):
    if self._handler:
      return self._handler

    # Import here to avoid import loop
    from .worker import get_current_worker
    return get_current_worker().log_handler

  def info(self, *args):
    self.handler.log("info", *args, **self.kwargs)

  def warning(self, *args):
    self.handler.log("warning", *args, **self.kwargs)

  def error(self, *args):
    self.handler.log("error", *args, **self.kwargs)

  def debug(self, *args):
    self.handler.log("debug", *args, **self.kwargs)


# Global log object, usable from all tasks
log = LoggerInterface(None, job="current")


class LogHandler(object):
  """ Job/Worker-aware log handler.

      We used the standard logging module before but it suffers from memory leaks
      when creating lots of logger objects.
  """

  def __init__(self, collection=None, quiet=False):
    self.reset()
    self.set_collection(collection)
    self.quiet = quiet

    # Import here to avoid import loop
    from .worker import get_current_job
    self.get_current_job = get_current_job

  def get_logger(self, worker=None, job=None):
    return LoggerInterface(self, worker=worker, job=job)

  def set_collection(self, collection=None):
    self.collection = collection

  def reset(self):
    self.buffer = {
      "workers": defaultdict(list),
      "jobs": defaultdict(list)
    }

  def log(self, level, *args, **kwargs):

    worker = kwargs.get("worker")
    job = kwargs.get("job")

    formatted = "%s [%s] %s" % (datetime.datetime.utcnow(), level.upper(), " ".join([unicode(x) for x in args]))

    if not self.quiet:
      print formatted

    if worker is not None:
      self.buffer["workers"][worker].append(formatted)
    else:
      if job == "current":
        job_object = self.get_current_job()
        if job_object:
          self.buffer["jobs"][job_object.id].append(formatted)
      else:
        self.buffer["jobs"][job].append(formatted)

  def flush(self):

    # We may log some stuff before we are even connected to Mongo!
    if self.collection is None:
      return

    inserts = [{
      "worker": k,
      "logs": "\n".join(v) + "\n"
    } for k, v in self.buffer["workers"].iteritems()] + [{
      "job": k,
      "logs": "\n".join(v) + "\n"
    } for k, v in self.buffer["jobs"].iteritems()]

    self.reset()

    if len(inserts) > 0:
      self.collection.insert(inserts, w=0)
