import time
import logging
import datetime

from django.db import transaction
from django.utils.encoding import smart_unicode

from core.models import Item
from projects.models import Item, CodeRepository, CodeCommit
from projects.providers import utils


try:
    import pysvn
except ImportError:
    pysvn = None

log = logging.getLogger("jellyroll.providers.svn")

#
# Public API
#
def enabled():
    return pysvn is not None

def update():
    for repository in CodeRepository.objects.filter(type="svn"):
        _update_repository(repository)
        
#
# Private API
#

def _update_repository(repository):
    source_identifier = "%s:%s" % (__name__, repository.url)
    last_update_date = Item.objects.get_last_update_of_model(CodeCommit, source=source_identifier)
    log.info("Updating changes from %s since %s", repository.url, last_update_date)
    rev = pysvn.Revision(pysvn.opt_revision_kind.date, time.mktime(last_update_date.timetuple()))
    c = pysvn.Client()
    for revision in reversed(c.log(repository.url, revision_end=rev)):
        _handle_revision(repository, revision)

@transaction.commit_on_success
def _handle_revision(repository, r):
    log.debug("Handling [%s] from %s" % (r.revision.number, repository.url))
    ci, created = CodeCommit.objects.get_or_create(
        revision = r.revision.number,
        repository = repository,
        committed = datetime.datetime.fromtimestamp(r.date),
        defaults = {"message": smart_unicode(r.message)}
    )
    return Item.objects.create_or_update(
        instance = ci, 
        timestamp = datetime.datetime.fromtimestamp(r.date),
        source = "%s:%s" % (__name__, repository.url),
    )