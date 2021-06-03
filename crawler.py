import os
import re
import json
import time
import requests
from requests.cookies import RequestsCookieJar
from bs4 import BeautifulSoup
from lxml import etree
import asyncio, aiohttp

from utils import get_cookies, write_json_data, start_homo_loop
from parse import *

'''
-| Crawler: 
	ouname, search_params, root_url, posts_id, posts_detials, posts_fileobj
----| __del__
----| get_search_page_count: 获取一个账号下相关搜索的页面数【待改进】
----| get_page_async: 异步获取页面内容
----| get_page: 获取页面内容
----| get_posts_id: 获取所有相关贴的id
----| _get_posts_id: 获取单页所有相关贴的id
----| get_post_details: 获取单个帖子的详细信息
----| get_comments: 获取单个帖子的所有评论【待改进：由于TCPConnector的keepalive有的会超时，需要加入异常捕获】
----| _get_post_details_and_post_comments: 获取单个帖子的详细信息和评论
----| get_post_details_and_post_comments: 获取所有帖子的详细信息和评论
----| run: 启动

如果同时爬取多个账号，可以尝试多线程。
'''

class Crawler:
	def __init__(self, ouname, use_local_posts_details=False,
		key_word='袁隆平', start_time='2021-05-21', end_time='2021-05-27'):
		'''
		args:
			ouid: 微博账号id
			ouname: 微博账号名
			rid: 帖子id
		'''
		self.ouname = ouname
		self.search_params = 'is_search=1&visible=0&is_ori=1&key_word={}&start_time={}&end_time={}'.format(key_word, start_time, end_time)
		self.root_url = 'https://weibo.com/{}?{}'.format(ouname, self.search_params)
		self.posts_id = []
		if use_local_posts_details:
			print("load posts detials from local file({})".format('data/{}/posts.json'.format(ouname)))
			with open('data/{}/posts.json'.format(ouname), 'r') as f:
				self.posts_details = json.load(f)
		else:
			self.posts_details = []
		if not os.path.exists('data/{}'.format(ouname)):
			os.makedirs('data/{}'.format(ouname))
		self.posts_fileobj = open('data/{}/posts.json'.format(self.ouname), 'w') # 在__del__方法内使用open()函数会报错


	def get_search_page_count(self):
		'''
		获取总页数。暴力求解（是否有更好的办法）
		'''
		i = 1
		while 1:
			url = '{}&page={}'.format(self.root_url, i)
			page_content = extract_FMView_html(self.get_page(url))
			soup = BeautifulSoup(page_content, 'lxml')
			if not soup.find(attrs={'action-type':'feed_list_item'}):
				return i-1
			i += 1


	async def get_page_async(self, client, url, format='text'):
		'''
		异步获取页面内容。
		'''
		async with client.get(url) as res:
			if format=='text':
				data = await res.text()
			elif format=='json':
				data = await res.json()
			time.sleep(1)
		return data


	def get_page(self, url, format='text'):
		'''
		获取页面内容。
		'''
		res = requests.get(url, headers=headers, cookies=cookies, timeout=timeout)
		time.sleep(1)
		if format=='text':
			return res.text
		elif format=='json':
			return res.json()


	def get_posts_id(self):
		'''
		获取搜索页（单页）内相关帖子id。
		注意：
			页面的加载机制会导致直接基于base_url的html文本不全。根据观察，一页内最多45条帖子，分三次获取数据。
			第一次根据base_url得到15条，之后两次根据数据接口各获得15条（mbloglist）。
		'''
		page_count = self.search_page_count
		# 从搜索页面中的$CONFIG变量中获取post_id, domain, ouid
		page_content = self.get_page(self.root_url)
		self.ouid = re.search(r".+CONFIG\['oid[^\d]+(\d+).+", page_content).group(1) # 之后爬取评论时要使用
		self.page_id = re.search(r".+CONFIG\['page_id[^\d]+(\d+).+", page_content).group(1)
		self.domain = re.search(r".+CONFIG\['domain[^\d]+(\d+).+", page_content).group(1)

		# 搜索页面
		target_search_urls = ['{}&page={}'.format(self.root_url, i) for i in range(page_count)]
		# 数据接口页面
		target_apis = []
		api_base = 'https://weibo.com/p/aj/v6/mblog/mbloglist?ajwvr=6&{}&id={}&domain={}&script_uri=/{}&feed_type=0'.format(
					self.search_params, self.page_id, self.domain, self.ouname)
		for i in range(1, page_count+1):
			target_apis.extend(['{}&pagebar={}&page={}&pre_page={}'.format(api_base, j, i, i) for j in range(2)]) # 90条微博翻页，一个pagebar是45条

		# 协程参数
		args_dicts = []
		for url in target_search_urls:
			args_dicts.append({'url':url, 'preprocessor':extract_FMView_html, 'format':'text'})
		for url in target_apis:
			args_dicts.append({'url':url, 'preprocessor':lambda x: x['data'], 'format':'json'})
		print(args_dicts)
		# 开启协程
		start_homo_loop(self._get_posts_id, args_dicts)


	async def _get_posts_id(self, url, preprocessor, format='text'):
		'''
		获得单个数据接口上的所有post_id
		'''
		async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(
			limit=16, ssl=False, keepalive_timeout=20), headers=headers, cookies=cookies) as client:
				page_data = await self.get_page_async(client, url, format=format)
				if page_data:
					try:
						page_content = preprocessor(page_data)
						posts_id = parse_search_page(page_content)
						self.posts_id.extend(posts_id)
					except:
						print("Failed to get post-ids. [url:{}]".format(url))




	def get_post_details(self, url, post_id):
		'''
		获取帖子的详细数据（mid、发布时间、文本内容、相关链接、转赞评）
		'''
		try:
			page_content = extract_FMView_html(self.get_page(url))
			post_details = parse_post_details(page_content)
			post_details.update({'post_id': post_id, 'ouid': self.ouid})
			self.posts_details.append(post_details)
			# print(post_details)
			return post_details['mid']
		except:
			print("Failed to get post details. [post-id: {}]".format(post_id))


	async def get_comments(self, url, mid):
		'''
		获取单个帖子的评论数据
		'''
		# 从评论数据接口中得到总的评论页数
		page_data = self.get_page('https://weibo.com/aj/v6/comment/big?ajwvr=6&id={}&page=1'.format(mid), format='json')
		total_pages = int(page_data['data']['page']['totalpage'])

		# 循环获取所有页面中的评论数据
		comments = []
		target_urls = ['https://weibo.com/aj/v6/comment/big?ajwvr=6&id={}&page={}'.format(mid, i) for i in range(1, total_pages+1)]
		comments_headers = headers
		comments_headers.update({'Referer': url})
		for url in target_urls:
			async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(
				limit=16, ssl=False, keepalive_timeout=64), headers=comments_headers, cookies=cookies) as client: # 评论可能比较多，这里的keepalive_timeout设置长一点
					page_data = await self.get_page_async(client, url, format='json')
					if page_data:
						try:
							page_content = page_data['data']['html']
							page_comments = parse_comments_page(page_content)
							comments.extend(page_comments)
						except:
							print("Failed to get comments. [mid: {}]".format(mid))
		
		# 将数据写入本地
		filepath = 'data/{}/comments/mid_{}.json'.format(self.ouname, mid)
		write_json_data(data=comments, filepath=filepath)
		print("Save comments. mid: {}".format(mid))



	async def _get_post_details_and_comments(self, url, post_id, mid=None):
		if not mid:
			mid = self.get_post_details(url, post_id) # 返回mid用爬取评论
		if mid:
			await self.get_comments(url, mid)

	
	def get_post_details_and_comments(self):
		if not self.posts_details:
			args_dicts = [{'url': 'https://weibo.com/{}/{}?type=comment#'.format(self.ouid, pid), 'post_id':pid} for pid in self.posts_id]
		else:
			args_dicts = [{'url': 'https://weibo.com/{}/{}?type=comment#'.format(detail['ouid'], detail['post_id']), 
			'post_id':detail['post_id'], 'mid':detail['mid']} for detail in self.posts_details]

		start_homo_loop(self._get_post_details_and_comments, args_dicts)


	def run(self):
		'''
		工作流程：爬取所有搜索页上帖子的id => 爬取每个帖子详情与评论
		并发方式：针对不同的账号使用多线程爬取，针对同一账号下不同帖子的数据使用协程
		'''
		if not self.posts_details:
			# 目前没有想到很好的获取总页数的方法
			self.search_page_count = self.get_search_page_count()
			print("search reaults page count: {}".format(self.search_page_count))
			if self.search_page_count==0: return 

			# 获取相关帖子id
			self.get_posts_id()
			print(self.posts_id, len(self.posts_id))

		# 爬取每个帖子的内容与评论
		self.get_post_details_and_comments()


	def __del__(self):
		# 当程序退出，实例对象被清除时将posts_details数据保存至本地
		write_json_data(data=self.posts_details, fileobj=self.posts_fileobj)


		




if __name__ == '__main__':
	targets = ['newsxh', 'breakingnews'] # 新华网、头条新闻
	global headers, cookies, timeout
	headers = {
		'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/90.0.4430.212 Safari/537.36',
	}
	cookies = get_cookies('cookies.txt') # 注意cookies要更新
	timeout = 20

	crawler = Crawler(ouname=targets[0], use_local_posts_details=False)
	crawler.run()




		

