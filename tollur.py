#!/usr/bin/env python3
# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4

'''tollur - A scriptable SMTP proxy'''

DESCRIPTION=__doc__
VERSION='0.3 / "After Pleasure Comes Pain"'
URL='https://github.com/a-laget/tollur'

try:
    import logging.handlers
    import configparser
    import importlib
    import argparse
    import asyncore
    import logging
    import smtplib
    import smtpd
    import uuid
    import sys

except ImportError as missing_module:
    print('Failed to load dependencies: "%s"' % missing_module)
    sys.exit(3)

_log = logging.getLogger('tollur')


# -----------------------------------------------------------------------------
class DebugToLog:
    '''Writes smtpd\'s debug stream to standard logging'''

    def write(self, msg):
        # Let's avoid printing the debug streams empty messages, shall we!
        if str(msg).strip():
            _log.debug('EXT: smtpd debug stream: "%s"' % str(msg))

    def flush(self):
        pass


# -----------------------------------------------------------------------------
class SMTPClient(smtplib.SMTP):
    '''SMTP client with some improved logging and various goodies'''

    def _print_debug(self, *args):
        '''Used to send smtplib\'s debug stream to standard logging'''

        msg = ''

        for arg in args:
            msg += str(arg)

        _log.debug('EXT: smtlib debug stream: "%s"' % msg)


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
    def handle_accept(self):
        '''Modified connection handler, as the super does not expose channel'''

        pair = self.accept()

        if pair is not None:
            connection, address = pair

            _log.debug('Incoming connection from %s' % repr(address))

            self.channel = smtpd.SMTPChannel(self, connection, address)
    
    # -------------------------------------------------------------------------
    def _deliver(self, msg_id, sender, recipients, data):
        '''Sends verified messages with SMTP(S) to server'''

        _log.info(
            'Delivering message with ID "%s" from "%s" to "%s"'
            % (msg_id, sender, recipients))

        try:
            _log.debug(
                'Starting SMTP(S) session with server "%s:%s"'
                % (self.server_address, self.server_port))
            
            SMTPClient.debuglevel = 1
            ses = SMTPClient(self.server_address, self.server_port)

            if self.user and self.password:
                _log.debug('Trying to authenticate as user "%s"' % self.user)
                ses.login(self.user, self.password)

            ses.sendmail(sender, recipients, data)

        except Exception as error_msg:
            _log.error(
                'Failed to deliver message with ID "%s": "%s"'
                % (msg_id, error_msg))

            self.channel.push('451 Error: Could not deliver ID "%s"' % msg_id)

            return

        finally:
            try:
                ses.quit()

            # This exception is raised if the session failed to be established
            except UnboundLocalError:
                pass

            except Exception as error_msg:
                _log.debug(
                    'Failed to close session gracefully for ID "%s": "%s"'
                    % (msg_id, error_msg))

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
            
                self.channel.push(
                    '550 Error: ID "%s" was denied by verifier' % msg_id)

                return

        except Exception as error_msg:
            raise Exception(
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

    parser.add_argument(
        '-V', '--version',
        action='version', version=VERSION,
        help='Show application version and exit')
    
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

        if not 'verifier-' + conf['main']['verifier'] in conf:
            raise Exception('Configuration section for verifier is required')

    except Exception as error_msg:
        raise Exception('Failed to parse configuration file: "%s"' % error_msg)

    # TODO: Add more error checking of configuration
    return conf


# -----------------------------------------------------------------------------
def setup_logging(dest, level):
    '''Configures application logging settings'''

    log_formatter = logging.Formatter(
        'tollur: %(levelname)s - %(message)s')

    if level == "debug":
        _log.setLevel(logging.DEBUG)
    
    elif level == "error":
        _log.setLevel(logging.ERROR)

    else:
        _log.setLevel(logging.INFO)

    if dest == 'stderr':
        log_handler = logging.StreamHandler()

    elif dest == 'syslog':
        log_handler = logging.handlers.SysLogHandler(address='/dev/log')

    log_handler.setFormatter(log_formatter)
    _log.addHandler(log_handler)

    return


# -----------------------------------------------------------------------------
def init_verifier(name, conf):
    '''Loads verifier module and sets it up with provided configuration'''

    _log.debug('Loding verifier module "%s"' % name)

    try:
        verifier_module = importlib.import_module('verifiers.' + name)

    except Exception as error_msg:
        raise Exception(
            'Failed to loader verifier module "%s": "%s"'
            % (name, error_msg))

    # -------------------------------------------------------------------------
    _log.debug('Initializing verifier module...')

    try:
        verifier = verifier_module.Verifier(conf)

    except Exception as error_msg:
        raise Exception(
            'Failed to initialize verifier module "%s": "%s"'
            % (name, error_msg))

    return verifier


# -----------------------------------------------------------------------------
def main():
    '''Main application function'''

    args = parse_arguments()    

    try:
        conf = parse_conf(args.conf_file)

    except Exception as error_msg:
        # _log is not used here since it's settings are specified in the config
        print(error_msg)
        sys.exit(1)

    setup_logging(conf['main']['log_dest'], conf['main']['log_level'])

    # -------------------------------------------------------------------------
    try:
        verifier = conf['main']['verifier']
        verifier = init_verifier(verifier, conf['verifier-' + verifier])

    except Exception as error_msg:
        _log.error(error_msg)
        sys.exit(1)

    # -------------------------------------------------------------------------
    # Needed to prevent information leakage from the SMTP server
    smtpd.__version__ = 'SMTP PROXY'
    smtpd.DEBUGSTREAM = DebugToLog()

    try:
        smtp_server = SMTPProxy(
            conf['listen']['address'], int(conf['listen']['port']),
            conf['server']['address'], int(conf['server']['port']),
            conf['server']['user'], conf['server']['password'],
            conf['server']['ca_store'],
            conf['server'].getboolean('start_tls'), verifier)

    except Exception as error_msg:
        _log.error('Failed to configure SMTP proxy: "%s"' % error_msg)
        sys.exit(1)

    # -------------------------------------------------------------------------
    _log.info(
        'Starting Tollur SMTP proxy - listening on %s:%i...'
        % (conf['listen']['address'], int(conf['listen']['port'])))
        
    try:
        asyncore.loop()

    except KeyboardInterrupt:
        _log.info('Tollur was interrupted by keyboard - exiting...')
        sys.exit(3)

    except Exception as error_msg:
        _log.error('SMTP proxy generated unhandled error: "%s"' % error_msg)
        sys.exit(1)


if __name__ == '__main__':
    main()
