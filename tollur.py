#!/usr/bin/env python
# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4

'''tollur - SMTP proxy with manual confirmation of outgoing messages'''

try:
    import argparse
    import asyncore
    import logging
    import smtplib
    import smtpd
    import uuid

    from sys import exit

except ImportError as missing_module:
    print('Failed to load dependencies: "%s"' % missing_module)
    exit(3)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger('tollur')


# -----------------------------------------------------------------------------
class SMTPProxy(smtpd.SMTPServer):
    '''SMTP proxy with manual confirmation of outgoing messages'''

    def __init__(
        self, listen_address='127.0.0.1', listen_port=9025,
        server_address=None, server_port=None, user=None, password=None,
        cert_chain=None, start_tls=True, verifier=None):

        self.listen_address = str(listen_address)
        self.listen_port = int(listen_port)

        if server_address is None or verifier is None:
            raise TypeError(
                'Argument "server_address" and "verifier" are required')
        
        self.server_address = server_address
        self.verifier = verifier

        if server_port is None and start_tls:
            self.server_port = 25
        
        elif server_port is None and not start_tls:
            self.sever_port = 465

        else:
            self.server_port = int(server_port)

        self.user = user
        self.password = password
        self.cert_chain = cert_chain
        self.start_tls = start_tls

        super(SMTPProxy, self).__init__(
            (self.listen_address, self.listen_port),
            (self.server_address, self.server_port))

    # -------------------------------------------------------------------------
    def process_message(self, peer, sender, recipients, data):
        '''Calls verifier to check if incoming e-mail should be sent'''

        msg_id = uuid.uuid4()

        log.info(
            'Proxy received incoming mail - '
            'ID: "%s", peer: "%s", sender: "%s", recipients: "%s"'
            % (msg_id, peer, sender, recipients))

        try:
            if self.verifier.verify(msg_id, peer, sender, recipients, data):
                log.info('Verifier accepted message ID "%s"' % msg_id)

                self._deliver(sender, recipients, data)
                return

            else:
                log.error('Verifier did not accept message ID "%s"' % msg_id)
        
                return

        except Exception as error_msg:
            raise VerificationError(
                'Verifier raised unhandled exception: "%s"' % error_msg)

# -----------------------------------------------------------------------------
def parse_arguments():
    '''Parses command line arguments'''

    pass


# -----------------------------------------------------------------------------
def main():
    '''Main application function'''

    args = parse_arguments()    
    log.debug('Provided arguments: "%s"' % str(args))

    try:
        smtp_server = SMTPProxy(
            args.listen_address, args.listen_port)

    except Exception as error_msg:
        log.error('Failed to start SMTP proxy: "%s"' % error_msg)
        exit(1)

    log.info(
        'Starting Tollur SMTP proxy - listening on %s:%i...'
        % (args.listen_address, args.listen_port))
        
    try:
        asyncore.loop()

    except Exception as error_msg:
        logger.error('SMTP proxy generated unhandled error: "%s"' % error_msg)
        exit(1)


if __name__ == '__main__':
    main()
