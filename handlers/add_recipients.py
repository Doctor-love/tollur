# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4

import logging
_log = logging.getLogger('tollur')

class Handler:
    '''Handler plugin that adds user specified recipients to messages''' 

    def __init__(self, conf):
        self.extra_recipients = conf['extra_recipients'].split(',')

    def process(self, msg):
        _log.info(
            'Adding recipients "%s" to message ID "%s"'
            % (', '.join(self.extra_recipients), msg.mid))

        msg.recipients += self.extra_recipients

        return True, msg
