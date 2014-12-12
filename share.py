#!/usr/bin/env python3

"""

Share file and notify by email

Depends: msmtp
Recommends: vsftpd, dropbox, dropbox-cli

Author:   David J. H. Shih  <djh.shih@gmail.com>
Date:     2011-08-15
License:  GPLv3

"""


import os, subprocess, argparse, shutil, textwrap, time, ftplib


class emaildb:

	emails = {
		'davids': 'david.shih@no.spam.com',
		'pauln': 'panorthcott@no.spam.com',
		'michaelt': 'mdtaylor@no.spam.com',
	}

	def get(self, name):
		try:
			email = self.emails[name]
		except:
			raise Exception('Name is not found in contact list')
		return email


class share_protocol:

	def format_mail(self, to_email, from_email, subject, link, instructions, message, signature):
		return textwrap.dedent('''
			To: {0}
			From: {1}
			Subject: {2}
			Reply-To: {1}

			{3}
			{4}
			{5}
			{6}
			''')\
			.format(to_email, from_email, subject, link, instructions, message, signature)\
			.strip()

class ftp(share_protocol):

	""" Share via ftp. Login required. """

	def __init__(self, host=None, user=None, password=None):
		self.host = host
		self.user = user
		self.password = password

		self.instructions = textwrap.dedent('''
		Click the above link or paste it into a browser.
		If you are prompted to login, enter the following information.

		user: {0}
		password: {1}''')\
		.format(user, password)

	def mail(self, args):

		print('Sharing via ftp server...')

		conn = ftplib.FTP(self.host)
		conn.login(self.user, self.password)

		with open(args.file, 'rb') as f:
			try:
				conn.cwd(args.recipient)
			except:
				# try removing any possible file that has the same name as the directory to be created
				try:
					conn.delete(args.recipient)
				except: pass
				# directory probably does not exist: create it
				conn.mkd(args.recipient)
				conn.cwd(args.recipient)

			print(conn.pwd())
			# send file in binary transfer mode
			conn.storbinary('STOR ' + os.path.basename(args.file), f)

		link = 'ftp://{0}:{1}@{2}/{3}/{4}'.format(self.user, self.password, 
			self.host, args.recipient, os.path.basename(args.file))

		return super().format_mail(args.to_email, args.from_email, args.subject, link,
			self.instructions, args.message, args.signature)


class ftp_local(ftp):

	""" Share via local ftp. An ftp server must be setup (e.g. vsftpd). """
	""" Warning: permissions may not be set properly. """

	path = '/srv/ftp'

	def mail(self, args):

		print('Sharing via local ftp server...')

		# copy file to local ftp directory
		ftp_dir = os.path.join(self.path, args.recipient)
		if not os.path.exists(ftp_dir):
			os.mkdir(ftp_dir)
		shutil.copy(args.file, ftp_dir)

		link = 'ftp://{0}:{1}@{2}/{3}/{4}'.format(self.user, self.password, 
			self.host, args.recipient, os.path.basename(args.file))

		return super().format_mail(args.to_email, args.from_email, args.subject, link,
			self.instructions, args.message, args.signature)


class dropbox(share_protocol):
	
	""" Share via dropbox. Programs dropbox and dropbox-cli must be installed """

	path = os.path.join(os.environ['HOME'], 'Dropbox', 'Public')

	instructions = textwrap.dedent('''
	Click the above link or paste it into a browser.
	Please notify me when you have downloaded the file.''')

	def mail(self, args):
		
		print('Sharing via Dropbox...')

		# copy file to local sync directory
		shutil.copy(args.file, self.path)
		file_path = os.path.join(self.path, os.path.basename(args.file))

		cmd = 'dropbox'

		subprocess.Popen([cmd, 'start'])

		print ('Syncing file...')
		while True:
			time.sleep(1)
			p = subprocess.Popen([cmd, 'filestatus', file_path], stdout=subprocess.PIPE)
			status = p.communicate()[0].decode('utf8').split(':')[1].strip()
			if status == 'up to date':
				break

		p = subprocess.Popen([cmd, 'puburl', file_path], stdout=subprocess.PIPE)
		link = p.communicate()[0].decode('utf8').strip()

		return super().format_mail(args.to_email, args.from_email, args.subject, link,
			self.instructions, args.message, args.signature)


def input_yesno(msg='', default='y'):
	if default == 'y':
		msg += ' [Y/n] '
	else:
		msg += ' [y/N] '

	x = input(msg)
	if x:
		# x is not empty, check validity
		while not x.lower() in ('y', 'n'):
			x = input(msg)
		x = x.lower()
	else:
		# use default option
		x = default
	
	return x == 'y'


def main():

	mail_fname = '/tmp/tmp.mail'
	mail_from = 'david.shih@no.spam.com'

	mail_signature = textwrap.dedent('''
	Cheers,
	David
	''')

	## Argument parser

	parser = argparse.ArgumentParser(description='Share file through FTP.')
	parser.add_argument('file', type=str, help='file to share')
	parser.add_argument('recipient', type=str, help='recipient nickname')
	parser.add_argument('subject', type=str, help='subject line of email')
	parser.add_argument('-f', '--from_email', type=str, default=mail_from, help="sender's email address")
	parser.add_argument('-t', '--to_email', type=str, help="recipient's email address")
	parser.add_argument('-m', '--message', type=str, default='', help='additional body message')
	parser.add_argument('-s', '--signature', type=str, default=mail_signature, help='email signature')
	parser.add_argument('-q', '--quick', action='store_true', help='skip prompts and message editing')
	parser.add_argument('--ftp_local', action='store_const', dest='protocol', const=ftp_local, default=ftp, help='sharing protocol')
	parser.add_argument('--dropbox', action='store_const', dest='protocol', const=dropbox, help='sharing protocol')

	args = parser.parse_args()

	if not args.to_email:
		args.to_email = emaildb().get(args.recipient)


	## Share file and prepare email

	mail_str = args.protocol().mail(args)


	send_email = True

	## Edit email message

	if not args.quick:

		# write message to temporary file for editing
		mail = open(mail_fname, 'w')
		mail.write(mail_str)
		mail.close()

		if os.environ['EDITOR']:
			editor = os.environ['EDITOR']
		else:
			editor = 'vi'
		p = subprocess.Popen([editor, mail_fname])
		p.wait()

		send_email = input_yesno('Continue sending email?')


	## Send email

	if send_email:

		print("Sending email...")

		msmtp = ['msmtp', args.to_email] 

		p = subprocess.Popen(msmtp, stdin=subprocess.PIPE)
		p.communicate(bytes(mail_str, 'utf8'))
		p.stdin.close()


if __name__ == '__main__':
	main()

