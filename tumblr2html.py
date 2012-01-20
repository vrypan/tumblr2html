#! /usr/bin/env python

# tumblr2html
# Copyright 2012 Panayotis Vryonis 
# http://vrypan.net/
# License: MIT.

import json
import urllib
import urllib2
import urlparse
import os
from django.template import Template, Context, loader
from django.conf import settings
import re
from datetime import date
import argparse
import shutil

settings.configure(
		DEBUG=True,
		TEMPLATE_DEBUG=True,
		TEMPLATE_DIRS=('templates',)
		)
		
def remove_html_tags(data):
	p = re.compile(r'<.*?>')
	return p.sub('', data)

class tumblr2html(object):
	def __init__(self, 
			tumblr_api_key=None, 
			blog=None, 
			html_path=None, 
			cont=False, 
			remember_api_key=False):		
		self.tumblr_api_key = tumblr_api_key
		self.blog = blog
		self.html_path = html_path
		self.index = []
		self.total_posts = 0
		self.rendered_posts = 0
		self.last_post_id = 0
		self.min_id = 0 # Do not render posts with ID <= than this. Used when --continue is selected
		self.cont = cont # True if --contine is selected
		self.key_from_conf=False # Did we read the api key from local cache? 
		self.remember_api_key = remember_api_key # Did the user ask (--remember-api-key) to store the key in local cache?
		
		if cont:
			self.get_conf()

		if not self.tumblr_api_key:
			self.init_ok = False
			return
		if not self.blog:
			self.init_ok = False
			return
		if not self.html_path:
			self.init_ok = False
			return
		self.init_ok = True
		
		self.get_blog_info()
		
		self.ppp = 10 # posts per page
		(self.total_pages,res) = divmod(self.total_posts, self.ppp)
		
	def get_blog_info(self):
		request_url = 'http://api.tumblr.com/v2/blog/%s/info?api_key=%s' % (self.blog, self.tumblr_api_key)
		response = urllib.urlopen(request_url)
		json_response = json.load(response)
		self.blog_info = json_response['response']['blog']
		self.total_posts = json_response['response']['blog']['posts']

	def get_conf(self):
		try:
			f = open(os.path.join(self.html_path,'.tumblr2html.json'), 'r')
			data = json.load(f)
			if data['blog']:
				self.blog = data['blog']
			if data['tumblr_api_key']:
				self.tumblr_api_key = data['tumblr_api_key']
				self.key_from_conf = True
			if data['last_post_id']:
				self.min_id = data['last_post_id']
			if data['index']:
				self.index = data['index']
		except IOError:
			pass
		f.close()

	def get_total_posts(self):
		if self.total_posts:
			return self.total_posts
		else:
			self.get_blog_info()
			return self.total_posts
			
	def render_text_post(self,p,b):
		path = os.path.join(self.html_path, 'posts', str(p['id']) )
		filename = os.path.join(path,'index.html')
		if not os.path.exists(path):
			os.makedirs(path)
		f = open(os.path.join(path,'post.json'), 'w')
		f.write(json.dumps(p))
		f.close()

		if not p['title']:
			p['title'] = remove_html_tags(p['body'])[0:140]

		# locate any links to uploaded images, make a local copy, 
		# and replace remote links with local
		img_links = re.findall(r'img src=[\'"]?([^\'" ]+)', p['body'])
		for i, img in enumerate(img_links):
			img_extension = os.path.splitext(img)[1][1:]
			img_filename = "img_%s.%s" % (i, img_extension) 
			img_file = os.path.join(path, img_filename)
			remote_file = urllib2.urlopen(img)
			local = open(img_file,'wb')
			local.write(remote_file.read())
			local.close()
			p['body'] = p['body'].replace(img,img_filename)
		
		context = Context({'post':p, 'blog':b})
		template = loader.get_template('text.html')
		html = template.render(context)
		f = open(filename,'w')
		f.write(html.encode('utf-8'))
		f.close()
		print "[text]", path
		
	def render_photo_post(self,p,b):
		path = os.path.join(self.html_path, 'posts', str(p['id']) )
		filename = os.path.join(path,'index.html')
		if not os.path.exists(path):
			os.makedirs(path)
			
		f = open(os.path.join(path,'post.json'), 'w')
		f.write(json.dumps(p))
		f.close()

		for i,photo in enumerate(p['photos']):			
			extension = os.path.splitext(photo['original_size']['url'])[1][1:] # get the original file extension.
			img_filename = "%s_original.%s" % (i, extension) 
			img_file = os.path.join(path, img_filename)
			remote_file = urllib2.urlopen(photo['original_size']['url'])
			local = open(img_file,'wb')
			local.write(remote_file.read())
			local.close()
			photo['original_size']['url'] = os.path.join('img',img_filename)

			prev_i = 0
			prev_w = 0
			prev_h = 0

			for alt in photo['alt_sizes']:
				img_filename = "%s_%sx%s.%s" % (i, alt['width'], alt['height'], extension) 
				img_file = os.path.join(path, img_filename)
				remote_file = urllib2.urlopen(alt['url'])
				local = open(img_file,'wb')
				local.write(remote_file.read())
				local.close()
				alt['url'] = img_filename
				if alt['width']<401 and alt['width']>prev_w:
					prev_url = alt['url']
					prev_w = alt['width']
					prev_h = alt['height']

			photo['prev'] = {'url':prev_url, 'width': prev_w, 'height':prev_h }
			p['title'] = 'photo'

		context = Context({'post':p, 'blog':b})
		template = loader.get_template('photo.html')
		html = template.render(context)
		f = open(filename,'w')
		f.write(html.encode('utf-8'))
		f.close()

		print "[photo]", path
		
	def render_link_post(self,p,b):
		path = os.path.join(self.html_path, 'posts', str(p['id']) )
		filename = os.path.join(path,'index.html')
		if not os.path.exists(path):
			os.makedirs(path)

		f = open(os.path.join(path,'post.json'), 'w')
		f.write(json.dumps(p))
		f.close()

		context = Context({'post':p, 'blog':b})
		template = loader.get_template('link.html')
		html = template.render(context)
		f = open(filename,'w')
		f.write(html.encode('utf-8'))
		f.close()

		print "[link]", path

	def render_quote_post(self,p,b):
		path = os.path.join(self.html_path, 'posts', str(p['id']) )
		filename = os.path.join(path,'index.html')
		if not os.path.exists(path):
			os.makedirs(path)
			
		f = open(os.path.join(path,'post.json'), 'w')
		f.write(json.dumps(p))
		f.close()

		context = Context({'post':p, 'blog':b})
		template = loader.get_template('quote.html')
		html = template.render(context)
		f = open(filename,'w')
		f.write(html.encode('utf-8'))
		f.close()

		p['title'] = 'quote'

		print "[quote]", path

	def render_chat_post(self,p,b):
		path = os.path.join(self.html_path, 'posts', str(p['id']) )
		filename = os.path.join(path,'index.html')
		if not os.path.exists(path):
			os.makedirs(path)

		f = open(os.path.join(path,'post.json'), 'w')
		f.write(json.dumps(p))
		f.close()

		context = Context({'post':p, 'blog':b})
		template = loader.get_template('chat.html')
		html = template.render(context)
		f = open(filename,'w')
		f.write(html.encode('utf-8'))
		f.close()

		print "[chat]", path


	def render_post(self, post, blog):
		if post['type'] == 'text' :
			self.render_text_post(post, blog)
		elif post['type'] == 'photo':
			self.render_photo_post(post, blog)
		elif post['type'] == 'link':
			self.render_link_post(post, blog)
		elif post['type'] == 'quote':
			self.render_quote_post(post, blog)
		elif post['type'] == 'chat':
			self.render_chat_post(post, blog)
		
		else:
			return
			
		self.index.append({
			'id': post['id'], 
			'title': post['title'], 
			'date':post['date'], 
			'timestamp':date.fromtimestamp(post['timestamp']), 
			'type':post['type']
			} )
	
	def render_index(self, page):
		pagination = {'total_pages':self.total_pages, 'current_page':page}
		context = Context({'posts':self.index, 'blog': self.blog_info, 'pagination':pagination} )
		template = loader.get_template('index.html')
		html = template.render(context)
		f = open(os.path.join(self.html_path, ('index%s.html' % page) ),'w')
		f.write(html.encode('utf-8'))
		f.close()
		print "[index%s.html]" % page
		
	def render_20posts(self,offset=0, limit=20):
		self.index = [] # reset indexXXX.html contents.
		request_url = 'http://api.tumblr.com/v2/blog/%s/posts?api_key=%s&offset=%s&limit=%s' % (self.blog, self.tumblr_api_key, offset, limit)
		response = urllib.urlopen(request_url)
		json_response = json.load(response)
		if json_response['meta']['status'] == 200:
			for p in json_response['response']['posts']:
				if self.cont and p['id'] <= self.min_id:
					return False
				if self.last_post_id < p['id']:
					self.last_post_id = p['id']
				self.render_post(post=p, blog=json_response['response']['blog'])
				self.rendered_posts = self.rendered_posts +1 
		return True

	def render_posts(self):
		total = self.get_total_posts()
		pages,posts_to_render = divmod(total, self.ppp)
		
		print "total posts=%s, pages=%s, posts_to_render=%s" % (total, pages, posts_to_render)
		
		# 1st time is special case. Instead of creating a page with few results, we add them to the palst page.
		posts_to_render = posts_to_render + self.ppp 
		offset = 0
		
		for page in range(pages,0,-1):
			print "offset=%s, posts=%s, page=%s" % (offset, posts_to_render, page)
			self.render_20posts(offset,posts_to_render)
			self.render_index(page)
			if page==pages:
				# we copy the last page index file to index.html (duplicate, but provides the index.html we need :-)
				shutil.copy2(os.path.join(self.html_path, ('index%s.html' % page)), os.path.join(self.html_path, 'index.html') )
			offset = offset + posts_to_render
			posts_to_render = self.ppp

		data = {'last_post_id': self.last_post_id, 'blog':self.blog}
		if self.remember_api_key or self.key_from_conf:
			data['tumblr_api_key'] = self.tumblr_api_key
		f = open(os.path.join(self.html_path,'.tumblr2html.json'), 'w')
		f.write(json.dumps(data))
		f.close()


def main(*argv):
	parser = argparse.ArgumentParser(description="usage: tumblr2html.py [options]", prefix_chars='-+')
	parser.add_argument("-k", "--api-key",
		dest="api_key",
		help="tumblr api key. See http://www.tumblr.com/oauth/apps")
	parser.add_argument("--remember-api-key",
		dest="remember_api_key",
		action="store_true", default=False,
		help="remember tumblr api key defined by -k or --api-key. Key will be stored in OUTPUT-PATH/.tumblr2html.json")
	parser.add_argument("-b", "--blog",
		dest="blog",
		help="tumblr blog, ex. 'blog.vrypan.net' or 'engineering.tumblr.com'")
	parser.add_argument("-p", "--path",
		dest="path",
		help="destination path for generated HTML")
	parser.add_argument("-c", "--continue",
		action="store_true", default=False,
		dest="cont",
		help="only download new posts since last backup [does nothing yet]")

	args = parser.parse_args()
	
	t2h = tumblr2html(
		tumblr_api_key=args.api_key, 
		blog=args.blog, 
		html_path=args.path, 
		cont=args.cont,
		remember_api_key=args.remember_api_key)
	if not t2h.init_ok:
		parser.print_help()
	else:
		t2h.render_posts()
	
if __name__ == '__main__':
	main()
