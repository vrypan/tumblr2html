# tumblr2html
# Copyright 2012 Panayotis Vryonis 
# http://vrypan.net/
# See LICENSE for details.

import json
import urllib
import urllib2
import urlparse
import os
from django.template import Template, Context, loader
from django.conf import settings
import re
from datetime import date

TUMBLR_API_KEY 	= '' # set your key here. see http://www.tumblr.com/oauth/apps
BLOG 			= '' # your tumblr blog, ex. 'blog.vrypan.net' or 'engineering.tumblr.com'
HTML_PATH 		= os.path.join('.','html') # where do you want the generated HTML files to go?

settings.configure(
		DEBUG=True,
		TEMPLATE_DEBUG=True,
		TEMPLATE_DIRS=('templates',)
		)
		
def remove_html_tags(data):
	p = re.compile(r'<.*?>')
	return p.sub('', data)

class tumblr2html(object):
	def __init__(self, tumblr_api_key, blog, html_path):
		self.tumblr_api_key = tumblr_api_key
		self.blog = blog
		self.html_path = html_path
		self.index = []
		self.total_posts = 0
		self.rendered_posts = 0
		self.get_blog_info()
		
	def get_blog_info(self):
		request_url = 'http://api.tumblr.com/v2/blog/%s/info?api_key=%s' % (self.blog, self.tumblr_api_key)
		response = urllib.urlopen(request_url)
		json_response = json.load(response)
		self.total_posts = json_response['response']['blog']['posts']

	def get_total_posts(self):
		if self.total_posts:
			return self.total_posts
		else:
			self.get_blog_info()
			return self.total_posts
			
	def render_text_post(self,p):
		path = os.path.join(self.html_path, 'posts', str(p['id']) )
		filename = os.path.join(path,'index.html')
		if not os.path.exists(path):
			os.makedirs(path)
		f = open(os.path.join(path,'post.json'), 'w')
		f.write(json.dumps(p))
		f.close()

		if not p['title']:
			p['title'] = remove_html_tags(p['body'])[0:100]

		context = Context(p)
		template = loader.get_template('text.html')
		html = template.render(context)
		f = open(filename,'w')
		f.write(html.encode('utf-8'))
		f.close()
		print "[text]", path
		
	def render_photo_post(self,p):
		path = os.path.join(self.html_path, 'posts', str(p['id']) )
		filename = os.path.join(path,'index.html')
		if not os.path.exists(path):
			os.makedirs(path)

		for i,photo in enumerate(p['photos']):			
			img_filename = "%s_original.jpg" % i #TODO: must set right extention!
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
				img_filename = "%s_%sx%s.jpg" % (i, alt['width'], alt['height']) #TODO: must set right extention!
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

		context = Context(p)
		template = loader.get_template('photo.html')
		html = template.render(context)
		f = open(filename,'w')
		f.write(html.encode('utf-8'))
		f.close()

		f = open(os.path.join(path,'post.json'), 'w')
		f.write(json.dumps(p))
		f.close()

		print "[photo]", path
		
	def render_link_post(self,p):
		path = os.path.join(self.html_path, 'posts', str(p['id']) )
		filename = os.path.join(path,'index.html')
		if not os.path.exists(path):
			os.makedirs(path)

		context = Context(p)
		template = loader.get_template('link.html')
		html = template.render(context)
		f = open(filename,'w')
		f.write(html.encode('utf-8'))
		f.close()

		f = open(os.path.join(path,'post.json'), 'w')
		f.write(json.dumps(p))
		f.close()

		print "[link]", path

	def render_post(self, p):
		if p['type'] == 'text' :
			self.render_text_post(p)
		if p['type'] == 'photo':
			self.render_photo_post(p)
		if p['type'] == 'link':
			self.render_link_post(p)

		self.index.append({'id': p['id'], 'title': p['title'], 'date':p['date'], 'timestamp':date.fromtimestamp(p['timestamp'])} )
	
	def render_index(self):
		context = Context({'posts':self.index} )
		template = loader.get_template('index.html')
		html = template.render(context)
		f = open(os.path.join(self.html_path, 'index.html'),'w')
		f.write(html.encode('utf-8'))
		f.close()
		print "[index.html]"
		
	def render_20posts(self,offset=0, limit=20):
		request_url = 'http://api.tumblr.com/v2/blog/%s/posts?api_key=%s&offset=%s&limit=%s' % (self.blog, self.tumblr_api_key, offset, limit)
		response = urllib.urlopen(request_url)
		json_response = json.load(response)
		if json_response['meta']['status'] == 200:
			for p in json_response['response']['posts']:
				self.render_post(p)
				self.rendered_posts = self.rendered_posts +1 

	def render_posts(self):
		total = self.get_total_posts()
		for i in range(0,total,20):
			self.render_20posts(i,20)
		self.render_index()

def main():
	t2h = tumblr2html(tumblr_api_key=TUMBLR_API_KEY, blog=BLOG, html_path=HTML_PATH)
	t2h.get_blog_info()
	t2h.render_posts()
	
if __name__ == '__main__':
	main()