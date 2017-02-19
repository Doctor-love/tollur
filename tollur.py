#!/usr/bin/env python3
# vim: tabstop=8 expandtab shiftwidth=4 softtabstop=4

'''tollur - A scriptable SMTP proxy'''

DESCRIPTION=__doc__
VERSION='0.6 / "Cryptic Struggles"'
URL='https://github.com/doctor-love/tollur'

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
    import ssl
    import sys

except ImportError as missing_module:
    print('Failed to load dependencies: "%s"' % missing_module)
    sys.exit(3)

# Should probably work with older Python 3 versions as well, but not tested
if sys.version_info < (3, 5):
    print('Tollur requires Python 3.5 or later - sorry!\n')
    sys.exit(3)

if ssl.OPENSSL_VERSION_INFO < (0, 9, 8):
    print('Tollur requires OpenSSL 0.9.8 or later - sorry!\n')
    sys.exit(3)

if sys.platform != 'linux':
    print('Tollur has only been tested on Linux - sorry!\n')
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
class MailMessage():
    '''Object used by handler plugin to manipulate forwarded message'''

    def __init__(self, peer, sender, recipients, data):
        self.peer = peer
        self.sender = sender
        self.recipients = recipients
        self.data = data
        self.mid = uuid.uuid4()


# -----------------------------------------------------------------------------
class SMTPClient(smtplib.SMTP):
    '''SMTP client with some improved logging and various goodies'''
                
    debuglevel = 1

    def _print_debug(self, *args):
        '''Used to send smtplib\'s debug stream to standard logging'''

        # Looks a bit strange, but smtplib passwd *args to print()
        msg = ''

        for arg in args:
            msg += str(arg)

        _log.debug('EXT: smtlib debug stream: "%s"' % msg)


# -----------------------------------------------------------------------------
class SMTPSClient(smtplib.SMTP_SSL):
    '''SMTPS client with some improved logging and various goodies'''
    
    debuglevel = 1

    def _print_debug(self, *args):
        '''Used to send smtplib\'s debug stream to standard logging'''

        msg = ''

        for arg in args:
            msg += str(arg)

        _log.debug('EXT: smtlib debug stream: "%s"' % msg)


# -----------------------------------------------------------------------------
class SMTPProxy(smtpd.SMTPServer):
    '''SMTP proxy with manual confirmation of outgoing messages'''
    
    # -------------------------------------------------------------------------
    def configure_upstream_tls(self):
        '''Sets up the TLS context for upstream based on user preferences'''

        _log.debug('Setting up upstream TLS context...')

        # Using a tweaked default context to minimize future "crypto rot"
        context = ssl.create_default_context(cafile=self.ca_store)
        
        _log.debug(
            'Loaded CA certs for upstream context: "%s"'
            % str(context.get_ca_certs()))

        context.verify_mode = ssl.CERT_REQUIRED
        context.check_hostname = True

        _log.debug('Configuring TLS protocols for upstream connection')

        context.options |= ssl.OP_NO_SSLv3

        # TODO: Add later TLS versions once they have been implemented
        versions = {
            1.0: ssl.OP_NO_TLSv1, 1.1: ssl.OP_NO_TLSv1_1,
            1.2: ssl.OP_NO_TLSv1_2}

        if self.tls_version:
            for version, option in versions.items():
                if version < self.tls_version:
                    _log.debug('Disabling upstream TLS version %s' % version)
                
                    context.options |= option

        if self.upstream_crl_check == 'chain': 
            context.verify_flags = ssl.VERIFY_CRL_CHECK_CHAIN
        
        elif self.upstream_crl_check == 'cert': 
            context.verify_flags = ssl.VERIFY_CRL_CHECK_LEAF

        if self.upstream_cipher_suites:
            context.set_ciphers(self.upstream_cipher_suites)

        return context

    # -------------------------------------------------------------------------
    def __init__(
        self, server_address='127.0.0.1', server_port=9025,
        upstream_address=None, upstream_port=25, user=None, password=None,
        ca_store=None, tls_mode='start_tls', upstream_cipher_suites='',
        tls_version=1.2, upstream_crl_check='chain', handler=None):

        self.server_address = str(server_address)
        self.server_port = int(server_port)

        if upstream_address is None or handler is None:
            raise TypeError(
                'Argument "upstream_address" and "handler" are required')
        
        self.upstream_address = upstream_address
        self.upstream_port = int(upstream_port)

        self.user = user
        self.password = password
        self.ca_store = ca_store
        self.tls_mode = tls_mode
        self.upstream_cipher_suites = upstream_cipher_suites
        self.upstream_crl_check = upstream_crl_check
        self.handler = handler
        
        if tls_version:
            self.tls_version = float(tls_version)

        else:
            self.tls_version = tls_version

        if self.tls_mode:
            self.tls_mode = tls_mode
            self.upstream_tls_context = self.configure_upstream_tls()

        super(SMTPProxy, self).__init__(
            (self.server_address, self.server_port),
            (self.upstream_address, self.upstream_port))

    # -------------------------------------------------------------------------
    def handle_accept(self):
        '''Modified connection handler, as the super does not expose channel'''

        pair = self.accept()

        if pair is not None:
            connection, address = pair

            _log.debug('Incoming connection from %s' % repr(address))

            self.channel = smtpd.SMTPChannel(self, connection, address)
    
    # -------------------------------------------------------------------------
    def _deliver(self, msg):
        '''Sends processed messages with SMTP(S) to upstream server'''

        _log.info(
            'Delivering message with ID "%s" from "%s" to "%s"'
            % (msg.mid, msg.sender, msg.recipients))

        try:
            _log.debug(
                'Starting SMTP(S) session with server "%s:%s"'
                % (self.upstream_address, self.upstream_port))

            if self.tls_mode is None or self.tls_mode == "start_tls":
                ses = SMTPClient(self.upstream_address, self.upstream_port)

            else:
                ses = SMTPSClient(
                    self.upstream_address, self.upstream_port,
                    context=self.upstream_tls_context)

            if self.tls_mode == "start_tls":
                ses.starttls(context=self.upstream_tls_context)
            
            if self.tls_mode:
                _log.debug(
                    'Established upstream connection - TLS session info: "%s"'
                    % str(self.upstream_tls_context.session_stats()))

            # -----------------------------------------------------------------
            if self.user and self.password:
                _log.debug('Trying to authenticate as user "%s"' % self.user)
                ses.login(self.user, self.password)

            ses.sendmail(msg.sender, msg.recipients, msg.data)
            
            if self.tls_mode:
                _log.debug(
                    'Finished upstream connection - TLS session info: "%s"'
                    % str(self.upstream_tls_context.session_stats()))

        except Exception as error_msg:
            _log.error(
                'Failed to deliver message with ID "%s": "%s"'
                % (msg.mid, error_msg))

            self.channel.push('451 Error: Could not deliver ID "%s"' % msg.mid)

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
                    % (msg.mid, error_msg))

        return                 

    # -------------------------------------------------------------------------
    def process_message(self, peer, sender, recipients, data):
        '''Calls handler to check if incoming e-mail should be sent'''

        msg = MailMessage(peer, sender, recipients, data)

        _log.info(
            'Proxy received incoming mail - '
            'ID: "%s", peer: "%s", sender: "%s", recipients: "%s"'
            % (msg.mid, msg.peer, msg.sender, msg.recipients))

        try:
            forward, msg = self.handler.process(msg)

            if forward:
                _log.info('Handler accepted message ID "%s"' % msg.mid)

                self._deliver(msg)
                return

            else:
                _log.error('Handler did not accept message ID "%s"' % msg.mid)
            
                self.channel.push(
                    '550 Error: ID "%s" was denied by handler' % msg.mid)

                return

        except Exception as error_msg:
            raise Exception(
                'Handler raised unhandled exception: "%s"' % error_msg)


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
        for section in ['main', 'server', 'upstream']:
            if not section in conf:
                raise Exception(
                    'Section "%s" required in configurationi file' % section)

        if not 'handler' in conf['main']:
            raise Exception('Handler needs to be specified in "main" section')

        if not 'handler-' + conf['main']['handler'] in conf:
            raise Exception('Configuration section for handler is required')

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
def init_handler(name, conf):
    '''Loads handler module and sets it up with provided configuration'''

    _log.debug('Loading handler module "%s"' % name)

    try:
        handler_module = importlib.import_module('handlers.' + name)

    except Exception as error_msg:
        raise Exception(
            'Failed to loader handler module "%s": "%s"'
            % (name, error_msg))

    # -------------------------------------------------------------------------
    _log.debug('Initializing handler module...')

    try:
        handler = handler_module.Handler(conf)

    except Exception as error_msg:
        raise Exception(
            'Failed to initialize handler module "%s": "%s"'
            % (name, error_msg))

    return handler


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
    if not conf.getboolean('main', 'iunderstandwhatiamdoing'):
        _log.error(
            'Tollur is experimental software - read through the source code, '
            'example configuration, open issues and try again! :-)')

        sys.exit(3)

    # -------------------------------------------------------------------------
    try:
        handler = conf['main']['handler']
        handler = init_handler(handler, conf['handler-' + handler])

    except Exception as error_msg:
        _log.error(error_msg)
        sys.exit(1)

    # -------------------------------------------------------------------------
    # Needed to prevent information leakage from the SMTP server
    smtpd.__version__ = 'SMTP PROXY'
    smtpd.DEBUGSTREAM = DebugToLog()

    try:
        smtp_server = SMTPProxy(
            conf['server']['address'], int(conf['server']['port']),
            conf['upstream']['address'], int(conf['upstream']['port']),
            conf['upstream']['user'], conf['upstream']['password'],
            conf['upstream']['ca_store'], conf['upstream']['tls_mode'],
            conf['upstream']['cipher_suites'], conf['upstream']['tls_version'],
            conf['upstream']['crl_check'], handler)

    except Exception as error_msg:
        _log.error('Failed to configure SMTP proxy: "%s"' % error_msg)
        sys.exit(1)

    # -------------------------------------------------------------------------
    _log.info(
        'Starting Tollur SMTP proxy - listening on %s:%i...'
        % (conf['server']['address'], int(conf['server']['port'])))
        
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
