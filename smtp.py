import base64
import os
import ssl
import socket
import logging
import json
from os import path
import sys

logging.basicConfig(filename="{}.log".format(__file__), level=logging.DEBUG, filemode='w')


def to_base64(byte_string):
    return base64.b64encode(byte_string)


def from_base64(base64_string):
    return base64.b64decode(base64_string)


sock = socket.socket()
ssl_socket = ssl.wrap_socket(sock)


def sendall(data):
    if isinstance(data, str):
        data = data.encode()

    ssl_socket.sendall(data + b'\r\n')


class SmtpClient:
    def __init__(self, host: str, login: str, password: str, port: int=465):
        self.attachments_paths = []
        self.boundary = 'boundary-ololo'
        self.host = host if host.startswith('smtp') else 'smtp.' + host
        self.port = port
        self.login = login
        self.password = password
        self.ssl_socket = ssl.wrap_socket(socket.socket())
        # Как устанавливается SSl соединение
        self.buflen = 2 ** 16
        self.connect()

    def sendall(self, data=None):
        logger = logging.getLogger('MSG')
        if not data:
            data = b''
        if isinstance(data, str):
            data = data.encode()
        logger.debug(data.decode())
        self.ssl_socket.sendall(data + b'\r\n')

    def receive(self):
        return self.ssl_socket.recv(self.buflen)

    def connect(self):
        self.ssl_socket.connect((self.host, self.port))
        logging.info(self.receive())
        self.sendall('EHLO 1')
        logging.info(self.receive())
        self.sendall('AUTH LOGIN')
        logging.info(self.receive())
        self.sendall(to_base64(self.login.encode()))
        logging.info(self.receive())
        self.sendall(to_base64(self.password.encode()))

        data = self.receive()
        if not data.decode().startswith('235'):
            logging.error('Authentication failed')
            raise Exception('Authentication failed')
        else:
            logging.info(data)

    def add_attachment(self, attachment_path):
        if not path.exists(attachment_path):
            raise Exception("Attachment \"{}\" doesn't exist".format(attachment_path))
        self.attachments_paths.append(attachment_path)

    def send_boundary(self):
        self.sendall('--{}'.format(self.boundary))

    def send_attachment(self, attachments):
        if path.getsize(attachments) > 10 * 1024 * 1024:
            raise Exception('Too large attachment: {}'
                            .format(attachments))
        attachment_name = path.basename(attachments)
        self.send_boundary()
        self.sendall('Content-Transfer-Encoding: base64')
        self.sendall('Content-Type: application/octet-stream; name="{}"'
                     .format(attachment_name))
        self.sendall('Content-Disposition: attachment; filename="{}"'
                     .format(attachment_name))
        self.sendall()
        with open(attachments, 'rb') as f:
            self.sendall(to_base64(f.read()))
        self.sendall()

    def send_attachments(self):
        for attachments in self.attachments_paths:
            self.send_attachment(attachments)

    def send_headers(self, from_email, from_name, recipients, subject, to_name):
        self.sendall('MAIL FROM: <{0}>'.format(from_email))
        logging.info(self.receive())
        self.sendall('RCPT TO: {}'.format(self.format_recipients(recipients)))
        logging.info(self.receive())
        self.sendall('DATA')
        logging.info(self.receive())
        self.sendall('From: "{}" <{}>'.format(from_name, from_email))
        self.sendall('Subject: {}'.format(subject))
        if to_name:
            self.sendall('To: "{}" <{}>'.format(to_name, recipients[0]))
        else:
            self.sendall('To: {}'.format(self.format_recipients(recipients)))

    def send_body(self, msg_path):
        self.sendall('MIME version: 1.0')
        self.sendall('Content-Type: multipart/mixed; '
                     'boundary="{}"'.format(self.boundary))
        self.sendall()
        self.send_boundary()
        self.sendall('Content-Type: text/plain; charset="UTF-8"')
        self.sendall('Content-Transfer-Encoding: base64')
        self.sendall()
        with open(msg_path, 'rb') as f:
            self.sendall(to_base64(f.read()))
        self.sendall()
        if self.attachments_paths:
            self.send_attachments()
        self.send_boundary()
        self.sendall()
        self.sendall('.')

    def send_message(self, msg_path, recipients: list, from_email: str=None,
                     from_name: str=None, subject='Without subject',
                     to_name=None):
        if not recipients:
            raise Exception('You must specify at least one recipient')

        if not from_email:
            from_email = '{0}@{1}'.format(self.login,
                                          self.host.split('smtp.')[-1])

        if not from_name:
            from_name = from_email.split('@')[0]

        if len(recipients) == 1:
            if not to_name:
                to_name = recipients[0].split('@')[0]
        else:
            to_name = None

        self.send_headers(from_email, from_name, recipients, subject, to_name)

        self.send_body(msg_path)

        data = self.receive()
        logging.info(data)
        if not data.decode().startswith('250'):
            raise Exception('Message not sent')

    @staticmethod
    def format_recipients(recipients):
        return ', '.join(['<{}>'.format(x) for x in recipients])


if __name__ == '__main__':
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
    except:
        print('Configuration file not found')
        sys.exit(1)
    client = SmtpClient(**config)
    client.add_attachment('картинка.png')
    client.add_attachment('config.json')
    client.send_message('msg.txt', ['gallyamb@gmail.com'],
                        from_name='Gallyam Biktashev',
                        subject='Hi, guys', to_name='BigBear')
