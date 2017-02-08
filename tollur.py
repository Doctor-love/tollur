#!/usr/bin/env python3
# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4

'''tollur - SMTP proxy with manual confirmation of outgoing messages'''

DESCRIPTION=__doc__
URL='https://github.com/a-laget/tollur'

try:
    import configparser
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

logging.basicConfig(level=logging.DEBUG)
_log = logging.getLogger('tollur')


# -----------------------------------------------------------------------------
class SMTPProxy(smtpd.SMTPServer):
    '''SMTP proxy with manual confirmation of outgoing messages'''

    def __init__(
        self, listen_address='127.0.0.1', listen_port=9025,
        server_address=None, server_port=25, user=None, password=None,
        ca_store=None, start_tls=False, verifier=None):

        self.listen_address = str(listen_address)
        self.listen_port = int(listen_port)

        if server_address is None or verifier is None:
            raise TypeError(
                'Argument "server_address" and "verifier" are required')
        
        self.server_address = server_address
        self.server_port = int(server_port)

        self.user = user
        self.password = password
        self.ca_store = ca_store
        self.start_tls = start_tls
        self.verifier = verifier

        super(SMTPProxy, self).__init__(
            (self.listen_address, self.listen_port),
            (self.server_address, self.server_port))
    
    # -------------------------------------------------------------------------
    def _deliver(msg_id, sender, recipients, data):
        '''Sends verified messages with SMTP(S) to server'''

        _log.info(
            'Delivering message with ID "%s" from "%s" to "%s"'
            % (msg_id, sender, recipients))

        try:
            _log.debug(
                'Starting SMTP(S) session with server "%s:%s"'
                % (self.server_address, self.server_port))
            
            ses = smtplib.SMTP(self.server_address, self.server_port)

        except Exception as error_msg:
            _log.error(
                'Failed to deliver message with ID "%s": "%s"'
                % (msg_id, error_msg))

            return

        finally:
            try:
                ses.quit()

            except Exception as error_msg:
                _log.debug('Failed to close session: "%s"' % error_msg)

            return                 

    # -------------------------------------------------------------------------
    def process_message(self, peer, sender, recipients, data):
        '''Calls verifier to check if incoming e-mail should be sent'''

        msg_id = uuid.uuid4()

        _log.info(
            'Proxy received incoming mail - '
            'ID: "%s", peer: "%s", sender: "%s", recipients: "%s"'
            % (msg_id, peer, sender, recipients))

        try:
            if self.verifier.verify(msg_id, peer, sender, recipients, data):
                _log.info('Verifier accepted message ID "%s"' % msg_id)

                self._deliver(msg_id, sender, recipients, data)
                return

            else:
                _log.error('Verifier did not accept message ID "%s"' % msg_id)
        
                return

        except Exception as error_msg:
            raise VerificationError(
                'Verifier raised unhandled exception: "%s"' % error_msg)


# -----------------------------------------------------------------------------
def parse_arguments():
    '''Parses command line arguments'''

    parser = argparse.ArgumentParser(
        description=DESCRIPTION,
        epilog='For information about configuration options, see: %s' % URL)

    parser.add_argument(
        dest='conf_file',
        metavar='/path/to/conf.ini', type=argparse.FileType('r'),
        help='Path to tollur configuration file')    
    
    return parser.parse_args()


# -----------------------------------------------------------------------------
def parse_conf(conf_file):
    '''Parses configuration file as INI an checks required values'''  

    conf = configparser.ConfigParser()

    try:
        conf.read_file(conf_file)

        # Various error checking of provided configuration file
        for section in ['main', 'listen', 'server']:
            if not section in conf:
                raise Exception(
                    'Section "%s" required in configurationi file' % section)

        if not 'verifier' in conf['main']:
            raise Exception('Verifier needs to be specified in "main" section')

        if not conf['main']['verifier'] in conf:
            raise Exception('Configuration section for verifier is required')

    except Exception as error_msg:
        raise Exception('Failed to parse configuration file: "%s"' % error_msg)

    # TODO: Add more error checking of configuration
    return conf


# -----------------------------------------------------------------------------
def setup_logging(dest, level):
    '''Configures application logging settings'''

    # TODO: Acctually do something here!
    pass


# -----------------------------------------------------------------------------
def init_verifier(name, conf):
    '''Loads verifier module and sets it up with provided configuration'''

    # TODO: Acctually do something here!
    return 'FISK'


# -----------------------------------------------------------------------------
def main():
    '''Main application function'''

    args = parse_arguments()    

    try:
        conf = parse_conf(args.conf_file)

    except Exception as error_msg:
        # _log is not used here since it's settings are specified in the config
        print(error_msg)
        exit(1)

    setup_logging(conf['main']['log_dest'], conf['main']['log_level'])

    # -------------------------------------------------------------------------
    try:
        verifier_name = conf['main']['verifier']
        verifier = init_verifier(verifier_name, conf[verifier_name])

    except Exception as error_msg:
        _log.error(error_msg)
        exit(1)

    try:
        smtp_server = SMTPProxy(
            conf['listen']['address'], int(conf['listen']['port']),
            conf['server']['address'], int(conf['server']['port']),
            conf['server']['user'], conf['server']['password'],
            conf['server']['ca_store'],
            conf['server'].getboolean('start_tls'), verifier)

    except Exception as error_msg:
        _log.error('Failed to configure SMTP proxy: "%s"' % error_msg)
        exit(1)

    # -------------------------------------------------------------------------
    _log.info(
        'Starting Tollur SMTP proxy - listening on %s:%i...'
        % (conf['listen']['address'], int(conf['listen']['port'])))
        
    try:
        asyncore.loop()

    except KeyboardInterrupt:
        _log.info('Tollur was interrupted by keyboard - exiting...')
        exit(3)

    except Exception as error_msg:
        _log.error('SMTP proxy generated unhandled error: "%s"' % error_msg)
        exit(1)


if __name__ == '__main__':
    main()
