# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4

import logging
_log = logging.getLogger('tollur')

class Handler:
    '''Handler class for a simple white list plugin''' 

    def __init__(self, conf):
        self.whitelist_domains = conf['whitelist_domains'].split(',')
        self.include_subdomains = conf.getboolean('include_subdomains')

    def process(self, msg):
        '''Function that is used to determine the status of received mail'''
        
        _log.debug('Checking if recipients domains are in whitelist')

        for recipient in msg.recipients:
            recipient_parts = recipient.split('@')

            if len(recipient_parts) != 2:
                _log.info(
                    'Something fishy is going on in message "%s" - '
                    'peer "%s" is trying to send a message to "%s"!'
                    % (msg.mid, str(msg.peer), str(recipient_parts)))

                return False, msg

            domain = recipient_parts[1]
            _log.debug(domain)

            if domain not in self.whitelist_domains:
                _log.info('Domain "%s" is not whitelisted!' % domain)

                return False, msg

        _log.info('Everything looks good - accepting "%s"' % msg.mid)

        return True, msg
